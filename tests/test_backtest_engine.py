from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from analysis.base import PredictionResult
from brain.memory import ProphetMemory
from execution.backtest_engine import BacktestEngine


class _FakeDB:
    async def get_league_matches(self, league_code: str, season=None, finished_only: bool = True):
        base = datetime(2025, 1, 1)
        matches = []
        for i in range(6):
            matches.append(
                SimpleNamespace(
                    id=i + 1,
                    match_date=base + timedelta(days=i),
                    home_team_id=100 + i,
                    away_team_id=200 + i,
                    league_code=league_code,
                    home_score=0,
                    away_score=1,
                    result="AWAY",
                )
            )
        return matches

    async def get_latest_odds(self, match_id: int):
        return SimpleNamespace(home_win=2.0, draw=3.0, away_win=3.5)

    async def save_backtest_result(self, **kwargs):
        return kwargs


class _FakeEnsemble:
    init_args: list[tuple[float, int, float]] = []

    def __init__(self, memory, learner, k_factor: float, form_window: int, form_decay: float):
        self.memory = memory
        self.learner = learner
        type(self).init_args.append((k_factor, form_window, form_decay))

    def train_ml_from_matches(self, matches):
        return {"status": "trained", "samples": len(list(matches))}

    def predict(self, home_team_id: int, away_team_id: int, league_code: str):
        return PredictionResult(home_win_prob=0.65, draw_prob=0.2, away_win_prob=0.15, confidence=0.7)

    def record_result(self, home_team_id: int, away_team_id: int, home_score: int, away_score: int, prediction):
        return {}


class _FakeEVCalculator:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def evaluate_match(self, *args, **kwargs):
        return [
            SimpleNamespace(
                is_value=True,
                market="home_win",
                kelly_stake=0.25,
                odds=2.0,
                model_prob=0.65,
                implied_prob=0.5,
                fair_prob=0.48,
                overround=1.05,
                edge=0.17,
                ev=0.3,
            )
        ]


class BacktestEngineTests(IsolatedAsyncioTestCase):
    async def test_backtest_uses_configured_model_params_and_staking_policy(self):
        _FakeEnsemble.init_args.clear()
        engine = BacktestEngine(
            db=_FakeDB(),
            memory=ProphetMemory(),
            bankroll=100.0,
            max_stake_fraction=0.5,
            staking_policy="flat",
            elo_k_factor=11.0,
            form_window=6,
            form_decay=0.77,
            initial_model_weights={"poisson": 0.2, "elo": 0.3, "form": 0.2, "h2h": 0.1, "ml": 0.2},
        )

        with patch("execution.backtest_engine.EnsemblePredictor", _FakeEnsemble), patch(
            "execution.backtest_engine.EVCalculator",
            _FakeEVCalculator,
        ):
            result = await engine.run_backtest("PL")

        self.assertEqual(_FakeEnsemble.init_args[0], (11.0, 6, 0.77))
        self.assertEqual(result["staking_policy"], "flat")
        self.assertEqual(result["final_bankroll"], 96.0)
        self.assertEqual(result["settled_bets"], 4)
        self.assertEqual(len(result["bet_results"]), 4)
        self.assertIn("home_win", result["value_bets_by_market"])
