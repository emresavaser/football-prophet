"""Abstract base for prediction models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PredictionResult:
    """Standardized output from any prediction model."""
    home_win_prob: float = 0.33
    draw_prob: float = 0.34
    away_win_prob: float = 0.33

    predicted_home_goals: float = 1.0
    predicted_away_goals: float = 1.0
    most_likely_score: str = "1-1"

    over_25_prob: float = 0.5
    btts_prob: float = 0.5

    confidence: float = 0.5
    model_name: str = ""
    details: dict = field(default_factory=dict)

    @property
    def predicted_outcome(self) -> str:
        probs = {
            "HOME": self.home_win_prob,
            "DRAW": self.draw_prob,
            "AWAY": self.away_win_prob,
        }
        return max(probs, key=probs.get)

    def normalize_probs(self) -> None:
        total = self.home_win_prob + self.draw_prob + self.away_win_prob
        if total > 0:
            self.home_win_prob /= total
            self.draw_prob /= total
            self.away_win_prob /= total


class PredictionModel(ABC):
    """Abstract prediction model interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        league_code: str,
        **context,
    ) -> PredictionResult:
        ...

    def is_ready(self) -> bool:
        """Check if model has enough data to make predictions."""
        return True
