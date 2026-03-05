"""Prediction lifecycle management: create → store → check result → notify brain."""

from __future__ import annotations

import json
from typing import Optional

from analysis.base import PredictionResult
from analysis.ensemble import EnsemblePredictor
from brain.memory import ProphetMemory
from brain.state import ProphetState
from data.database import DatabaseManager
from odds.value_finder import ValueFinder, ValueBet
from utils.logging import get_logger

log = get_logger(__name__)


class PredictionManager:
    """
    Manages the full prediction lifecycle:
    1. Generate prediction (ensemble)
    2. Compare with odds (find value)
    3. Store in database
    4. Track in brain state
    5. Check results when match finishes
    6. Feed results back to brain for learning
    """

    def __init__(
        self,
        db: DatabaseManager,
        ensemble: EnsemblePredictor,
        memory: ProphetMemory,
        state: ProphetState,
        value_finder: ValueFinder,
    ):
        self._db = db
        self._ensemble = ensemble
        self._memory = memory
        self._state = state
        self._value_finder = value_finder

    async def predict_match(
        self,
        match_id: int,
        home_team_id: int,
        away_team_id: int,
        league_code: str,
        odds: Optional[dict] = None,
        home_team_name: str = "",
        away_team_name: str = "",
    ) -> tuple[PredictionResult, list[ValueBet]]:
        """Generate and store prediction for a match."""
        # Generate ensemble prediction
        prediction = self._ensemble.predict(home_team_id, away_team_id, league_code)

        # Find value bets
        value_bets = []
        if odds:
            value_bets = self._value_finder.find_value(
                match_id=match_id,
                home_team=home_team_name,
                away_team=away_team_name,
                league_code=league_code,
                prediction=prediction,
                odds=odds,
            )

        # Store in database
        best_value = value_bets[0] if value_bets else None
        await self._db.save_prediction(
            match_id=match_id,
            home_win_prob=prediction.home_win_prob,
            draw_prob=prediction.draw_prob,
            away_win_prob=prediction.away_win_prob,
            predicted_home_goals=prediction.predicted_home_goals,
            predicted_away_goals=prediction.predicted_away_goals,
            most_likely_score=prediction.most_likely_score,
            over_25_prob=prediction.over_25_prob,
            btts_prob=prediction.btts_prob,
            confidence=prediction.confidence,
            model_breakdown=json.dumps(prediction.details.get("model_breakdown", {})),
            is_value_bet=len(value_bets) > 0,
            value_bet_market=best_value.market if best_value else None,
            edge=best_value.edge if best_value else None,
            kelly_stake=best_value.kelly_stake if best_value else None,
            ev=best_value.ev if best_value else None,
        )

        # Track in state
        self._state.add_prediction(match_id, {
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "league_code": league_code,
            "prediction": prediction.predicted_outcome,
            "confidence": prediction.confidence,
            "value_bets": len(value_bets),
        })

        self._state.scan_stats.record_scan(
            predictions=1,
            value_bets=len(value_bets),
        )

        log.info(
            "prediction_created",
            match_id=match_id,
            predicted=prediction.predicted_outcome,
            confidence=round(prediction.confidence, 3),
            score=prediction.most_likely_score,
            value_bets=len(value_bets),
        )

        return prediction, value_bets

    async def check_results(self) -> list[dict]:
        """
        Check pending predictions against actual results.
        Feeds results back to brain for learning.
        """
        processed = []
        pending = await self._db.get_pending_predictions()

        for pred in pending:
            match = await self._db.get_match(pred.match_id)
            if not match or match.status != "FINISHED" or match.home_score is None:
                continue

            # Determine outcome
            if match.home_score > match.away_score:
                outcome = "HOME"
            elif match.home_score < match.away_score:
                outcome = "AWAY"
            else:
                outcome = "DRAW"

            # Check if prediction was correct
            probs = {
                "HOME": pred.home_win_prob,
                "DRAW": pred.draw_prob,
                "AWAY": pred.away_win_prob,
            }
            predicted_outcome = max(probs, key=probs.get)
            is_correct = predicted_outcome == outcome

            # Calculate Brier score
            brier = (
                (pred.home_win_prob - (1 if outcome == "HOME" else 0)) ** 2
                + (pred.draw_prob - (1 if outcome == "DRAW" else 0)) ** 2
                + (pred.away_win_prob - (1 if outcome == "AWAY" else 0)) ** 2
            )

            # Update DB
            await self._db.update_prediction_result(pred.id, outcome, is_correct, brier)

            # Record in brain state
            self._state.record_model_result("ensemble", is_correct)

            # Update memory
            self._memory.update_after_match(
                match.home_team_id, match.away_team_id,
                match.home_score, match.away_score,
                match.league_code,
            )

            # Feed to ensemble for learning (ELO update + weight adaptation)
            model_breakdown = {}
            try:
                model_breakdown = json.loads(pred.model_breakdown) if pred.model_breakdown else {}
            except (json.JSONDecodeError, TypeError):
                pass

            prediction_result = PredictionResult(
                home_win_prob=pred.home_win_prob,
                draw_prob=pred.draw_prob,
                away_win_prob=pred.away_win_prob,
                details={"model_breakdown": model_breakdown},
            )
            self._ensemble.record_result(
                match.home_team_id, match.away_team_id,
                match.home_score, match.away_score,
                prediction_result,
            )

            # Remove from active
            self._state.remove_prediction(pred.match_id)

            processed.append({
                "match_id": match.id,
                "predicted": predicted_outcome,
                "actual": outcome,
                "correct": is_correct,
                "brier": round(brier, 4),
            })

            log.info(
                "result_checked",
                match_id=match.id,
                predicted=predicted_outcome,
                actual=outcome,
                correct=is_correct,
                brier=round(brier, 4),
            )

        return processed
