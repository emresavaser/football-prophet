from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from api.routes.backtests import get_backtest, list_backtests


class _FakeDB:
    async def list_backtests(self, league_code=None, limit: int = 20, offset: int = 0):
        return [
            SimpleNamespace(
                run_id="run-2",
                created_at=datetime(2026, 3, 6, 12, 0, 0),
                league_code=league_code or "PL",
                date_from=datetime(2025, 8, 1),
                date_to=datetime(2026, 2, 1),
                total_matches=120,
                correct_predictions=65,
                accuracy=0.54,
                total_bets=40,
                winning_bets=22,
                roi=0.12,
                profit_loss=120.0,
                avg_brier_score=0.21,
            )
        ]

    async def get_backtest(self, run_id: str):
        return SimpleNamespace(
            run_id=run_id,
            created_at=datetime(2026, 3, 6, 12, 0, 0),
            league_code="PL",
            date_from=datetime(2025, 8, 1),
            date_to=datetime(2026, 2, 1),
            total_matches=120,
            correct_predictions=65,
            accuracy=0.54,
            total_bets=40,
            winning_bets=22,
            roi=0.12,
            profit_loss=120.0,
            avg_brier_score=0.21,
            avg_confidence=0.64,
            avg_edge=0.08,
            model_weights_used=json.dumps({"elo": 0.3, "ml": 0.2}),
            config_snapshot=json.dumps({"staking_policy": "flat"}),
            report_json=json.dumps({"bet_summary": {"roi": 0.12}, "bet_results": [{"market": "home_win", "pnl": 0.5}]}),
        )


class BacktestsRouteTests(IsolatedAsyncioTestCase):
    async def test_list_backtests_returns_summary_rows(self):
        prophet = SimpleNamespace(db=_FakeDB())

        with patch("api.app.get_prophet", return_value=prophet):
            payload = await list_backtests(league="pl", limit=5, offset=2)

        self.assertEqual(payload.total, 1)
        self.assertEqual(payload.offset, 2)
        self.assertEqual(payload.limit, 5)
        self.assertEqual(payload.backtests[0].run_id, "run-2")
        self.assertEqual(payload.backtests[0].league_code, "PL")

    async def test_get_backtest_returns_parsed_detail_payload(self):
        prophet = SimpleNamespace(db=_FakeDB())

        with patch("api.app.get_prophet", return_value=prophet):
            payload = await get_backtest("run-2")

        self.assertEqual(payload.run_id, "run-2")
        self.assertEqual(payload.model_weights_used["elo"], 0.3)
        self.assertEqual(payload.config_snapshot["staking_policy"], "flat")
        self.assertEqual(payload.report["bet_summary"]["roi"], 0.12)
        self.assertEqual(payload.report["bet_results"][0]["market"], "home_win")
