"""Head-to-head match history analyzer."""

from __future__ import annotations

from brain.memory import ProphetMemory
from .base import PredictionModel, PredictionResult


class H2HAnalyzer(PredictionModel):
    """
    Analyzes historical head-to-head matchups between two teams.
    Uses H2H record + recent H2H goal patterns.
    """

    MIN_H2H_MATCHES = 3

    def __init__(self, memory: ProphetMemory):
        self._memory = memory

    @property
    def name(self) -> str:
        return "h2h"

    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        league_code: str,
        **context,
    ) -> PredictionResult:
        h2h = self._memory.get_h2h(home_team_id, away_team_id)

        if h2h.total_matches < self.MIN_H2H_MATCHES:
            # Not enough H2H data - return neutral prediction
            return PredictionResult(
                home_win_prob=0.40,
                draw_prob=0.25,
                away_win_prob=0.35,
                confidence=0.15,
                model_name=self.name,
                details={"h2h_matches": h2h.total_matches, "note": "insufficient_data"},
            )

        total = h2h.total_matches

        # Determine which team is team1/team2 in H2H profile
        if home_team_id == h2h.team1_id:
            home_h2h_wins = h2h.team1_wins
            away_h2h_wins = h2h.team2_wins
        else:
            home_h2h_wins = h2h.team2_wins
            away_h2h_wins = h2h.team1_wins

        # Raw probabilities from H2H record
        home_win_pct = home_h2h_wins / total
        draw_pct = h2h.draws / total
        away_win_pct = away_h2h_wins / total

        # Apply home advantage boost (slight)
        home_win_prob = home_win_pct * 1.05
        draw_prob = draw_pct
        away_win_prob = away_win_pct * 0.95

        # Normalize
        s = home_win_prob + draw_prob + away_win_prob
        if s > 0:
            home_win_prob /= s
            draw_prob /= s
            away_win_prob /= s

        # Goal estimates from H2H average
        avg_goals = h2h.avg_total_goals
        if home_win_prob > away_win_prob:
            pred_home = avg_goals * 0.55
            pred_away = avg_goals * 0.45
        elif away_win_prob > home_win_prob:
            pred_home = avg_goals * 0.45
            pred_away = avg_goals * 0.55
        else:
            pred_home = avg_goals * 0.5
            pred_away = avg_goals * 0.5

        # Confidence increases with more H2H matches
        confidence = min(0.7, 0.2 + h2h.total_matches * 0.05)

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
                "h2h_matches": total,
                "home_h2h_wins": home_h2h_wins,
                "away_h2h_wins": away_h2h_wins,
                "h2h_draws": h2h.draws,
                "avg_total_goals": round(avg_goals, 2),
            },
        )
        return result

    def is_ready(self) -> bool:
        return len(self._memory.h2h_cache) > 0
