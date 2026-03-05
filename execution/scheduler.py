"""Match scanning and prediction scheduling."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from config.leagues import LEAGUES
from data.database import DatabaseManager
from data_sources.base import DataSourceAdapter
from utils.logging import get_logger

log = get_logger(__name__)


class MatchScheduler:
    """
    Scans for upcoming matches and schedules predictions.
    Coordinates data fetching from sources and DB storage.
    """

    def __init__(
        self,
        db: DatabaseManager,
        data_source: DataSourceAdapter,
        active_leagues: list[str],
        scan_interval: int = 3600,
    ):
        self._db = db
        self._source = data_source
        self._leagues = active_leagues
        self._scan_interval = scan_interval
        self._last_scan: dict[str, float] = {}

    async def scan_upcoming(self, days_ahead: int = 7) -> list[dict]:
        """
        Scan all active leagues for upcoming matches.
        Returns list of {match_id, home_team_id, away_team_id, league_code, match_date}.
        """
        all_upcoming = []

        for league_code in self._leagues:
            if league_code not in LEAGUES:
                continue

            try:
                raw_matches = await self._source.fetch_upcoming_matches(league_code, days_ahead)

                for rm in raw_matches:
                    # Upsert teams
                    home_team = await self._db.upsert_team(
                        name=rm.home_team, league_code=league_code
                    )
                    away_team = await self._db.upsert_team(
                        name=rm.away_team, league_code=league_code
                    )

                    # Upsert match
                    match = await self._db.upsert_match(
                        external_id=rm.external_id,
                        league_code=league_code,
                        season=rm.season,
                        matchday=rm.matchday,
                        match_date=rm.match_date,
                        status=rm.status,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        home_score=rm.home_score,
                        away_score=rm.away_score,
                    )

                    all_upcoming.append({
                        "match_id": match.id,
                        "home_team_id": home_team.id,
                        "away_team_id": away_team.id,
                        "home_team": rm.home_team,
                        "away_team": rm.away_team,
                        "league_code": league_code,
                        "match_date": rm.match_date,
                    })

                log.info("scan_complete", league=league_code, matches=len(raw_matches))
            except Exception as e:
                log.error("scan_error", league=league_code, error=str(e))

        return all_upcoming

    async def sync_results(self) -> list[dict]:
        """
        Fetch and update results for recently finished matches.
        Returns list of newly finished matches.
        """
        finished = []

        for league_code in self._leagues:
            try:
                raw_matches = await self._source.fetch_matches(league_code)

                for rm in raw_matches:
                    if rm.status != "FINISHED" or rm.home_score is None:
                        continue

                    match = await self._db.upsert_match(
                        external_id=rm.external_id,
                        status="FINISHED",
                        home_score=rm.home_score,
                        away_score=rm.away_score,
                        home_ht_score=rm.home_ht_score,
                        away_ht_score=rm.away_ht_score,
                    )
                    finished.append({
                        "match_id": match.id,
                        "external_id": rm.external_id,
                        "home_score": rm.home_score,
                        "away_score": rm.away_score,
                    })

            except Exception as e:
                log.error("result_sync_error", league=league_code, error=str(e))

        return finished

    async def sync_team_stats(self, league_code: str) -> int:
        """Sync team statistics for a league. Returns number of teams updated."""
        try:
            stats = await self._source.fetch_team_stats(league_code)
            for s in stats:
                await self._db.upsert_team(
                    name=s.team_name,
                    league_code=league_code,
                )
            return len(stats)
        except Exception as e:
            log.error("team_stats_sync_error", league=league_code, error=str(e))
            return 0
