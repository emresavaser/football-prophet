from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from data_sources.historical_collector import HistoricalDataCollector


class _FakeDB:
    async def upsert_team(self, name: str, league_code: str):
        return SimpleNamespace(id=1 if name == "Home" else 2)

    async def get_match_by_external_id(self, external_id: str):
        if external_id == "existing":
            return SimpleNamespace(id=99)
        return None

    async def upsert_match(self, external_id: str, **kwargs):
        return SimpleNamespace(id=1, external_id=external_id)


class _FakeAdapter:
    async def fetch_season_matches(self, league_code: str, season: str):
        return [
            SimpleNamespace(
                external_id="existing",
                season=season,
                matchday=1,
                match_date=datetime(2025, 1, 1),
                status="FINISHED",
                home_team="Home",
                away_team="Away",
                home_score=1,
                away_score=0,
            ),
            SimpleNamespace(
                external_id="new-one",
                season=season,
                matchday=2,
                match_date=datetime(2025, 1, 2),
                status="SCHEDULED",
                home_team="Home",
                away_team="Away",
                home_score=None,
                away_score=None,
            ),
        ]


class HistoricalCollectorTests(IsolatedAsyncioTestCase):
    async def test_collect_counts_only_new_matches(self):
        collector = HistoricalDataCollector(db=_FakeDB(), adapter=_FakeAdapter())

        summary = await collector.collect(["PL"], seasons=["2025-2026"])

        self.assertEqual(summary["total_fetched"], 2)
        self.assertEqual(summary["total_new"], 1)
        self.assertEqual(summary["leagues"]["PL"]["new"], 1)
