from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from api.routes.predictions import get_value_bets


class _FakeDB:
    async def get_value_bets(self, upcoming_only: bool = True):
        return [
            SimpleNamespace(
                match_id=55,
                value_bet_market="draw",
                home_win_prob=0.5,
                draw_prob=0.3,
                away_win_prob=0.2,
                over_25_prob=0.61,
                btts_prob=0.58,
                edge=0.08,
                ev=0.14,
                kelly_stake=0.03,
                confidence=0.67,
                fair_prob=0.28,
                overround=1.05,
                id=10,
                prediction_id=99,
                odds=3.25,
                implied_prob=1 / 3.25,
            )
        ]

    async def get_match(self, match_id: int):
        return SimpleNamespace(
            id=match_id,
            league_code="PL",
            home_team_id=1,
            away_team_id=2,
            match_date=datetime(2026, 3, 10, 20, 0, 0),
        )

    async def get_team(self, team_id: int):
        names = {1: "Home FC", 2: "Away FC"}
        return SimpleNamespace(name=names[team_id])

    async def get_latest_odds(self, match_id: int):
        return SimpleNamespace(home_win=2.1, draw=3.1, away_win=3.8, over_25=1.95, btts_yes=1.88)


class PredictionRouteTests(IsolatedAsyncioTestCase):
    async def test_value_bets_returns_market_specific_payload(self):
        prophet = SimpleNamespace(db=_FakeDB())

        with patch("api.app.get_prophet", return_value=prophet):
            payload = await get_value_bets()

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0].market, "draw")
        self.assertEqual(payload[0].odds, 3.1)
        self.assertEqual(payload[0].model_prob, 0.3)
        self.assertAlmostEqual(payload[0].implied_prob, 1 / 3.25)
        self.assertEqual(payload[0].closing_odds, 3.1)
        self.assertAlmostEqual(payload[0].clv, (3.25 - 3.1) / 3.1)
