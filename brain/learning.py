"""AdaptiveLearner - Learns from prediction results, adjusts model weights."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PredictionRecord:
    match_id: int = 0
    predicted_home_prob: float = 0.0
    predicted_draw_prob: float = 0.0
    predicted_away_prob: float = 0.0
    actual_outcome: str = ""  # "HOME", "DRAW", "AWAY"
    model_breakdown: dict = field(default_factory=dict)
    confidence: float = 0.0
    brier_score: float = 0.0


class AdaptiveLearner:
    """
    Learns from prediction vs actual results.
    Adjusts model weights: accurate model → weight up, inaccurate → weight down.

    Weight bounds: min=0.05, max=0.50
    After each adjustment, weights are normalized to sum to 1.0.
    """

    WEIGHT_UP = 0.03       # Faster convergence (was 0.02)
    WEIGHT_DOWN = 0.015    # Faster convergence (was 0.01)
    MIN_WEIGHT = 0.03      # Lower floor for weak models (was 0.05)
    MAX_WEIGHT = 0.55      # Higher ceiling for strong models (was 0.50)

    def __init__(self, initial_weights: Optional[dict[str, float]] = None):
        self.model_weights: dict[str, float] = initial_weights or {
            "poisson": 0.15,
            "elo": 0.30,
            "form": 0.25,
            "h2h": 0.05,
            "ml": 0.25,
        }
        self.prediction_history: list[dict] = []
        self.calibration_bins: dict[str, list[float]] = {
            f"{i/10:.1f}": [] for i in range(0, 11)
        }
        self.model_brier_scores: dict[str, list[float]] = {
            name: [] for name in self.model_weights
        }

    def record_prediction_result(
        self,
        predicted: dict,      # {home_prob, draw_prob, away_prob}
        actual_outcome: str,   # HOME, DRAW, AWAY
        model_breakdown: dict, # {model_name: {home, draw, away, correct: bool}}
    ) -> dict[str, float]:
        """
        Record a prediction result and adjust model weights.
        Returns updated weights.
        """
        # Calculate Brier score for ensemble
        outcome_vec = {"HOME": 0, "DRAW": 1, "AWAY": 2}
        probs = [predicted["home_prob"], predicted["draw_prob"], predicted["away_prob"]]
        actual_idx = outcome_vec.get(actual_outcome, 0)
        brier = sum(
            (p - (1.0 if i == actual_idx else 0.0)) ** 2
            for i, p in enumerate(probs)
        )

        # Record history
        self.prediction_history.append({
            "predicted": predicted,
            "actual": actual_outcome,
            "model_breakdown": model_breakdown,
            "brier": brier,
        })

        # Calibration tracking
        confidence = max(probs)
        bin_key = f"{min(int(confidence * 10), 10) / 10:.1f}"
        was_correct = probs.index(max(probs)) == actual_idx
        self.calibration_bins.setdefault(bin_key, []).append(1.0 if was_correct else 0.0)

        # Adjust weights per model
        for model_name, model_pred in model_breakdown.items():
            if model_name not in self.model_weights:
                continue

            model_correct = model_pred.get("correct", False)
            if model_correct:
                self.model_weights[model_name] = min(
                    self.MAX_WEIGHT,
                    self.model_weights[model_name] + self.WEIGHT_UP,
                )
            else:
                self.model_weights[model_name] = max(
                    self.MIN_WEIGHT,
                    self.model_weights[model_name] - self.WEIGHT_DOWN,
                )

            # Track per-model Brier score
            m_probs = [
                model_pred.get("home", 0.33),
                model_pred.get("draw", 0.33),
                model_pred.get("away", 0.33),
            ]
            m_brier = sum(
                (p - (1.0 if i == actual_idx else 0.0)) ** 2
                for i, p in enumerate(m_probs)
            )
            self.model_brier_scores.setdefault(model_name, []).append(m_brier)

        # Normalize weights to sum = 1.0
        self._normalize_weights()

        return dict(self.model_weights)

    def _normalize_weights(self) -> None:
        total = sum(self.model_weights.values())
        if total > 0:
            for k in self.model_weights:
                self.model_weights[k] /= total

    def get_calibration_curve(self) -> dict[str, float]:
        """Returns predicted confidence → actual accuracy mapping."""
        curve = {}
        for bin_key, outcomes in self.calibration_bins.items():
            if outcomes:
                curve[bin_key] = sum(outcomes) / len(outcomes)
        return curve

    def get_model_performance(self) -> dict[str, dict]:
        """Returns performance summary per model."""
        perf = {}
        for name, briers in self.model_brier_scores.items():
            if briers:
                perf[name] = {
                    "weight": self.model_weights.get(name, 0),
                    "avg_brier": sum(briers) / len(briers),
                    "total_predictions": len(briers),
                    "best_brier": min(briers),
                    "worst_brier": max(briers),
                }
        return perf

    @property
    def total_predictions(self) -> int:
        return len(self.prediction_history)

    @property
    def overall_brier(self) -> float:
        if not self.prediction_history:
            return 0.0
        return sum(p["brier"] for p in self.prediction_history) / len(self.prediction_history)

    def to_dict(self) -> dict:
        return {
            "model_weights": self.model_weights,
            "prediction_history": self.prediction_history[-500:],  # Keep last 500
            "calibration_bins": self.calibration_bins,
            "model_brier_scores": {
                k: v[-200:] for k, v in self.model_brier_scores.items()
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> AdaptiveLearner:
        learner = cls(initial_weights=d.get("model_weights"))
        learner.prediction_history = d.get("prediction_history", [])
        learner.calibration_bins = d.get("calibration_bins", {})
        learner.model_brier_scores = d.get("model_brier_scores", {})
        return learner
