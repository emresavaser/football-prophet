"""Form analyzer with exponential decay weighting."""

from __future__ import annotations

from typing import Sequence

from brain.memory import ProphetMemory
from .base import PredictionModel, PredictionResult


class FormAnalyzer(PredictionModel):
    """
    Recent form analysis with exponential decay.
    Last 10 matches, decay factor = 0.9 per match.
    Separate home/away form consideration.
    """

    def __init__(self, memory: ProphetMemory, window: int = 10, decay: float = 0.9):
        self._memory = memory
        self._window = window
        self._decay = decay

    @property
    def name(self) -> str:
        return "form"

    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        league_code: str,
        **context,
    ) -> PredictionResult:
        home_profile = self._memory.get_team_profile(home_team_id)
        away_profile = self._memory.get_team_profile(away_team_id)

        # Calculate form scores
        home_form = self._calc_form(home_profile.last_5_results)
        away_form = self._calc_form(away_profile.last_5_results)

        # Factor in home/away records
        home_home_strength = self._record_strength(home_profile.home_record)
        away_away_strength = self._record_strength(away_profile.away_record)

        # Combined form score (0-1 scale)
        home_combined = (home_form * 0.6 + home_home_strength * 0.4)
        away_combined = (away_form * 0.6 + away_away_strength * 0.4)

        # Convert to probabilities
        total = home_combined + away_combined
        if total == 0:
            home_win_prob = 0.40
            away_win_prob = 0.30
        else:
            home_win_prob = home_combined / total * 0.75  # Scale for draw allowance
            away_win_prob = away_combined / total * 0.75

        draw_prob = 1.0 - home_win_prob - away_win_prob
        draw_prob = max(0.15, min(0.35, draw_prob))

        # Rescale
        hw_aw = home_win_prob + away_win_prob
        if hw_aw > 0:
            scale = (1.0 - draw_prob) / hw_aw
            home_win_prob *= scale
            away_win_prob *= scale

        # Goal estimates from form
        league_avg = self._memory.get_league_avg(league_code)
        home_scoring_rate = home_profile.home_record.avg_goals_scored if home_profile.home_record.played > 0 else league_avg.avg_home_goals
        away_scoring_rate = away_profile.away_record.avg_goals_scored if away_profile.away_record.played > 0 else league_avg.avg_away_goals

        pred_home = home_scoring_rate * (0.7 + home_form * 0.6)
        pred_away = away_scoring_rate * (0.7 + away_form * 0.6)

        confidence = abs(home_combined - away_combined) * 0.5 + 0.25
        confidence = min(0.85, max(0.15, confidence))

        result = PredictionResult(
            home_win_prob=home_win_prob,
            draw_prob=draw_prob,
            away_win_prob=away_win_prob,
            predicted_home_goals=pred_home,
            predicted_away_goals=pred_away,
            most_likely_score=f"{round(pred_home)}-{round(pred_away)}",
            confidence=confidence,
            model_name=self.name,
            details={
                "home_form": round(home_form, 3),
                "away_form": round(away_form, 3),
                "home_trend": home_profile.trend,
                "away_trend": away_profile.trend,
            },
        )
        result.normalize_probs()
        return result

    def _calc_form(self, results: list[str]) -> float:
        """
        Calculate weighted form score using exponential decay.
        Returns 0-1 scale.
        """
        if not results:
            return 0.5

        points_map = {"W": 3.0, "D": 1.0, "L": 0.0}
        total_weight = 0.0
        weighted_points = 0.0

        for i, result in enumerate(reversed(results[-self._window:])):
            weight = self._decay ** i
            total_weight += weight
            weighted_points += points_map.get(result, 0) * weight

        if total_weight == 0:
            return 0.5

        return weighted_points / (total_weight * 3.0)  # Normalize to 0-1

    @staticmethod
    def _record_strength(record) -> float:
        """Convert W/D/L record to 0-1 strength."""
        if record.played == 0:
            return 0.5
        return record.points / (record.played * 3)

    def is_ready(self) -> bool:
        return any(
            len(p.last_5_results) >= 3
            for p in self._memory.team_profiles.values()
        )
