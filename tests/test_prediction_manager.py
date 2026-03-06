from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from analysis.base import PredictionResult
from execution.prediction_manager import PredictionManager


class _FakeDB:
    def __init__(self) -> None:
        self.saved_prediction = None
        self.saved_value_bets = None
        self.updated_prediction = None
        self.settled_value_bets = []
        self.predictions = []

    async def save_prediction(self, **kwargs):
        self.saved_prediction = kwargs
        return SimpleNamespace(id=123)

    async def save_value_bets(self, prediction_id: int, match_id: int, value_bets):
        self.saved_value_bets = {
            "prediction_id": prediction_id,
            "match_id": match_id,
            "value_bets": value_bets,
        }

    async def get_pending_predictions(self):
        return self.predictions

    async def get_match(self, match_id: int):
        return SimpleNamespace(
            id=match_id,
            status="FINISHED",
            home_team_id=1,
            away_team_id=2,
            home_score=2,
            away_score=1,
            league_code="PL",
        )

    async def update_prediction_result(self, prediction_id: int, outcome: str, is_correct: bool, brier: float):
        self.updated_prediction = {
            "prediction_id": prediction_id,
            "outcome": outcome,
            "is_correct": is_correct,
            "brier": brier,
        }

    async def get_value_bets_for_prediction(self, prediction_id: int):
        return [
            SimpleNamespace(id=1, market="home_win", odds=2.2, kelly_stake=0.03),
            SimpleNamespace(id=2, market="over_25", odds=1.9, kelly_stake=0.04),
            SimpleNamespace(id=3, market="btts_no", odds=1.8, kelly_stake=0.02),
        ]

    async def get_latest_odds(self, match_id: int):
        return SimpleNamespace(home_win=2.0, over_25=2.1, btts_no=1.7)

    async def settle_value_bet(self, value_bet_id: int, **kwargs):
        self.settled_value_bets.append((value_bet_id, kwargs))


class _FakeEnsemble:
    def predict(self, home_team_id: int, away_team_id: int, league_code: str):
        return PredictionResult(home_win_prob=0.5, draw_prob=0.2, away_win_prob=0.3, confidence=0.7)


class _FakeState:
    def __init__(self) -> None:
        self.scan_stats = SimpleNamespace(record_scan=lambda **kwargs: None)
        self.model_results = []
        self.removed = []

    def add_prediction(self, match_id: int, payload: dict) -> None:
        self.last_prediction = (match_id, payload)

    def record_model_result(self, model_name: str, is_correct: bool) -> None:
        self.model_results.append((model_name, is_correct))

    def remove_prediction(self, match_id: int) -> None:
        self.removed.append(match_id)


class PredictionManagerTests(IsolatedAsyncioTestCase):
    async def test_predict_match_persists_all_value_bets(self):
        db = _FakeDB()
        manager = PredictionManager(
            db=db,
            ensemble=_FakeEnsemble(),
            memory=SimpleNamespace(),
            state=_FakeState(),
            value_finder=SimpleNamespace(
                find_value=lambda **kwargs: [
                    SimpleNamespace(
                        market="home_win",
                        model_prob=0.5,
                        implied_prob=0.45,
                        fair_prob=0.44,
                        overround=1.05,
                        odds=2.2,
                        ev=0.1,
                        edge=0.06,
                        kelly_stake=0.03,
                        confidence=0.7,
                    ),
                    SimpleNamespace(
                        market="over_25",
                        model_prob=0.58,
                        implied_prob=0.5,
                        fair_prob=0.48,
                        overround=1.04,
                        odds=2.0,
                        ev=0.12,
                        edge=0.1,
                        kelly_stake=0.04,
                        confidence=0.7,
                    ),
                ]
            ),
        )

        _, value_bets = await manager.predict_match(
            match_id=50,
            home_team_id=1,
            away_team_id=2,
            league_code="PL",
            odds={"home_win": 2.2, "over_25": 2.0, "under_25": 1.8},
            home_team_name="Home",
            away_team_name="Away",
        )

        self.assertEqual(len(value_bets), 2)
        self.assertEqual(db.saved_prediction["value_bet_market"], "home_win")
        self.assertEqual(db.saved_value_bets["prediction_id"], 123)
        self.assertEqual(len(db.saved_value_bets["value_bets"]), 2)
        self.assertEqual(db.saved_value_bets["value_bets"][1]["market"], "over_25")

    async def test_check_results_settles_value_bets_and_persists_clv(self):
        db = _FakeDB()
        db.predictions = [
            SimpleNamespace(
                id=88,
                match_id=50,
                home_win_prob=0.5,
                draw_prob=0.2,
                away_win_prob=0.3,
                model_breakdown="{}",
            )
        ]
        state = _FakeState()
        memory_updates = []
        manager = PredictionManager(
            db=db,
            ensemble=SimpleNamespace(record_result=lambda *args, **kwargs: {}),
            memory=SimpleNamespace(update_after_match=lambda *args: memory_updates.append(args)),
            state=state,
            value_finder=SimpleNamespace(),
        )

        processed = await manager.check_results()

        self.assertEqual(len(processed), 1)
        self.assertEqual(db.updated_prediction["outcome"], "HOME")
        self.assertEqual(len(db.settled_value_bets), 3)
        home_win = dict(db.settled_value_bets[0][1])
        over_25 = dict(db.settled_value_bets[1][1])
        btts_no = dict(db.settled_value_bets[2][1])
        self.assertEqual(home_win["result"], "WIN")
        self.assertEqual(home_win["pnl"], 0.036)
        self.assertEqual(home_win["closing_odds"], 2.0)
        self.assertEqual(over_25["result"], "WIN")
        self.assertEqual(btts_no["result"], "LOSS")
        self.assertEqual(state.removed, [50])
