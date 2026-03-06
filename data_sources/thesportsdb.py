"""TheSportsDB adapter for all supported leagues (free, no key required)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from .base import DataSourceAdapter, RawMatch, RawTeamStats
from config.leagues import LEAGUES, get_league

BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"


# Season format for TheSportsDB: "2025-2026"
def _current_season() -> str:
    now = datetime.now(timezone.utc)
    year = now.year if now.month >= 7 else now.year - 1
    return f"{year}-{year + 1}"


def _get_league_id(league_code: str) -> int | None:
    """Get TheSportsDB league ID from leagues config."""
    league = get_league(league_code)
    if league and league.thesportsdb_id:
        return league.thesportsdb_id
    return None


class TheSportsDBAdapter(DataSourceAdapter):
    """Adapter for TheSportsDB free API (all supported leagues)."""

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        self._last_request_ts = 0.0

    @property
    def name(self) -> str:
        return "TheSportsDB"

    async def _throttled_get(self, url: str, params: Optional[dict] = None) -> dict:
        """Rate-limited GET (max 30 req/min)."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_ts
        if elapsed < 2.0:
            await asyncio.sleep(2.0 - elapsed)

        resp = await self._client.get(url, params=params)
        self._last_request_ts = asyncio.get_event_loop().time()
        resp.raise_for_status()
        return resp.json()

    async def fetch_season_matches(
        self, league_code: str, season: str, max_rounds: int = 42
    ) -> list[RawMatch]:
        """Fetch all matches for a season using round-by-round requests.

        eventsseason.php is limited to 15 results on the free tier,
        so we use eventsround.php which returns all matches per round.
        """
        league_id = _get_league_id(league_code)
        if not league_id:
            return []

        all_matches: list[RawMatch] = []
        empty_streak = 0

        for r in range(1, max_rounds + 1):
            data = await self._throttled_get(
                f"{BASE_URL}/eventsround.php",
                {"id": league_id, "r": r, "s": season},
            )
            events = data.get("events") or []
            if not events:
                empty_streak += 1
                # Stop after 2 consecutive empty rounds
                if empty_streak >= 2:
                    break
                continue

            empty_streak = 0
            all_matches.extend(self._parse_event(e, league_code, season) for e in events)

        return all_matches

    async def fetch_matches(
        self, league_code: str, season: Optional[str] = None, matchday: Optional[int] = None
    ) -> list[RawMatch]:
        league_id = _get_league_id(league_code)
        if not league_id:
            return []

        s = season or _current_season()

        if matchday:
            data = await self._throttled_get(
                f"{BASE_URL}/eventsround.php",
                {"id": league_id, "r": matchday, "s": s},
            )
            events = data.get("events") or []
            return [self._parse_event(e, league_code, s) for e in events]

        return await self.fetch_season_matches(league_code, s)

    async def fetch_upcoming_matches(
        self, league_code: str, days_ahead: int = 7
    ) -> list[RawMatch]:
        league_id = _get_league_id(league_code)
        if not league_id:
            return []

        s = _current_season()
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)

        # Scan rounds to find upcoming matches
        upcoming: list[RawMatch] = []
        found_future = False

        for r in range(1, 42):
            data = await self._throttled_get(
                f"{BASE_URL}/eventsround.php",
                {"id": league_id, "r": r, "s": s},
            )
            events = data.get("events") or []
            if not events:
                break

            for e in events:
                match = self._parse_event(e, league_code, s)
                if match.status == "SCHEDULED" and now <= match.match_date <= cutoff:
                    upcoming.append(match)
                    found_future = True

            # If we found upcoming and this round is past cutoff, stop
            if found_future:
                all_past_cutoff = all(
                    self._parse_event(e, league_code, s).match_date > cutoff
                    for e in events
                )
                if all_past_cutoff:
                    break

        return upcoming

    async def fetch_team_stats(
        self, league_code: str, season: Optional[str] = None
    ) -> list[RawTeamStats]:
        league_id = _get_league_id(league_code)
        if not league_id:
            return []

        s = season or _current_season()
        data = await self._throttled_get(
            f"{BASE_URL}/lookuptable.php",
            {"l": league_id, "s": s},
        )

        stats = []
        for row in data.get("table") or []:
            stats.append(RawTeamStats(
                team_name=row.get("strTeam", ""),
                league_code=league_code,
                played=int(row.get("intPlayed", 0)),
                wins=int(row.get("intWin", 0)),
                draws=int(row.get("intDraw", 0)),
                losses=int(row.get("intLoss", 0)),
                goals_for=int(row.get("intGoalsFor", 0)),
                goals_against=int(row.get("intGoalsAgainst", 0)),
            ))
        return stats

    async def fetch_h2h(
        self, team1_name: str, team2_name: str, limit: int = 10
    ) -> list[RawMatch]:
        return []

    def _parse_event(self, e: dict, league_code: str, season: str) -> RawMatch:
        status_raw = e.get("strStatus") or ""
        if status_raw == "Match Finished":
            status = "FINISHED"
        elif status_raw in ("Not Started", ""):
            status = "SCHEDULED"
        else:
            status = "LIVE"

        match_date = datetime.now(timezone.utc)
        date_str = e.get("dateEvent", "")
        time_str = e.get("strTime") or "00:00:00"
        if date_str:
            try:
                match_date = datetime.strptime(
                    f"{date_str} {time_str[:5]}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass

        home_score = None
        away_score = None
        if status == "FINISHED":
            try:
                hs = e.get("intHomeScore")
                as_ = e.get("intAwayScore")
                if hs is not None and hs != "":
                    home_score = int(hs)
                if as_ is not None and as_ != "":
                    away_score = int(as_)
            except (ValueError, TypeError):
                pass

        return RawMatch(
            external_id=str(e.get("idEvent", "")),
            league_code=league_code,
            season=season.split("-")[0],
            matchday=int(e.get("intRound", 0)) or None,
            match_date=match_date,
            status=status,
            home_team=e.get("strHomeTeam", ""),
            away_team=e.get("strAwayTeam", ""),
            home_score=home_score,
            away_score=away_score,
        )

    async def close(self) -> None:
        await self._client.aclose()
