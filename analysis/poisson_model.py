"""Dixon-Coles Poisson model for score prediction."""

from __future__ import annotations

import numpy as np
from scipy.stats import poisson

from brain.memory import ProphetMemory
from .base import PredictionModel, PredictionResult


class PoissonModel(PredictionModel):
    """
    Dixon-Coles inspired Poisson model.

    λ_home = attack_home × defense_away × home_advantage × league_avg_home_goals
    λ_away = attack_away × defense_home × league_avg_away_goals

    Produces a score probability matrix (0-0 to max_goals-max_goals).
    """

    MAX_GOALS = 6
    HOME_ADVANTAGE = 1.25  # Default home advantage factor

    def __init__(self, memory: ProphetMemory):
        self._memory = memory

    @property
    def name(self) -> str:
        return "poisson"

    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        league_code: str,
        **context,
    ) -> PredictionResult:
        home_profile = self._memory.get_team_profile(home_team_id)
        away_profile = self._memory.get_team_profile(away_team_id)
        league_avg = self._memory.get_league_avg(league_code)

        # Calculate expected goals
        lambda_home = (
            home_profile.attack_strength
            * away_profile.defense_strength
            * self.HOME_ADVANTAGE
            * league_avg.avg_home_goals
        )
        lambda_away = (
            away_profile.attack_strength
            * home_profile.defense_strength
            * league_avg.avg_away_goals
        )

        # Clamp to reasonable range
        lambda_home = max(0.3, min(lambda_home, 5.0))
        lambda_away = max(0.2, min(lambda_away, 4.5))

        # Score probability matrix
        score_matrix = self._build_score_matrix(lambda_home, lambda_away)

        # Apply Dixon-Coles low-score correction
        score_matrix = self._dixon_coles_correction(score_matrix, lambda_home, lambda_away)

        # Derive probabilities
        home_win_prob = 0.0
        draw_prob = 0.0
        away_win_prob = 0.0
        over_25_prob = 0.0
        btts_prob = 0.0

        most_likely_score = "1-1"
        max_prob = 0.0

        for i in range(self.MAX_GOALS + 1):
            for j in range(self.MAX_GOALS + 1):
                p = score_matrix[i][j]
                if i > j:
                    home_win_prob += p
                elif i < j:
                    away_win_prob += p
                else:
                    draw_prob += p

                if i + j > 2:
                    over_25_prob += p
                if i > 0 and j > 0:
                    btts_prob += p

                if p > max_prob:
                    max_prob = p
                    most_likely_score = f"{i}-{j}"

        # Confidence based on how decisive the prediction is
        probs = sorted([home_win_prob, draw_prob, away_win_prob], reverse=True)
        confidence = probs[0] - probs[1]  # Gap between top two
        confidence = min(0.95, max(0.1, confidence + 0.3))

        result = PredictionResult(
            home_win_prob=home_win_prob,
            draw_prob=draw_prob,
            away_win_prob=away_win_prob,
            predicted_home_goals=lambda_home,
            predicted_away_goals=lambda_away,
            most_likely_score=most_likely_score,
            over_25_prob=over_25_prob,
            btts_prob=btts_prob,
            confidence=confidence,
            model_name=self.name,
            details={
                "lambda_home": round(lambda_home, 3),
                "lambda_away": round(lambda_away, 3),
                "score_matrix_top": self._top_scores(score_matrix, 5),
            },
        )
        result.normalize_probs()
        return result

    def _build_score_matrix(self, lh: float, la: float) -> list[list[float]]:
        matrix = []
        for i in range(self.MAX_GOALS + 1):
            row = []
            for j in range(self.MAX_GOALS + 1):
                p = poisson.pmf(i, lh) * poisson.pmf(j, la)
                row.append(p)
            matrix.append(row)
        return matrix

    def _dixon_coles_correction(
        self, matrix: list[list[float]], lh: float, la: float, rho: float = -0.1
    ) -> list[list[float]]:
        """
        Dixon-Coles correction for low-scoring matches.
        Adjusts probabilities for 0-0, 1-0, 0-1, 1-1 scores.
        """
        if len(matrix) < 2 or len(matrix[0]) < 2:
            return matrix

        # Correction factor
        matrix[0][0] *= max(0, 1.0 - lh * la * rho)
        matrix[1][0] *= max(0, 1.0 + la * rho)
        matrix[0][1] *= max(0, 1.0 + lh * rho)
        matrix[1][1] *= max(0, 1.0 - rho)

        # Re-normalize
        total = sum(sum(row) for row in matrix)
        if total > 0:
            for i in range(len(matrix)):
                for j in range(len(matrix[i])):
                    matrix[i][j] /= total

        return matrix

    def _top_scores(self, matrix: list[list[float]], n: int) -> list[dict]:
        scores = []
        for i in range(len(matrix)):
            for j in range(len(matrix[i])):
                scores.append({"score": f"{i}-{j}", "prob": round(matrix[i][j], 4)})
        scores.sort(key=lambda x: x["prob"], reverse=True)
        return scores[:n]

    def is_ready(self) -> bool:
        return len(self._memory.team_profiles) >= 2
