from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from api.routes.dashboard import get_roi


class _FakeDB:
    async def get_model_accuracy(self, days: int = 30):
        return {"accuracy": 0.55, "total": 20, "correct": 11, "avg_brier": 0.22}

    async def get_value_bets(self, upcoming_only: bool = False):
        return [
            SimpleNamespace(market="home_win", clv=0.05, result="WIN", won=True, push=False, kelly_stake=0.03, pnl=0.036),
            SimpleNamespace(market="home_win", clv=-0.02, result="LOSS", won=False, push=False, kelly_stake=0.02, pnl=-0.02),
            SimpleNamespace(market="over_25", clv=0.01, result="PUSH", won=False, push=True, kelly_stake=0.01, pnl=0.0),
        ]


class DashboardRouteTests(IsolatedAsyncioTestCase):
    async def test_roi_aggregates_bet_level_metrics(self):
        prophet = SimpleNamespace(db=_FakeDB(), config=SimpleNamespace(bankroll=1000.0))

        with patch("api.app.get_prophet", return_value=prophet):
            payload = await get_roi()

        self.assertEqual(payload["value_bets_total"], 3)
        self.assertEqual(payload["settled_bets"], 3)
        self.assertEqual(payload["wins"], 1)
        self.assertEqual(payload["pushes"], 1)
        self.assertAlmostEqual(payload["total_staked"], 0.06)
        self.assertAlmostEqual(payload["total_pnl"], 0.016)
        self.assertAlmostEqual(payload["roi"], 0.016 / 0.06)
        self.assertEqual(payload["value_bets_by_market"]["home_win"]["wins"], 1)
