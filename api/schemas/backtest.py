"""Pydantic schemas for backtest API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class BacktestSummarySchema(BaseModel):
    run_id: str
    created_at: datetime
    league_code: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    total_matches: Optional[int] = None
    correct_predictions: Optional[int] = None
    accuracy: Optional[float] = None
    total_bets: Optional[int] = None
    winning_bets: Optional[int] = None
    roi: Optional[float] = None
    profit_loss: Optional[float] = None
    avg_brier_score: Optional[float] = None

    class Config:
        from_attributes = True


class BacktestDetailSchema(BacktestSummarySchema):
    avg_confidence: Optional[float] = None
    avg_edge: Optional[float] = None
    model_weights_used: dict[str, float] = {}
    config_snapshot: dict[str, Any] = {}
    report: dict[str, Any] = {}


class BacktestListSchema(BaseModel):
    backtests: list[BacktestSummarySchema]
    total: int
    offset: int = 0
    limit: int = 20
