"""Ensemble predictor combining all models with learned weights."""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np

from brain.memory import ProphetMemory
from brain.learning import AdaptiveLearner
from .base import PredictionModel, PredictionResult
from .poisson_model import PoissonModel
from .elo_rating import ELORatingModel
from .form_analyzer import FormAnalyzer
from .h2h_analyzer import H2HAnalyzer
from .ml_model import MLModel


class EnsemblePredictor:
    """
    Combines all prediction models using weighted ensemble.
    Weights are dynamically adjusted by the AdaptiveLearner.
    """

    def __init__(
        self,
        memory: ProphetMemory,
        learner: AdaptiveLearner,
        k_factor: float = 32.0,
        form_window: int = 10,
        form_decay: float = 0.9,
    ):
        self._memory = memory
        self._learner = learner
        self._k_factor = k_factor
        self._form_window = form_window
        self._form_decay = form_decay

        # Initialize sub-models
        self._models: dict[str, PredictionModel] = {
            "poisson": PoissonModel(memory),
            "elo": ELORatingModel(memory, k_factor=k_factor),
            "form": FormAnalyzer(memory, window=form_window, decay=form_decay),
            "h2h": H2HAnalyzer(memory),
            "ml": MLModel(memory),
        }

    def train_ml_from_matches(self, matches: Iterable, min_samples: int = 50) -> dict:
        """Train the ML model on chronological pre-match features."""
        ml_model = self._models.get("ml")
        if not isinstance(ml_model, MLModel):
            return {"status": "ml_model_unavailable", "samples": 0}

        ordered_matches = sorted(
            (
                match for match in matches
                if getattr(match, "home_score", None) is not None and getattr(match, "away_score", None) is not None
            ),
            key=lambda match: (match.match_date, match.id),
        )
        if len(ordered_matches) < min_samples:
            return {"status": "insufficient_data", "samples": len(ordered_matches)}

        replay_memory = ProphetMemory()
        replay_learner = AdaptiveLearner(initial_weights=dict(self._learner.model_weights))
        replay_ensemble = EnsemblePredictor(
            replay_memory,
            replay_learner,
            k_factor=self._k_factor,
            form_window=self._form_window,
            form_decay=self._form_decay,
        )
        replay_ml = replay_ensemble.models.get("ml")
        elo_model = replay_ensemble.models.get("elo")
        if not isinstance(replay_ml, MLModel):
            return {"status": "ml_model_unavailable", "samples": 0}

        X: list[list[float]] = []
        y: list[int] = []
        label_map = {"AWAY": 0, "DRAW": 1, "HOME": 2}

        for match in ordered_matches:
            X.append(replay_ml.extract_features(match.home_team_id, match.away_team_id, match.league_code))
            y.append(label_map.get(match.result or "DRAW", 1))

            replay_memory.update_after_match(
                match.home_team_id,
                match.away_team_id,
                match.home_score,
                match.away_score,
                match.league_code,
            )

            if isinstance(elo_model, ELORatingModel):
                elo_model.update_ratings(
                    match.home_team_id,
                    match.away_team_id,
                    match.home_score,
                    match.away_score,
                )

        return ml_model.train(X=np.array(X, dtype=float), y=np.array(y, dtype=int))

    @property
    def models(self) -> dict[str, PredictionModel]:
        return self._models

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._learner.model_weights)

    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        league_code: str,
        **context,
    ) -> PredictionResult:
        """Generate ensemble prediction by combining all models."""
        model_results: dict[str, PredictionResult] = {}
        weights = self._learner.model_weights

        # Collect predictions from each model
        for name, model in self._models.items():
            if not model.is_ready():
                continue
            try:
                result = model.predict(home_team_id, away_team_id, league_code, **context)
                model_results[name] = result
            except Exception:
                continue

        if not model_results:
            return PredictionResult(
                model_name="ensemble",
                details={"error": "no_models_ready"},
            )

        # Weighted combination
        total_weight = 0.0
        home_prob = 0.0
        draw_prob = 0.0
        away_prob = 0.0
        pred_home_goals = 0.0
        pred_away_goals = 0.0
        over_25 = 0.0
        btts = 0.0

        for name, result in model_results.items():
            w = weights.get(name, 0.1)
            total_weight += w
            home_prob += result.home_win_prob * w
            draw_prob += result.draw_prob * w
            away_prob += result.away_win_prob * w
            pred_home_goals += result.predicted_home_goals * w
            pred_away_goals += result.predicted_away_goals * w
            over_25 += result.over_25_prob * w
            btts += result.btts_prob * w

        if total_weight > 0:
            home_prob /= total_weight
            draw_prob /= total_weight
            away_prob /= total_weight
            pred_home_goals /= total_weight
            pred_away_goals /= total_weight
            over_25 /= total_weight
            btts /= total_weight

        # Most likely score (mode across models)
        score_votes: dict[str, int] = {}
        for result in model_results.values():
            s = result.most_likely_score
            score_votes[s] = score_votes.get(s, 0) + 1
        most_likely = max(score_votes, key=score_votes.get) if score_votes else f"{round(pred_home_goals)}-{round(pred_away_goals)}"

        # Confidence: weighted average of model confidences + agreement bonus
        conf_sum = sum(r.confidence * weights.get(n, 0.1) for n, r in model_results.items())
        conf_weight = sum(weights.get(n, 0.1) for n in model_results)
        base_confidence = conf_sum / conf_weight if conf_weight > 0 else 0.3

        # Agreement bonus: if models agree on outcome, boost confidence
        outcomes = [r.predicted_outcome for r in model_results.values()]
        agreement = max(outcomes.count(o) for o in set(outcomes)) / len(outcomes)
        confidence = base_confidence * 0.7 + agreement * 0.3
        confidence = min(0.95, max(0.1, confidence))

        # Build model breakdown for learning
        model_breakdown = {}
        for name, result in model_results.items():
            model_breakdown[name] = {
                "home": result.home_win_prob,
                "draw": result.draw_prob,
                "away": result.away_win_prob,
                "predicted_outcome": result.predicted_outcome,
                "confidence": result.confidence,
            }

        ensemble_result = PredictionResult(
            home_win_prob=home_prob,
            draw_prob=draw_prob,
            away_win_prob=away_prob,
            predicted_home_goals=pred_home_goals,
            predicted_away_goals=pred_away_goals,
            most_likely_score=most_likely,
            over_25_prob=over_25,
            btts_prob=btts,
            confidence=confidence,
            model_name="ensemble",
            details={
                "weights": {k: round(v, 3) for k, v in weights.items()},
                "model_breakdown": model_breakdown,
                "models_used": list(model_results.keys()),
                "agreement": round(agreement, 2),
            },
        )
        ensemble_result.normalize_probs()
        return ensemble_result

    def record_result(
        self,
        home_team_id: int,
        away_team_id: int,
        home_score: int,
        away_score: int,
        prediction: PredictionResult,
    ) -> dict[str, float]:
        """
        Record match result for learning.
        Updates ELO ratings and brain weights.
        """
        # Determine actual outcome
        if home_score > away_score:
            outcome = "HOME"
        elif home_score < away_score:
            outcome = "AWAY"
        else:
            outcome = "DRAW"

        # Update ELO
        elo_model = self._models.get("elo")
        if isinstance(elo_model, ELORatingModel):
            elo_model.update_ratings(home_team_id, away_team_id, home_score, away_score)

        # Determine per-model correctness
        breakdown = prediction.details.get("model_breakdown", {})
        for name, data in breakdown.items():
            data["correct"] = data.get("predicted_outcome") == outcome

        # Feed to learner
        predicted = {
            "home_prob": prediction.home_win_prob,
            "draw_prob": prediction.draw_prob,
            "away_prob": prediction.away_win_prob,
        }
        new_weights = self._learner.record_prediction_result(predicted, outcome, breakdown)
        return new_weights
