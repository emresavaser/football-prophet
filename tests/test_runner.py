from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from bot.runner import Runner


class _FakeCache:
    def __init__(self) -> None:
        self.values: dict[object, dict] = {}

    def cache_odds(self, key, value) -> None:
        self.values[key] = value

    def get_odds(self, key):
        return self.values.get(key)


class _FakeDB:
    def __init__(self) -> None:
        self.saved: list[dict] = []

    async def get_match_by_external_id(self, external_id: str):
        if external_id == "ext-1":
            return SimpleNamespace(id=77)
        return None

    async def save_odds(self, **kwargs):
        self.saved.append(kwargs)


class _FakeOddsProvider:
    async def fetch_odds(self, league_code: str):
        return [
            SimpleNamespace(
                match_external_id="ext-1",
                bookmaker="average",
                home_win=2.1,
                draw=3.4,
                away_win=3.6,
                over_25=1.9,
                under_25=1.95,
                btts_yes=1.8,
                btts_no=2.0,
            )
        ]


class RunnerOddsTests(IsolatedAsyncioTestCase):
    async def test_update_odds_caches_with_stable_keys_and_saves_db_snapshot(self):
        cache = _FakeCache()
        db = _FakeDB()
        prophet = SimpleNamespace(
            config=SimpleNamespace(active_leagues=["PL"]),
            odds_provider=_FakeOddsProvider(),
            cache=cache,
            db=db,
        )

        runner = Runner(prophet)
        await runner._update_odds()

        self.assertIn("ext-1", cache.values)
        self.assertIn(77, cache.values)
        self.assertEqual(cache.values["ext-1"]["draw"], 3.4)
        self.assertEqual(db.saved[0]["match_id"], 77)

    async def test_scan_matches_reads_odds_from_external_id_cache(self):
        captured: list[dict] = []
        cache = _FakeCache()
        cache.cache_odds("ext-9", {"home_win": 2.2, "draw": 3.1, "away_win": 3.5})

        class _FakeScheduler:
            async def scan_upcoming(self, days_ahead: int = 7):
                return [
                    {
                        "match_id": 9,
                        "external_id": "ext-9",
                        "home_team_id": 1,
                        "away_team_id": 2,
                        "league_code": "PL",
                        "home_team": "Home",
                        "away_team": "Away",
                    }
                ]

            async def sync_results(self):
                return []

        class _FakePredictionManager:
            async def predict_match(self, **kwargs):
                captured.append(kwargs["odds"])
                return SimpleNamespace(), []

        prophet = SimpleNamespace(
            scheduler=_FakeScheduler(),
            prediction_manager=_FakePredictionManager(),
            odds_provider=object(),
            cache=cache,
            notifier=None,
            state=SimpleNamespace(
                active_predictions={},
                scan_stats=SimpleNamespace(record_scan=lambda **kwargs: None),
            ),
        )

        runner = Runner(prophet)
        await runner._scan_matches()

        self.assertEqual(captured[0]["home_win"], 2.2)
