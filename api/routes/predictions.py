"""Prediction API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from api.schemas.prediction import PredictionSchema, ValueBetSchema

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/upcoming", response_model=list[PredictionSchema])
async def get_upcoming_predictions(league: Optional[str] = None):
    """Get predictions for upcoming matches."""
    from api.app import get_prophet
    prophet = get_prophet()
    predictions = await prophet.db.get_pending_predictions()

    result = []
    for pred in predictions:
        match = await prophet.db.get_match(pred.match_id)
        if not match:
            continue
        if league and match.league_code != league.upper():
            continue

        home_team = await prophet.db.get_team(match.home_team_id)
        away_team = await prophet.db.get_team(match.away_team_id)

        probs = {"HOME": pred.home_win_prob, "DRAW": pred.draw_prob, "AWAY": pred.away_win_prob}

        result.append(PredictionSchema(
            id=pred.id,
            match_id=pred.match_id,
            created_at=pred.created_at,
            home_win_prob=pred.home_win_prob,
            draw_prob=pred.draw_prob,
            away_win_prob=pred.away_win_prob,
            predicted_home_goals=pred.predicted_home_goals,
            predicted_away_goals=pred.predicted_away_goals,
            most_likely_score=pred.most_likely_score,
            over_25_prob=pred.over_25_prob,
            btts_prob=pred.btts_prob,
            confidence=pred.confidence,
            predicted_outcome=max(probs, key=probs.get),
            is_value_bet=pred.is_value_bet or False,
            value_bet_market=pred.value_bet_market,
            edge=pred.edge,
            ev=pred.ev,
            kelly_stake=pred.kelly_stake,
            home_team_name=home_team.name if home_team else None,
            away_team_name=away_team.name if away_team else None,
            league_code=match.league_code,
            match_date=match.match_date,
        ))

    return result


@router.get("/match/{match_id}", response_model=list[PredictionSchema])
async def get_match_predictions(match_id: int):
    """Get all predictions for a specific match."""
    from api.app import get_prophet
    prophet = get_prophet()
    predictions = await prophet.db.get_predictions_for_match(match_id)

    if not predictions:
        raise HTTPException(status_code=404, detail="No predictions found")

    match = await prophet.db.get_match(match_id)
    home_team = await prophet.db.get_team(match.home_team_id) if match else None
    away_team = await prophet.db.get_team(match.away_team_id) if match else None

    result = []
    for pred in predictions:
        probs = {"HOME": pred.home_win_prob, "DRAW": pred.draw_prob, "AWAY": pred.away_win_prob}
        result.append(PredictionSchema(
            id=pred.id,
            match_id=pred.match_id,
            created_at=pred.created_at,
            home_win_prob=pred.home_win_prob,
            draw_prob=pred.draw_prob,
            away_win_prob=pred.away_win_prob,
            predicted_home_goals=pred.predicted_home_goals,
            predicted_away_goals=pred.predicted_away_goals,
            most_likely_score=pred.most_likely_score,
            confidence=pred.confidence,
            predicted_outcome=max(probs, key=probs.get),
            is_correct=pred.is_correct,
            brier_score=pred.brier_score,
            is_value_bet=pred.is_value_bet or False,
            home_team_name=home_team.name if home_team else None,
            away_team_name=away_team.name if away_team else None,
            league_code=match.league_code if match else None,
        ))

    return result


@router.get("/value-bets", response_model=list[ValueBetSchema])
async def get_value_bets():
    """Get current value bets."""
    from api.app import get_prophet
    prophet = get_prophet()
    value_preds = await prophet.db.get_value_bets(upcoming_only=True)

    result = []
    for pred in value_preds:
        match = await prophet.db.get_match(pred.match_id)
        if not match:
            continue
        home_team = await prophet.db.get_team(match.home_team_id)
        away_team = await prophet.db.get_team(match.away_team_id)

        result.append(ValueBetSchema(
            match_id=pred.match_id,
            home_team=home_team.name if home_team else "?",
            away_team=away_team.name if away_team else "?",
            league_code=match.league_code,
            market=pred.value_bet_market or "",
            odds=0.0,
            model_prob=pred.home_win_prob,
            implied_prob=0.0,
            edge=pred.edge or 0.0,
            ev=pred.ev or 0.0,
            kelly_stake=pred.kelly_stake or 0.0,
            confidence=pred.confidence,
            match_date=match.match_date,
        ))

    return result
