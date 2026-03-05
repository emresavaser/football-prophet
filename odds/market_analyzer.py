"""Market efficiency and odds movement analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class MarketAnalysis:
    bookmaker_margin: float
    market_efficiency: str   # "efficient", "moderate", "inefficient"
    odds_movement: str       # "shortening", "stable", "drifting"
    sharp_money_signal: bool


class MarketAnalyzer:
    """
    Analyzes betting market efficiency and odds movements.
    Detects bookmaker margin, market efficiency, and sharp money signals.
    """

    @staticmethod
    def calculate_margin(home_odds: float, draw_odds: float, away_odds: float) -> float:
        """Calculate bookmaker overround/margin."""
        if not all([home_odds, draw_odds, away_odds]):
            return 0.0
        return (1/home_odds + 1/draw_odds + 1/away_odds) - 1.0

    @staticmethod
    def remove_margin(
        home_odds: float, draw_odds: float, away_odds: float
    ) -> tuple[float, float, float]:
        """Convert odds to fair (margin-free) probabilities."""
        total_implied = 1/home_odds + 1/draw_odds + 1/away_odds
        if total_implied == 0:
            return 0.33, 0.34, 0.33
        return (
            (1/home_odds) / total_implied,
            (1/draw_odds) / total_implied,
            (1/away_odds) / total_implied,
        )

    def analyze_market(
        self,
        current_odds: dict,   # {home_win, draw, away_win}
        opening_odds: Optional[dict] = None,  # Same structure, earlier snapshot
    ) -> MarketAnalysis:
        """Full market analysis for a match."""
        h, d, a = current_odds.get("home_win", 0), current_odds.get("draw", 0), current_odds.get("away_win", 0)

        margin = self.calculate_margin(h, d, a) if all([h, d, a]) else 0.0

        # Market efficiency assessment
        if margin < 0.03:
            efficiency = "efficient"
        elif margin < 0.08:
            efficiency = "moderate"
        else:
            efficiency = "inefficient"

        # Odds movement analysis
        movement = "stable"
        sharp_signal = False
        if opening_odds:
            oh = opening_odds.get("home_win", h)
            od = opening_odds.get("draw", d)
            oa = opening_odds.get("away_win", a)

            if h and oh:
                home_change = (h - oh) / oh if oh else 0
                away_change = (a - oa) / oa if oa else 0

                if home_change < -0.05:
                    movement = "shortening"  # Home odds dropping = money on home
                    if home_change < -0.10:
                        sharp_signal = True
                elif home_change > 0.05:
                    movement = "drifting"    # Home odds rising

        return MarketAnalysis(
            bookmaker_margin=round(margin, 4),
            market_efficiency=efficiency,
            odds_movement=movement,
            sharp_money_signal=sharp_signal,
        )

    @staticmethod
    def odds_to_probability(decimal_odds: float) -> float:
        return 1.0 / decimal_odds if decimal_odds > 0 else 0.0

    @staticmethod
    def probability_to_odds(prob: float) -> float:
        return 1.0 / prob if prob > 0 else 0.0
