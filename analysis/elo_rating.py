"""ELO rating system with goal-difference adjusted K-factor."""

from __future__ import annotations

import math

from brain.memory import ProphetMemory
from .base import PredictionModel, PredictionResult


class ELORatingModel(PredictionModel):
    """
    ELO-based prediction model.
    R_new = R_old + K * (actual - expected)
    K-factor adjusted by goal difference.
    """

    def __init__(
        self,
        memory: ProphetMemory,
        k_factor: float = 32.0,
        home_advantage: float = 65.0,
        initial_rating: float = 1500.0,
    ):
        self._memory = memory
        self._k_factor = k_factor
        self._home_advantage = home_advantage
        self._initial_rating = initial_rating

    @property
    def name(self) -> str:
        return "elo"

    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        league_code: str,
        **context,
    ) -> PredictionResult:
        home_profile = self._memory.get_team_profile(home_team_id)
        away_profile = self._memory.get_team_profile(away_team_id)

        home_elo = home_profile.elo_rating or self._initial_rating
        away_elo = away_profile.elo_rating or self._initial_rating

        # Expected scores with home advantage
        exp_home = self._expected_score(home_elo + self._home_advantage, away_elo)
        exp_away = 1.0 - exp_home

        # Convert to 1X2 probabilities
        # Draw probability: higher when teams are close in ELO, lower when gap is large
        elo_diff = abs((home_elo + self._home_advantage) - away_elo)
        draw_prob = max(0.12, 0.30 - elo_diff / 1200.0)

        home_win_prob = exp_home * (1.0 - draw_prob)
        away_win_prob = exp_away * (1.0 - draw_prob)

        # Estimate goals from ELO
        league_avg = self._memory.get_league_avg(league_code)
        strength_ratio = exp_home / exp_away if exp_away > 0 else 1.5
        total_goals = league_avg.avg_goals_per_match

        pred_home_goals = total_goals * strength_ratio / (1 + strength_ratio)
        pred_away_goals = total_goals / (1 + strength_ratio)

        # Confidence
        confidence = min(0.95, max(0.2, abs(exp_home - 0.5) * 2 + 0.2))

        result = PredictionResult(
            home_win_prob=home_win_prob,
            draw_prob=draw_prob,
            away_win_prob=away_win_prob,
            predicted_home_goals=pred_home_goals,
            predicted_away_goals=pred_away_goals,
            most_likely_score=f"{round(pred_home_goals)}-{round(pred_away_goals)}",
            confidence=confidence,
            model_name=self.name,
            details={
                "home_elo": round(home_elo, 1),
                "away_elo": round(away_elo, 1),
                "elo_diff": round(home_elo + self._home_advantage - away_elo, 1),
                "exp_home": round(exp_home, 4),
            },
        )
        result.normalize_probs()
        return result

    def update_ratings(
        self,
        home_team_id: int,
        away_team_id: int,
        home_score: int,
        away_score: int,
    ) -> tuple[float, float]:
        """
        Update ELO ratings after a match.
        Returns (new_home_elo, new_away_elo).
        """
        home_profile = self._memory.get_team_profile(home_team_id)
        away_profile = self._memory.get_team_profile(away_team_id)

        home_elo = home_profile.elo_rating or self._initial_rating
        away_elo = away_profile.elo_rating or self._initial_rating

        exp_home = self._expected_score(home_elo + self._home_advantage, away_elo)
        exp_away = 1.0 - exp_home

        # Actual result (1=win, 0.5=draw, 0=loss)
        if home_score > away_score:
            actual_home, actual_away = 1.0, 0.0
        elif home_score < away_score:
            actual_home, actual_away = 0.0, 1.0
        else:
            actual_home, actual_away = 0.5, 0.5

        # K-factor adjusted by goal difference
        goal_diff = abs(home_score - away_score)
        k = self._adjusted_k(goal_diff)

        new_home = home_elo + k * (actual_home - exp_home)
        new_away = away_elo + k * (actual_away - exp_away)

        home_profile.elo_rating = new_home
        away_profile.elo_rating = new_away

        return new_home, new_away

    @staticmethod
    def _expected_score(rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

    def _adjusted_k(self, goal_diff: int) -> float:
        """K-factor increases with goal difference."""
        if goal_diff <= 1:
            return self._k_factor
        elif goal_diff == 2:
            return self._k_factor * 1.5
        else:
            return self._k_factor * (1.75 + (goal_diff - 3) * 0.125)

    def is_ready(self) -> bool:
        return len(self._memory.team_profiles) >= 2
