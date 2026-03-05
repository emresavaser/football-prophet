"""ProphetState - Runtime state tracking for Football Prophet."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ModelHealth:
    accuracy: float = 0.0
    total_predictions: int = 0
    correct_predictions: int = 0
    last_error: Optional[str] = None
    streak: int = 0  # Positive = correct streak, negative = wrong streak

    def record_result(self, correct: bool) -> None:
        self.total_predictions += 1
        if correct:
            self.correct_predictions += 1
            self.streak = max(1, self.streak + 1)
        else:
            self.streak = min(-1, self.streak - 1)
        if self.total_predictions > 0:
            self.accuracy = self.correct_predictions / self.total_predictions

    def to_dict(self) -> dict:
        return {
            "accuracy": self.accuracy,
            "total": self.total_predictions,
            "correct": self.correct_predictions,
            "last_error": self.last_error,
            "streak": self.streak,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ModelHealth:
        return cls(
            accuracy=d.get("accuracy", 0.0),
            total_predictions=d.get("total", 0),
            correct_predictions=d.get("correct", 0),
            last_error=d.get("last_error"),
            streak=d.get("streak", 0),
        )


@dataclass
class ScanStats:
    matches_scanned: int = 0
    predictions_made: int = 0
    value_bets_found: int = 0
    errors: int = 0
    last_scan_ts: float = 0.0

    def record_scan(self, matches: int = 0, predictions: int = 0, value_bets: int = 0) -> None:
        self.matches_scanned += matches
        self.predictions_made += predictions
        self.value_bets_found += value_bets
        self.last_scan_ts = time.time()

    def to_dict(self) -> dict:
        return {
            "matches_scanned": self.matches_scanned,
            "predictions_made": self.predictions_made,
            "value_bets_found": self.value_bets_found,
            "errors": self.errors,
            "last_scan_ts": self.last_scan_ts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ScanStats:
        return cls(**{k: d[k] for k in d if k in cls.__dataclass_fields__})


class ProphetState:
    """
    Runtime state for Football Prophet.
    Tracks active predictions, model health, and scan statistics.
    """

    def __init__(self):
        self.active_predictions: dict[int, dict] = {}  # match_id → prediction data
        self.model_health: dict[str, ModelHealth] = {
            "poisson": ModelHealth(),
            "elo": ModelHealth(),
            "form": ModelHealth(),
            "h2h": ModelHealth(),
            "ml": ModelHealth(),
            "ensemble": ModelHealth(),
        }
        self.scan_stats = ScanStats()
        self.last_save_ts: float = 0.0
        self._start_ts: float = time.time()

    @property
    def uptime(self) -> float:
        return time.time() - self._start_ts

    def add_prediction(self, match_id: int, prediction: dict) -> None:
        self.active_predictions[match_id] = prediction

    def remove_prediction(self, match_id: int) -> None:
        self.active_predictions.pop(match_id, None)

    def record_model_result(self, model_name: str, correct: bool) -> None:
        if model_name in self.model_health:
            self.model_health[model_name].record_result(correct)

    def record_model_error(self, model_name: str, error: str) -> None:
        if model_name in self.model_health:
            self.model_health[model_name].last_error = error

    def to_dict(self) -> dict:
        return {
            "active_predictions": self.active_predictions,
            "model_health": {k: v.to_dict() for k, v in self.model_health.items()},
            "scan_stats": self.scan_stats.to_dict(),
            "last_save_ts": self.last_save_ts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ProphetState:
        state = cls()
        state.active_predictions = d.get("active_predictions", {})
        for name, health_dict in d.get("model_health", {}).items():
            state.model_health[name] = ModelHealth.from_dict(health_dict)
        state.scan_stats = ScanStats.from_dict(d.get("scan_stats", {}))
        state.last_save_ts = d.get("last_save_ts", 0.0)
        return state
