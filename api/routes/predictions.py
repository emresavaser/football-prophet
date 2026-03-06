"""Prediction API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from api.schemas.prediction import PredictionSchema, ValueBetSchema

router = APIRouter(prefix="/predictions", tags=["predictions"])

MARKET_MODEL_PROB_FIELDS = {
    "home_win": "home_win_prob",
    "draw": "draw_prob",
    "away_win": "away_win_prob",
    "over_25": "over_25_prob",
    "btts_yes": "btts_prob",
}

MARKET_ODDS_FIELDS = {
    "home_win": "home_win",
    "draw": "draw",
    "away_win": "away_win",
    "over_25": "over_25",
    "under_25": "under_25",
    "btts_yes": "btts_yes",
    "btts_no": "btts_no",
}


def _value_bet_snapshot(pred, odds) -> tuple[float, float, float]:
    market = getattr(pred, "market", None) or getattr(pred, "value_bet_market", "") or ""
    model_prob_field = MARKET_MODEL_PROB_FIELDS.get(market)
    odds_field = MARKET_ODDS_FIELDS.get(market)

    model_prob = float(getattr(pred, "model_prob", 0.0) or 0.0)
    if model_prob_field and model_prob == 0.0:
        model_prob = float(getattr(pred, model_prob_field, 0.0) or 0.0)
    offered_odds = float(getattr(pred, "odds", 0.0) or 0.0)
    if odds and odds_field:
        offered_odds = float(getattr(odds, odds_field, offered_odds) or offered_odds)
    implied_prob = float(getattr(pred, "implied_prob", 0.0) or 0.0)
    if implied_prob == 0.0 and offered_odds > 0:
        implied_prob = 1.0 / offered_odds
    return offered_odds, model_prob, implied_prob


def _closing_line_snapshot(value_bet, latest_odds) -> tuple[float | None, float | None, float | None]:
    market = getattr(value_bet, "market", None) or getattr(value_bet, "value_bet_market", "") or ""
    odds_field = MARKET_ODDS_FIELDS.get(market)
    if not latest_odds or not odds_field:
        return None, None, None

    closing_odds = getattr(latest_odds, odds_field, None)
    if not closing_odds:
        return None, None, None

    closing_implied = 1.0 / closing_odds if closing_odds > 0 else None
    taken_odds = getattr(value_bet, "odds", None)
    clv = ((taken_odds - closing_odds) / closing_odds) if taken_odds and closing_odds else None
    return closing_odds, closing_implied, clv


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
    for value_bet in value_preds:
        match = await prophet.db.get_match(value_bet.match_id)
        if not match:
            continue
        odds = await prophet.db.get_latest_odds(value_bet.match_id)
        home_team = await prophet.db.get_team(match.home_team_id)
        away_team = await prophet.db.get_team(match.away_team_id)
        offered_odds, model_prob, implied_prob = _value_bet_snapshot(value_bet, odds)
        closing_odds, closing_implied_prob, clv = _closing_line_snapshot(value_bet, odds)

        result.append(ValueBetSchema(
            id=value_bet.id,
            prediction_id=value_bet.prediction_id,
            match_id=value_bet.match_id,
            home_team=home_team.name if home_team else "?",
            away_team=away_team.name if away_team else "?",
            league_code=match.league_code,
            market=getattr(value_bet, "market", None) or getattr(value_bet, "value_bet_market", "") or "",
            odds=offered_odds,
            model_prob=model_prob,
            implied_prob=implied_prob,
            fair_prob=value_bet.fair_prob,
            overround=value_bet.overround,
            edge=value_bet.edge or 0.0,
            ev=value_bet.ev or 0.0,
            kelly_stake=value_bet.kelly_stake or 0.0,
            confidence=value_bet.confidence,
            closing_odds=closing_odds,
            closing_implied_prob=closing_implied_prob,
            clv=clv,
            result=getattr(value_bet, "result", None),
            won=getattr(value_bet, "won", None),
            push=getattr(value_bet, "push", None),
            pnl=getattr(value_bet, "pnl", None),
            settled_at=getattr(value_bet, "settled_at", None),
            match_date=match.match_date,
        ))

    return result
