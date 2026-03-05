"""Backtesting engine for historical data evaluation.

Integrates DrawdownGuard, slippage simulation, Monte Carlo ruin analysis,
and vig-removed fair probability edge calculation.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

import numpy as np

from analysis.ensemble import EnsemblePredictor
from brain.memory import ProphetMemory
from brain.learning import AdaptiveLearner
from data.database import DatabaseManager
from odds.calculator import EVCalculator
from risk.kelly import DrawdownGuard, KellyQuarterPolicy, get_staking_policy
from risk.monte_carlo import simulate_ruin_probability
from market.slippage import simulate_fill_odds
from utils.logging import get_logger

log = get_logger(__name__)


class BacktestEngine:
    """
    Runs backtests on historical match data.
    Now with DrawdownGuard, max stake cap, bankroll floor,
    slippage simulation, and Monte Carlo ruin analysis.
    """

    def __init__(
        self,
        db: DatabaseManager,
        memory: ProphetMemory,
        min_edge: float = 0.05,
        kelly_fraction: float = 0.25,
        bankroll: float = 1000.0,
        vig_method: str = "shin",
        # Risk parameters
        drawdown_soft: float = 0.10,
        drawdown_hard: float = 0.25,
        max_stake_fraction: float = 0.05,
        staking_policy: str = "kelly_quarter",
        bankroll_floor: float = 1.0,
        slippage_enabled: bool = False,
    ):
        self._db = db
        self._memory = memory
        self._min_edge = min_edge
        self._kelly_fraction = kelly_fraction
        self._initial_bankroll = bankroll
        self._vig_method = vig_method
        self._drawdown_soft = drawdown_soft
        self._drawdown_hard = drawdown_hard
        self._max_stake_fraction = max_stake_fraction
        self._staking_policy_name = staking_policy
        self._bankroll_floor = bankroll_floor
        self._slippage_enabled = slippage_enabled

    async def run_backtest(
        self,
        league_code: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        season: Optional[str] = None,
    ) -> dict:
        """Run backtest with risk management integration."""
        run_id = str(uuid.uuid4())[:8]

        # Fetch finished matches
        matches = await self._db.get_league_matches(
            league_code, season=season, finished_only=True
        )

        if date_from:
            matches = [m for m in matches if m.match_date >= date_from]
        if date_to:
            matches = [m for m in matches if m.match_date <= date_to]

        if not matches:
            return {"run_id": run_id, "error": "no_matches_found", "total_matches": 0}

        # Create fresh memory and learner for backtest
        bt_memory = ProphetMemory()
        bt_learner = AdaptiveLearner()
        bt_ensemble = EnsemblePredictor(bt_memory, bt_learner)
        ev_calc = EVCalculator(
            kelly_fraction=self._kelly_fraction,
            vig_method=self._vig_method,
        )

        # Initialize DrawdownGuard
        guard = DrawdownGuard(
            soft_threshold=self._drawdown_soft,
            hard_limit=self._drawdown_hard,
            initial_bankroll=self._initial_bankroll,
        )

        # Results tracking
        results = {
            "run_id": run_id,
            "league_code": league_code,
            "date_from": str(date_from) if date_from else str(matches[0].match_date),
            "date_to": str(date_to) if date_to else str(matches[-1].match_date),
            "total_matches": 0,
            "predicted_matches": 0,
            "correct_predictions": 0,
            "accuracy": 0.0,
            "brier_scores": [],
            "value_bets": 0,
            "winning_bets": 0,
            "bankroll_history": [self._initial_bankroll],
            "roi": 0.0,
            "profit_loss": 0.0,
            "model_weights_final": {},
            "per_matchday": [],
            # Drawdown tracking
            "max_drawdown": 0.0,
            "drawdown_halts": 0,
            "guard_states": [],
            # MC results (populated after backtest)
            "monte_carlo": None,
            # Slippage tracking
            "slippage_stats": None,
            # Bet data for MC
            "_bet_probs": [],
            "_bet_odds": [],
        }

        bankroll = self._initial_bankroll
        max_dd = 0.0
        warmup = min(30, len(matches) // 3)
        fill_results = []

        for i, match in enumerate(matches):
            results["total_matches"] += 1

            if match.home_score is None or match.away_score is None:
                continue

            home_id = match.home_team_id
            away_id = match.away_team_id

            # After warmup, start making predictions
            if i >= warmup:
                try:
                    prediction = bt_ensemble.predict(home_id, away_id, league_code)

                    # Determine correctness
                    actual = match.result
                    predicted = prediction.predicted_outcome
                    is_correct = predicted == actual

                    results["predicted_matches"] += 1
                    if is_correct:
                        results["correct_predictions"] += 1

                    # Brier score
                    brier = (
                        (prediction.home_win_prob - (1 if actual == "HOME" else 0)) ** 2
                        + (prediction.draw_prob - (1 if actual == "DRAW" else 0)) ** 2
                        + (prediction.away_win_prob - (1 if actual == "AWAY" else 0)) ** 2
                    )
                    results["brier_scores"].append(brier)

                    # Simulate value betting with odds if available
                    odds = await self._db.get_latest_odds(match.id)
                    if odds and odds.home_win and odds.draw and odds.away_win:
                        ev_results = ev_calc.evaluate_match(
                            prediction.home_win_prob, prediction.draw_prob, prediction.away_win_prob,
                            odds.home_win, odds.draw, odds.away_win,
                            min_edge=self._min_edge,
                        )
                        for ev_r in ev_results:
                            if ev_r.is_value:
                                results["value_bets"] += 1

                                # Check bankroll floor
                                if bankroll <= self._bankroll_floor:
                                    continue

                                # Get drawdown multiplier
                                dd_multiplier = guard.stake_multiplier()
                                if dd_multiplier <= 0.0:
                                    results["drawdown_halts"] += 1
                                    continue

                                # Calculate stake with Kelly
                                raw_stake_frac = ev_r.kelly_stake
                                # Apply max stake cap
                                capped_frac = min(raw_stake_frac, self._max_stake_fraction)
                                stake = bankroll * capped_frac * dd_multiplier

                                # Apply slippage if enabled
                                effective_odds = ev_r.odds
                                if self._slippage_enabled:
                                    fill = simulate_fill_odds(
                                        offered_odds=ev_r.odds,
                                        market=ev_r.market,
                                        match_id=str(match.id),
                                        minute=0,
                                    )
                                    fill_results.append(fill)
                                    if not fill.filled:
                                        continue
                                    effective_odds = fill.fill_odds

                                # Store bet data for MC simulation
                                results["_bet_probs"].append(ev_r.model_prob)
                                results["_bet_odds"].append(effective_odds)

                                # Determine if bet won
                                bet_won = False
                                if ev_r.market == "home_win" and actual == "HOME":
                                    bet_won = True
                                elif ev_r.market == "draw" and actual == "DRAW":
                                    bet_won = True
                                elif ev_r.market == "away_win" and actual == "AWAY":
                                    bet_won = True

                                if bet_won:
                                    results["winning_bets"] += 1
                                    bankroll += stake * (effective_odds - 1)
                                else:
                                    bankroll -= stake

                                # Update guard
                                guard.update(bankroll)
                                dd = guard.current_drawdown()
                                if dd > max_dd:
                                    max_dd = dd

                                results["bankroll_history"].append(round(bankroll, 2))

                    # Feed result to ensemble for learning
                    bt_ensemble.record_result(
                        home_id, away_id,
                        match.home_score, match.away_score,
                        prediction,
                    )

                except Exception as e:
                    log.warning("backtest_prediction_error", match_id=match.id, error=str(e))

            # Always update memory (even during warmup)
            bt_memory.update_after_match(
                home_id, away_id,
                match.home_score, match.away_score,
                league_code,
            )

        # Final stats
        if results["predicted_matches"] > 0:
            results["accuracy"] = results["correct_predictions"] / results["predicted_matches"]
        if results["brier_scores"]:
            results["avg_brier_score"] = sum(results["brier_scores"]) / len(results["brier_scores"])
        else:
            results["avg_brier_score"] = 0.0

        results["profit_loss"] = bankroll - self._initial_bankroll
        results["roi"] = results["profit_loss"] / self._initial_bankroll if self._initial_bankroll > 0 else 0
        results["final_bankroll"] = round(bankroll, 2)
        results["model_weights_final"] = dict(bt_learner.model_weights)
        results["max_drawdown"] = round(max_dd, 4)

        # Guard final state
        results["guard_final"] = guard.guard_state()

        # Slippage stats
        if self._slippage_enabled and fill_results:
            from market.slippage import compute_slippage_metrics
            results["slippage_stats"] = compute_slippage_metrics(fill_results)

        # Monte Carlo ruin simulation
        bet_probs = results.pop("_bet_probs")
        bet_odds = results.pop("_bet_odds")
        if len(bet_probs) >= 5:
            try:
                policy = KellyQuarterPolicy(f_max=self._max_stake_fraction)
                mc_guard = DrawdownGuard(
                    soft_threshold=self._drawdown_soft,
                    hard_limit=self._drawdown_hard,
                    initial_bankroll=self._initial_bankroll,
                )
                mc_results = simulate_ruin_probability(
                    model_probs=np.array(bet_probs),
                    decimal_odds=np.array(bet_odds),
                    policy=policy,
                    guard=mc_guard,
                    initial_bankroll=self._initial_bankroll,
                    n_paths=2_000,
                )
                results["monte_carlo"] = mc_results
            except Exception as e:
                log.warning("monte_carlo_error", error=str(e))

        # Store result in DB
        await self._db.save_backtest_result(
            run_id=run_id,
            league_code=league_code,
            date_from=date_from or (matches[0].match_date if matches else None),
            date_to=date_to or (matches[-1].match_date if matches else None),
            total_matches=results["total_matches"],
            correct_predictions=results["correct_predictions"],
            accuracy=results["accuracy"],
            total_bets=results["value_bets"],
            winning_bets=results["winning_bets"],
            roi=results["roi"],
            profit_loss=results["profit_loss"],
            avg_brier_score=results["avg_brier_score"],
            avg_confidence=0.0,
            avg_edge=0.0,
            model_weights_used=json.dumps(results["model_weights_final"]),
        )

        # Clean up large data for return — keep up to 500 entries
        del results["brier_scores"]
        results["bankroll_history"] = results["bankroll_history"][-500:]

        log.info(
            "backtest_complete",
            run_id=run_id,
            matches=results["total_matches"],
            accuracy=round(results["accuracy"], 4),
            roi=round(results["roi"], 4),
            max_drawdown=results["max_drawdown"],
        )

        return results
