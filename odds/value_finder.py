"""Value bet detection by comparing model probabilities to market odds."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from analysis.base import PredictionResult
from .calculator import EVCalculator, EVResult


@dataclass
class ValueBet:
    match_id: int
    home_team: str
    away_team: str
    league_code: str
    market: str
    model_prob: float
    implied_prob: float
    fair_prob: float
    overround: float
    odds: float
    ev: float
    edge: float
    kelly_stake: float
    confidence: float
    prediction: Optional[PredictionResult] = None


class ValueFinder:
    """
    Finds value bets by comparing ensemble model probabilities
    against bookmaker odds.
    """

    def __init__(
        self,
        min_edge: float = 0.05,
        min_confidence: float = 0.55,
        min_odds: float = 1.30,
        max_odds: float = 10.0,
        kelly_fraction: float = 0.25,
        vig_method: str = "shin",
    ):
        self._calculator = EVCalculator(kelly_fraction=kelly_fraction, vig_method=vig_method)
        self._min_edge = min_edge
        self._min_confidence = min_confidence
        self._min_odds = min_odds
        self._max_odds = max_odds

    def find_value(
        self,
        match_id: int,
        home_team: str,
        away_team: str,
        league_code: str,
        prediction: PredictionResult,
        odds: dict,  # {home_win, draw, away_win, over_25, under_25, btts_yes, btts_no}
    ) -> list[ValueBet]:
        """Find value bets for a single match."""
        if prediction.confidence < self._min_confidence:
            return []

        ev_results = self._calculator.evaluate_match(
            home_prob=prediction.home_win_prob,
            draw_prob=prediction.draw_prob,
            away_prob=prediction.away_win_prob,
            home_odds=odds.get("home_win"),
            draw_odds=odds.get("draw"),
            away_odds=odds.get("away_win"),
            over_25_prob=prediction.over_25_prob,
            over_25_odds=odds.get("over_25"),
            under_25_odds=odds.get("under_25"),
            btts_prob=prediction.btts_prob,
            btts_yes_odds=odds.get("btts_yes"),
            btts_no_odds=odds.get("btts_no"),
            min_edge=self._min_edge,
            min_odds=self._min_odds,
            max_odds=self._max_odds,
        )

        value_bets = []
        for ev_r in ev_results:
            if ev_r.is_value:
                value_bets.append(ValueBet(
                    match_id=match_id,
                    home_team=home_team,
                    away_team=away_team,
                    league_code=league_code,
                    market=ev_r.market,
                    model_prob=ev_r.model_prob,
                    implied_prob=ev_r.implied_prob,
                    fair_prob=ev_r.fair_prob,
                    overround=ev_r.overround,
                    odds=ev_r.odds,
                    ev=ev_r.ev,
                    edge=ev_r.edge,
                    kelly_stake=ev_r.kelly_stake,
                    confidence=prediction.confidence,
                    prediction=prediction,
                ))

        # Sort by edge (highest first)
        value_bets.sort(key=lambda vb: vb.edge, reverse=True)
        return value_bets

    def find_value_batch(
        self,
        matches: list[dict],  # [{match_id, home_team, away_team, league_code, prediction, odds}]
    ) -> list[ValueBet]:
        """Find value bets across multiple matches."""
        all_value = []
        for m in matches:
            vbs = self.find_value(
                match_id=m["match_id"],
                home_team=m["home_team"],
                away_team=m["away_team"],
                league_code=m["league_code"],
                prediction=m["prediction"],
                odds=m["odds"],
            )
            all_value.extend(vbs)

        all_value.sort(key=lambda vb: vb.ev, reverse=True)
        return all_value
