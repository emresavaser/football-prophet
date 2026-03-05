"""Performance momentum / trend calculation."""

from __future__ import annotations

from brain.memory import ProphetMemory


class MomentumCalculator:
    """
    Calculates short-term momentum based on last 5 matches.
    Outputs: "strong_up", "up", "neutral", "down", "strong_down"
    """

    def __init__(self, memory: ProphetMemory):
        self._memory = memory

    def get_momentum(self, team_id: int) -> dict:
        profile = self._memory.get_team_profile(team_id)
        results = profile.last_5_results[-5:]

        if len(results) < 3:
            return {"momentum": "neutral", "score": 0.5, "direction": 0}

        points = [3.0 if r == "W" else 1.0 if r == "D" else 0.0 for r in results]

        # Weighted average (more recent = higher weight)
        weights = [0.1, 0.15, 0.2, 0.25, 0.3]
        if len(points) < 5:
            weights = weights[-len(points):]
            total_w = sum(weights)
            weights = [w / total_w for w in weights]

        score = sum(p * w for p, w in zip(points, weights)) / 3.0  # Normalize to 0-1

        # Trend direction (comparing first half vs second half)
        mid = len(points) // 2
        first_half = sum(points[:mid]) / max(mid, 1)
        second_half = sum(points[mid:]) / max(len(points) - mid, 1)
        direction = second_half - first_half  # Positive = improving

        if score >= 0.8:
            label = "strong_up"
        elif score >= 0.6:
            label = "up"
        elif score >= 0.4:
            label = "neutral"
        elif score >= 0.2:
            label = "down"
        else:
            label = "strong_down"

        return {
            "momentum": label,
            "score": round(score, 3),
            "direction": round(direction, 3),
            "last_5": results,
        }

    def get_momentum_diff(self, home_id: int, away_id: int) -> float:
        """Returns momentum difference (positive = home momentum advantage)."""
        home = self.get_momentum(home_id)
        away = self.get_momentum(away_id)
        return home["score"] - away["score"]
