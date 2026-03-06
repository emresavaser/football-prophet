"""XGBoost/sklearn machine learning model for match prediction."""

from __future__ import annotations

from typing import Optional

import numpy as np

from brain.memory import ProphetMemory
from .base import PredictionModel, PredictionResult

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler


class MLModel(PredictionModel):
    """
    Machine learning model using XGBoost (or sklearn fallback).
    Features: ELO diff, form diff, attack/defense strengths, H2H stats, venue.
    """

    def __init__(self, memory: ProphetMemory):
        self._memory = memory
        self._scaler = StandardScaler()
        self._model: Optional[object] = None
        self._is_trained = False
        self._feature_names = [
            "elo_diff", "form_diff",
            "home_attack", "home_defense",
            "away_attack", "away_defense",
            "home_home_ppg", "away_away_ppg",
            "h2h_home_win_rate", "h2h_avg_goals",
            "home_trend_val", "away_trend_val",
        ]

    @property
    def name(self) -> str:
        return "ml"

    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        league_code: str,
        **context,
    ) -> PredictionResult:
        features = self._extract_features(home_team_id, away_team_id, league_code)

        if self._is_trained and self._model is not None:
            X = np.array([features])
            try:
                X_scaled = self._scaler.transform(X)
            except Exception:
                X_scaled = X
            proba = self._model.predict_proba(X_scaled)[0]
            # Classes: 0=AWAY, 1=DRAW, 2=HOME (alphabetical)
            away_prob, draw_prob, home_prob = proba[0], proba[1], proba[2]
        else:
            # Fallback: heuristic from features
            home_prob, draw_prob, away_prob = self._heuristic_predict(features)

        # Goal estimates
        league_avg = self._memory.get_league_avg(league_code)
        strength_diff = features[0] / 400.0  # ELO diff normalized
        pred_home = league_avg.avg_home_goals * (1 + strength_diff * 0.15)
        pred_away = league_avg.avg_away_goals * (1 - strength_diff * 0.15)

        confidence = max(home_prob, draw_prob, away_prob)

        result = PredictionResult(
            home_win_prob=home_prob,
            draw_prob=draw_prob,
            away_win_prob=away_prob,
            predicted_home_goals=max(0.2, pred_home),
            predicted_away_goals=max(0.2, pred_away),
            most_likely_score=f"{round(pred_home)}-{round(pred_away)}",
            confidence=confidence,
            model_name=self.name,
            details={"trained": self._is_trained, "features": dict(zip(self._feature_names, features))},
        )
        result.normalize_probs()
        return result

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Train the model on historical data. y: 0=AWAY, 1=DRAW, 2=HOME."""
        if len(X) < 50:
            return {"status": "insufficient_data", "samples": len(X)}

        self._scaler.fit(X)
        X_scaled = self._scaler.transform(X)

        if HAS_XGBOOST:
            self._model = XGBClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.05,
                objective="multi:softprob",
                num_class=3,
                eval_metric="mlogloss",
                use_label_encoder=False,
            )
        else:
            self._model = GradientBoostingClassifier(n_estimators=200, learning_rate=0.05)

        self._model.fit(X_scaled, y)
        self._is_trained = True

        train_score = self._model.score(X_scaled, y)
        return {"status": "trained", "samples": len(X), "train_accuracy": train_score}

    def extract_features(self, home_id: int, away_id: int, league_code: str) -> list[float]:
        hp = self._memory.get_team_profile(home_id)
        ap = self._memory.get_team_profile(away_id)
        h2h = self._memory.get_h2h(home_id, away_id)

        elo_diff = (hp.elo_rating or 1500) - (ap.elo_rating or 1500)
        form_diff = hp.form_score - ap.form_score

        home_ppg = hp.home_record.points / hp.home_record.played if hp.home_record.played > 0 else 1.0
        away_ppg = ap.away_record.points / ap.away_record.played if ap.away_record.played > 0 else 1.0

        h2h_rate = 0.5
        if h2h.total_matches > 0:
            if home_id == h2h.team1_id:
                h2h_rate = h2h.team1_wins / h2h.total_matches
            else:
                h2h_rate = h2h.team2_wins / h2h.total_matches

        trend_map = {"rising": 1.0, "stable": 0.0, "declining": -1.0}

        return [
            elo_diff,
            form_diff,
            hp.attack_strength,
            hp.defense_strength,
            ap.attack_strength,
            ap.defense_strength,
            home_ppg,
            away_ppg,
            h2h_rate,
            h2h.avg_total_goals,
            trend_map.get(hp.trend, 0.0),
            trend_map.get(ap.trend, 0.0),
        ]

    def _extract_features(self, home_id: int, away_id: int, league_code: str) -> list[float]:
        return self.extract_features(home_id, away_id, league_code)

    @staticmethod
    def _heuristic_predict(features: list[float]) -> tuple[float, float, float]:
        """Simple heuristic when ML model is not trained."""
        elo_diff = features[0]
        form_diff = features[1]

        # Sigmoid-like mapping
        combined = elo_diff / 400.0 + form_diff * 2.0
        home_strength = 1.0 / (1.0 + np.exp(-combined))

        draw_prob = max(0.15, 0.28 - abs(combined) * 0.1)
        home_prob = home_strength * (1 - draw_prob)
        away_prob = (1 - home_strength) * (1 - draw_prob)

        return home_prob, draw_prob, away_prob

    def is_ready(self) -> bool:
        return self._is_trained and len(self._memory.team_profiles) >= 2
