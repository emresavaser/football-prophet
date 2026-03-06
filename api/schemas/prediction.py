"""Pydantic schemas for predictions."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PredictionSchema(BaseModel):
    id: int
    match_id: int
    created_at: datetime

    home_win_prob: float
    draw_prob: float
    away_win_prob: float

    predicted_home_goals: Optional[float] = None
    predicted_away_goals: Optional[float] = None
    most_likely_score: Optional[str] = None

    over_25_prob: Optional[float] = None
    btts_prob: Optional[float] = None

    confidence: float
    predicted_outcome: Optional[str] = None

    is_correct: Optional[bool] = None
    brier_score: Optional[float] = None

    is_value_bet: bool = False
    value_bet_market: Optional[str] = None
    edge: Optional[float] = None
    kelly_stake: Optional[float] = None
    ev: Optional[float] = None

    # Match info (joined)
    home_team_name: Optional[str] = None
    away_team_name: Optional[str] = None
    league_code: Optional[str] = None
    match_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class ValueBetSchema(BaseModel):
    id: Optional[int] = None
    prediction_id: Optional[int] = None
    match_id: int
    home_team: str
    away_team: str
    league_code: str
    market: str
    odds: float
    model_prob: float
    implied_prob: float
    fair_prob: Optional[float] = None
    overround: Optional[float] = None
    edge: float
    ev: float
    kelly_stake: float
    confidence: float
    closing_odds: Optional[float] = None
    closing_implied_prob: Optional[float] = None
    clv: Optional[float] = None
    result: Optional[str] = None
    won: Optional[bool] = None
    push: Optional[bool] = None
    pnl: Optional[float] = None
    settled_at: Optional[datetime] = None
    match_date: Optional[datetime] = None


class PredictionListSchema(BaseModel):
    predictions: list[PredictionSchema]
    total: int
