"""Pydantic schemas for odds data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OddsSchema(BaseModel):
    id: int
    match_id: int
    bookmaker: str = "average"
    timestamp: datetime

    home_win: Optional[float] = None
    draw: Optional[float] = None
    away_win: Optional[float] = None

    over_25: Optional[float] = None
    under_25: Optional[float] = None

    btts_yes: Optional[float] = None
    btts_no: Optional[float] = None

    bookmaker_margin: Optional[float] = None

    class Config:
        from_attributes = True


class OddsListSchema(BaseModel):
    odds: list[OddsSchema]
    match_id: int
