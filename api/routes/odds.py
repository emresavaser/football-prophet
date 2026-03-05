"""Odds API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas.odds import OddsSchema, OddsListSchema

router = APIRouter(prefix="/odds", tags=["odds"])


@router.get("/match/{match_id}", response_model=OddsListSchema)
async def get_match_odds(match_id: int):
    """Get odds history for a match."""
    from api.app import get_prophet
    prophet = get_prophet()

    latest = await prophet.db.get_latest_odds(match_id)
    if not latest:
        raise HTTPException(status_code=404, detail="No odds found")

    return OddsListSchema(
        odds=[OddsSchema(
            id=latest.id,
            match_id=latest.match_id,
            bookmaker=latest.bookmaker,
            timestamp=latest.timestamp,
            home_win=latest.home_win,
            draw=latest.draw,
            away_win=latest.away_win,
            over_25=latest.over_25,
            under_25=latest.under_25,
            btts_yes=latest.btts_yes,
            btts_no=latest.btts_no,
            bookmaker_margin=latest.bookmaker_margin,
        )],
        match_id=match_id,
    )
