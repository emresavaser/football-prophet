"""API-Football (RapidAPI) adapter."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx

from config.leagues import LEAGUES
from .base import DataSourceAdapter, RawMatch, RawTeamStats

BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"


class APIFootballAdapter(DataSourceAdapter):
    """Adapter for API-Football via RapidAPI."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "X-RapidAPI-Key": api_key,
                "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com",
            },
            timeout=30.0,
        )

    @property
    def name(self) -> str:
        return "API-Football"

    def _get_league_id(self, league_code: str) -> int:
        league = LEAGUES.get(league_code)
        if not league:
            raise ValueError(f"Unknown league code: {league_code}")
        return league.api_football_id

    def _current_season(self) -> int:
        now = datetime.utcnow()
        return now.year if now.month >= 7 else now.year - 1

    async def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        resp = await self._client.get(endpoint, params=params)
        resp.raise_for_status()
        return resp.json()

    async def fetch_matches(
        self, league_code: str, season: Optional[str] = None, matchday: Optional[int] = None
    ) -> list[RawMatch]:
        league_id = self._get_league_id(league_code)
        s = int(season.split("-")[0]) if season else self._current_season()
        params = {"league": league_id, "season": s}
        if matchday:
            params["round"] = f"Regular Season - {matchday}"

        data = await self._get("/fixtures", params)
        return [self._parse_fixture(f, league_code) for f in data.get("response", [])]

    async def fetch_upcoming_matches(
        self, league_code: str, days_ahead: int = 7
    ) -> list[RawMatch]:
        league_id = self._get_league_id(league_code)
        date_from = datetime.utcnow().strftime("%Y-%m-%d")
        date_to = (datetime.utcnow() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        params = {
            "league": league_id,
            "season": self._current_season(),
            "from": date_from,
            "to": date_to,
        }
        data = await self._get("/fixtures", params)
        return [self._parse_fixture(f, league_code) for f in data.get("response", [])]

    async def fetch_team_stats(
        self, league_code: str, season: Optional[str] = None
    ) -> list[RawTeamStats]:
        league_id = self._get_league_id(league_code)
        s = int(season.split("-")[0]) if season else self._current_season()
        data = await self._get("/standings", {"league": league_id, "season": s})

        stats = []
        for league_data in data.get("response", []):
            for standing_group in league_data.get("league", {}).get("standings", []):
                for row in standing_group:
                    team_info = row.get("team", {})
                    all_stats = row.get("all", {})
                    home_stats = row.get("home", {})
                    away_stats = row.get("away", {})
                    goals = all_stats.get("goals", {})
                    home_goals = home_stats.get("goals", {})
                    away_goals = away_stats.get("goals", {})

                    stats.append(RawTeamStats(
                        team_name=team_info.get("name", ""),
                        league_code=league_code,
                        played=all_stats.get("played", 0),
                        wins=all_stats.get("win", 0),
                        draws=all_stats.get("draw", 0),
                        losses=all_stats.get("lose", 0),
                        goals_for=goals.get("for", 0),
                        goals_against=goals.get("against", 0),
                        home_wins=home_stats.get("win", 0),
                        home_draws=home_stats.get("draw", 0),
                        home_losses=home_stats.get("lose", 0),
                        away_wins=away_stats.get("win", 0),
                        away_draws=away_stats.get("draw", 0),
                        away_losses=away_stats.get("lose", 0),
                    ))
        return stats

    async def fetch_h2h(
        self, team1_name: str, team2_name: str, limit: int = 10
    ) -> list[RawMatch]:
        # Need team IDs for H2H endpoint - would require team lookup first
        return []

    def _parse_fixture(self, f: dict, league_code: str) -> RawMatch:
        fixture = f.get("fixture", {})
        teams = f.get("teams", {})
        goals = f.get("goals", {})
        score = f.get("score", {})
        halftime = score.get("halftime", {})

        status_map = {
            "NS": "SCHEDULED",
            "1H": "LIVE", "2H": "LIVE", "HT": "LIVE",
            "FT": "FINISHED",
            "PST": "POSTPONED",
            "CANC": "CANCELLED",
        }
        raw_status = fixture.get("status", {}).get("short", "NS")

        match_date = datetime.utcnow()
        date_str = fixture.get("date", "")
        if date_str:
            try:
                match_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return RawMatch(
            external_id=f"apif_{fixture.get('id', '')}",
            league_code=league_code,
            season=str(f.get("league", {}).get("season", "")),
            matchday=f.get("league", {}).get("round", ""),
            match_date=match_date,
            status=status_map.get(raw_status, "SCHEDULED"),
            home_team=teams.get("home", {}).get("name", ""),
            away_team=teams.get("away", {}).get("name", ""),
            home_score=goals.get("home"),
            away_score=goals.get("away"),
            home_ht_score=halftime.get("home"),
            away_ht_score=halftime.get("away"),
        )

    async def close(self) -> None:
        await self._client.aclose()
