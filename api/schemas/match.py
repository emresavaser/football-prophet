"""Pydantic schemas for match data."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TeamSchema(BaseModel):
    id: int
    name: str
    league_code: str
    elo_rating: Optional[float] = None

    class Config:
        from_attributes = True


class MatchSchema(BaseModel):
    id: int
    external_id: Optional[str] = None
    league_code: str
    season: Optional[str] = None
    matchday: Optional[int] = None
    match_date: datetime
    status: str

    home_team_id: int
    away_team_id: int
    home_team_name: Optional[str] = None
    away_team_name: Optional[str] = None

    home_score: Optional[int] = None
    away_score: Optional[int] = None

    class Config:
        from_attributes = True


class MatchListSchema(BaseModel):
    matches: list[MatchSchema]
    total: int
    league_code: Optional[str] = None
