"""football-data.org API adapter (free tier: 10 req/min)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx

from .base import DataSourceAdapter, RawMatch, RawTeamStats

BASE_URL = "https://api.football-data.org/v4"


class FootballDataOrgAdapter(DataSourceAdapter):
    """Adapter for football-data.org REST API."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"X-Auth-Token": api_key},
            timeout=30.0,
        )
        self._request_count = 0
        self._last_request_ts = 0.0

    @property
    def name(self) -> str:
        return "football-data.org"

    async def _throttled_get(self, url: str, params: Optional[dict] = None) -> dict:
        """Rate-limited GET request (max 10/min)."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_ts
        if elapsed < 6.0:  # ~10 req/min safety
            await asyncio.sleep(6.0 - elapsed)

        resp = await self._client.get(url, params=params)
        self._last_request_ts = asyncio.get_event_loop().time()
        self._request_count += 1
        resp.raise_for_status()
        return resp.json()

    async def fetch_matches(
        self, league_code: str, season: Optional[str] = None, matchday: Optional[int] = None
    ) -> list[RawMatch]:
        params = {}
        if season:
            params["season"] = season.split("-")[0]  # "2024-25" → "2024"
        if matchday:
            params["matchday"] = matchday

        data = await self._throttled_get(f"/competitions/{league_code}/matches", params)
        return [self._parse_match(m, league_code) for m in data.get("matches", [])]

    async def fetch_upcoming_matches(
        self, league_code: str, days_ahead: int = 7
    ) -> list[RawMatch]:
        date_from = datetime.utcnow().strftime("%Y-%m-%d")
        date_to = (datetime.utcnow() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        params = {"dateFrom": date_from, "dateTo": date_to, "status": "SCHEDULED"}
        data = await self._throttled_get(f"/competitions/{league_code}/matches", params)
        return [self._parse_match(m, league_code) for m in data.get("matches", [])]

    async def fetch_team_stats(
        self, league_code: str, season: Optional[str] = None
    ) -> list[RawTeamStats]:
        params = {}
        if season:
            params["season"] = season.split("-")[0]
        data = await self._throttled_get(f"/competitions/{league_code}/standings", params)

        stats = []
        for table in data.get("standings", []):
            if table.get("type") != "TOTAL":
                continue
            for row in table.get("table", []):
                team = row.get("team", {})
                stats.append(RawTeamStats(
                    team_name=team.get("name", ""),
                    league_code=league_code,
                    played=row.get("playedGames", 0),
                    wins=row.get("won", 0),
                    draws=row.get("draw", 0),
                    losses=row.get("lost", 0),
                    goals_for=row.get("goalsFor", 0),
                    goals_against=row.get("goalsAgainst", 0),
                ))
        return stats

    async def fetch_h2h(
        self, team1_name: str, team2_name: str, limit: int = 10
    ) -> list[RawMatch]:
        # football-data.org doesn't have a direct H2H endpoint
        # This would need to be derived from match history
        return []

    def _parse_match(self, m: dict, league_code: str) -> RawMatch:
        score = m.get("score", {})
        full_time = score.get("fullTime", {})
        half_time = score.get("halfTime", {})
        season_info = m.get("season", {})
        season_str = str(season_info.get("startDate", ""))[:4] if season_info else ""

        match_date_str = m.get("utcDate", "")
        match_date = datetime.utcnow()
        if match_date_str:
            try:
                match_date = datetime.fromisoformat(match_date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return RawMatch(
            external_id=str(m.get("id", "")),
            league_code=league_code,
            season=season_str,
            matchday=m.get("matchday"),
            match_date=match_date,
            status=m.get("status", "SCHEDULED"),
            home_team=m.get("homeTeam", {}).get("name", ""),
            away_team=m.get("awayTeam", {}).get("name", ""),
            home_score=full_time.get("home"),
            away_score=full_time.get("away"),
            home_ht_score=half_time.get("home"),
            away_ht_score=half_time.get("away"),
        )

    async def close(self) -> None:
        await self._client.aclose()
