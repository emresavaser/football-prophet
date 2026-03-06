"""Team API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Optional

from api.schemas.match import TeamSchema

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/league/{league_code}", response_model=list[TeamSchema])
async def get_teams_by_league(league_code: str):
    """Get all teams in a league."""
    from api.app import get_prophet
    prophet = get_prophet()
    teams = await prophet.db.get_teams_by_league(league_code.upper())
    return [
        TeamSchema(
            id=t.id,
            name=t.name,
            league_code=t.league_code,
            elo_rating=t.elo_rating,
        )
        for t in teams
    ]


@router.get("/{team_id}", response_model=dict)
async def get_team_detail(team_id: int):
    """Get team details with brain profile."""
    from api.app import get_prophet
    prophet = get_prophet()

    team = await prophet.db.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    profile = prophet.memory.get_team_profile(team_id)
    strength = prophet.strength_calc.get_team_strength(team_id)

    return {
        "id": team.id,
        "name": team.name,
        "league_code": team.league_code,
        "elo_rating": profile.elo_rating,
        "attack_strength": strength["attack"],
        "defense_strength": strength["defense"],
        "overall_strength": strength["overall"],
        "form_score": profile.form_score,
        "trend": profile.trend,
        "last_5": profile.last_5_results,
        "home_record": profile.home_record.to_dict(),
        "away_record": profile.away_record.to_dict(),
    }
