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

    history = await prophet.db.get_odds_history(match_id)
    if not history:
        raise HTTPException(status_code=404, detail="No odds found")

    return OddsListSchema(
        odds=[
            OddsSchema(
                id=item.id,
                match_id=item.match_id,
                bookmaker=item.bookmaker,
                timestamp=item.timestamp,
                home_win=item.home_win,
                draw=item.draw,
                away_win=item.away_win,
                over_25=item.over_25,
                under_25=item.under_25,
                btts_yes=item.btts_yes,
                btts_no=item.btts_no,
                bookmaker_margin=item.bookmaker_margin,
            )
            for item in history
        ],
        match_id=match_id,
    )
