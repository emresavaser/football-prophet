"""Match data API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Optional

from api.schemas.match import MatchSchema, MatchListSchema

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/today", response_model=MatchListSchema)
async def get_today_matches(league: Optional[str] = None):
    """Get today's matches."""
    from api.app import get_prophet
    prophet = get_prophet()
    matches = await prophet.db.get_upcoming_matches(
        league_code=league.upper() if league else None,
        days_ahead=1,
    )

    items = []
    for m in matches:
        home = await prophet.db.get_team(m.home_team_id)
        away = await prophet.db.get_team(m.away_team_id)
        items.append(MatchSchema(
            id=m.id,
            external_id=m.external_id,
            league_code=m.league_code,
            season=m.season,
            matchday=m.matchday,
            match_date=m.match_date,
            status=m.status,
            home_team_id=m.home_team_id,
            away_team_id=m.away_team_id,
            home_team_name=home.name if home else None,
            away_team_name=away.name if away else None,
            home_score=m.home_score,
            away_score=m.away_score,
        ))

    return MatchListSchema(matches=items, total=len(items), league_code=league)


@router.get("/league/{league_code}", response_model=MatchListSchema)
async def get_league_matches(league_code: str, season: Optional[str] = None):
    """Get matches for a league."""
    from api.app import get_prophet
    prophet = get_prophet()
    matches = await prophet.db.get_league_matches(league_code.upper(), season=season)

    items = []
    for m in matches:
        items.append(MatchSchema(
            id=m.id,
            league_code=m.league_code,
            season=m.season,
            matchday=m.matchday,
            match_date=m.match_date,
            status=m.status,
            home_team_id=m.home_team_id,
            away_team_id=m.away_team_id,
            home_score=m.home_score,
            away_score=m.away_score,
        ))

    return MatchListSchema(matches=items, total=len(items), league_code=league_code)


@router.get("/team/{team_id}/history", response_model=list[MatchSchema])
async def get_team_history(team_id: int, limit: int = 20):
    """Get match history for a team."""
    from api.app import get_prophet
    prophet = get_prophet()
    matches = await prophet.db.get_team_matches(team_id, limit=limit)

    if not matches:
        raise HTTPException(status_code=404, detail="No matches found")

    return [
        MatchSchema(
            id=m.id,
            league_code=m.league_code,
            season=m.season,
            matchday=m.matchday,
            match_date=m.match_date,
            status=m.status,
            home_team_id=m.home_team_id,
            away_team_id=m.away_team_id,
            home_score=m.home_score,
            away_score=m.away_score,
        )
        for m in matches
    ]
