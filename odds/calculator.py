"""Expected Value and Kelly Criterion calculations with vig removal support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .vig_removal import fair_probabilities, fair_probabilities_2way


@dataclass
class EVResult:
    market: str              # "home_win", "draw", "away_win", "over_25", etc.
    model_prob: float        # Our estimated probability
    implied_prob: float      # Bookmaker implied probability (raw, with vig)
    fair_prob: float         # Vig-removed fair probability
    overround: float         # Market overround (e.g. 1.05 = 5% margin)
    odds: float              # Decimal odds
    ev: float                # Expected value
    edge: float              # Edge over fair probability (model_prob - fair_prob)
    kelly_stake: float       # Recommended stake (fraction of bankroll)
    is_value: bool           # EV > 0 and meets criteria


class EVCalculator:
    """
    Calculates Expected Value, implied probability, and Kelly Criterion stakes.
    Now with vig removal: edge = model_prob - fair_prob (not implied_prob).
    """

    def __init__(self, kelly_fraction: float = 0.25, vig_method: str = "shin"):
        self._kelly_fraction = kelly_fraction
        self._vig_method = vig_method

    def calculate_ev(self, model_prob: float, decimal_odds: float) -> float:
        """Calculate expected value per unit stake."""
        return (model_prob * (decimal_odds - 1)) - (1 - model_prob)

    def implied_probability(self, decimal_odds: float) -> float:
        """Convert decimal odds to implied probability."""
        if decimal_odds <= 0:
            return 0.0
        return 1.0 / decimal_odds

    def kelly_stake(self, model_prob: float, decimal_odds: float) -> float:
        """Calculate Kelly Criterion stake as fraction of bankroll."""
        b = decimal_odds - 1
        p = model_prob
        q = 1 - p

        if b <= 0 or p <= 0:
            return 0.0

        kelly = (b * p - q) / b
        if kelly <= 0:
            return 0.0

        return kelly * self._kelly_fraction

    def evaluate_market(
        self,
        market: str,
        model_prob: float,
        decimal_odds: float,
        fair_prob: float = 0.0,
        overround_val: float = 1.0,
        min_edge: float = 0.05,
        min_odds: float = 1.30,
        max_odds: float = 10.0,
    ) -> EVResult:
        """Full evaluation of a single market.

        If fair_prob is provided (> 0), edge is calculated against it.
        Otherwise falls back to implied probability.
        """
        implied = self.implied_probability(decimal_odds)
        ev = self.calculate_ev(model_prob, decimal_odds)
        kelly = self.kelly_stake(model_prob, decimal_odds)

        # Use fair_prob for edge if available, otherwise implied
        effective_fair = fair_prob if fair_prob > 0 else implied
        edge = model_prob - effective_fair

        is_value = (
            ev > 0
            and edge >= min_edge
            and min_odds <= decimal_odds <= max_odds
        )

        return EVResult(
            market=market,
            model_prob=round(model_prob, 4),
            implied_prob=round(implied, 4),
            fair_prob=round(effective_fair, 4),
            overround=round(overround_val, 4),
            odds=decimal_odds,
            ev=round(ev, 4),
            edge=round(edge, 4),
            kelly_stake=round(kelly, 4),
            is_value=is_value,
        )

    def evaluate_match(
        self,
        home_prob: float,
        draw_prob: float,
        away_prob: float,
        home_odds: Optional[float],
        draw_odds: Optional[float],
        away_odds: Optional[float],
        over_25_prob: Optional[float] = None,
        over_25_odds: Optional[float] = None,
        under_25_odds: Optional[float] = None,
        btts_prob: Optional[float] = None,
        btts_yes_odds: Optional[float] = None,
        btts_no_odds: Optional[float] = None,
        **criteria,
    ) -> list[EVResult]:
        """Evaluate all markets for a match, with vig removal."""
        results = []
        min_edge = criteria.get("min_edge", 0.05)
        min_odds = criteria.get("min_odds", 1.30)
        max_odds = criteria.get("max_odds", 10.0)

        # Compute fair probabilities for 1X2 market using vig removal
        fair_home, fair_draw, fair_away, overround_3way = 0.0, 0.0, 0.0, 1.0
        if home_odds and draw_odds and away_odds:
            try:
                fair_home, fair_draw, fair_away, overround_3way = fair_probabilities(
                    home_odds, draw_odds, away_odds, method=self._vig_method
                )
            except Exception:
                # Fallback to implied if vig removal fails
                fair_home = self.implied_probability(home_odds)
                fair_draw = self.implied_probability(draw_odds)
                fair_away = self.implied_probability(away_odds)
                overround_3way = fair_home + fair_draw + fair_away

        markets = [
            ("home_win", home_prob, home_odds, fair_home, overround_3way),
            ("draw", draw_prob, draw_odds, fair_draw, overround_3way),
            ("away_win", away_prob, away_odds, fair_away, overround_3way),
        ]

        # Over/under 2.5 — 2-way vig removal
        if over_25_prob is not None and over_25_odds is not None and under_25_odds is not None:
            try:
                fair_over, fair_under, ov_ou = fair_probabilities_2way(
                    over_25_odds, under_25_odds, method=self._vig_method
                )
            except Exception:
                fair_over = self.implied_probability(over_25_odds)
                fair_under = self.implied_probability(under_25_odds)
                ov_ou = fair_over + fair_under
            markets.append(("over_25", over_25_prob, over_25_odds, fair_over, ov_ou))
            markets.append(("under_25", 1 - over_25_prob, under_25_odds, fair_under, ov_ou))
        else:
            if over_25_prob is not None and over_25_odds is not None:
                markets.append(("over_25", over_25_prob, over_25_odds, 0.0, 1.0))
            if over_25_prob is not None and under_25_odds is not None:
                markets.append(("under_25", 1 - over_25_prob, under_25_odds, 0.0, 1.0))

        # BTTS — 2-way vig removal
        if btts_prob is not None and btts_yes_odds is not None and btts_no_odds is not None:
            try:
                fair_yes, fair_no, ov_btts = fair_probabilities_2way(
                    btts_yes_odds, btts_no_odds, method=self._vig_method
                )
            except Exception:
                fair_yes = self.implied_probability(btts_yes_odds)
                fair_no = self.implied_probability(btts_no_odds)
                ov_btts = fair_yes + fair_no
            markets.append(("btts_yes", btts_prob, btts_yes_odds, fair_yes, ov_btts))
            markets.append(("btts_no", 1 - btts_prob, btts_no_odds, fair_no, ov_btts))
        else:
            if btts_prob is not None and btts_yes_odds is not None:
                markets.append(("btts_yes", btts_prob, btts_yes_odds, 0.0, 1.0))
            if btts_prob is not None and btts_no_odds is not None:
                markets.append(("btts_no", 1 - btts_prob, btts_no_odds, 0.0, 1.0))

        for market, prob, odds, fair_p, ov in markets:
            if odds is not None and prob is not None:
                results.append(
                    self.evaluate_market(
                        market, prob, odds,
                        fair_prob=fair_p,
                        overround_val=ov,
                        min_edge=min_edge,
                        min_odds=min_odds,
                        max_odds=max_odds,
                    )
                )

        return results
