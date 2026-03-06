from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from api.routes.odds import get_match_odds


class _FakeDB:
    async def get_odds_history(self, match_id: int):
        return [
            SimpleNamespace(
                id=1,
                match_id=match_id,
                bookmaker="average",
                timestamp=datetime(2026, 3, 1, 10, 0, 0),
                home_win=2.2,
                draw=3.3,
                away_win=3.5,
                over_25=1.95,
                under_25=1.9,
                btts_yes=1.85,
                btts_no=1.95,
                bookmaker_margin=0.04,
            ),
            SimpleNamespace(
                id=2,
                match_id=match_id,
                bookmaker="average",
                timestamp=datetime(2026, 3, 1, 12, 0, 0),
                home_win=2.1,
                draw=3.25,
                away_win=3.6,
                over_25=1.9,
                under_25=1.95,
                btts_yes=1.8,
                btts_no=2.0,
                bookmaker_margin=0.05,
            ),
        ]


class OddsRouteTests(IsolatedAsyncioTestCase):
    async def test_match_odds_returns_full_history(self):
        prophet = SimpleNamespace(db=_FakeDB())

        with patch("api.app.get_prophet", return_value=prophet):
            payload = await get_match_odds(44)

        self.assertEqual(payload.match_id, 44)
        self.assertEqual(len(payload.odds), 2)
        self.assertEqual(payload.odds[0].home_win, 2.2)
        self.assertEqual(payload.odds[1].home_win, 2.1)
