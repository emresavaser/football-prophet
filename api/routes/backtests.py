"""Backtest API endpoints."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from api.schemas.backtest import BacktestDetailSchema, BacktestListSchema, BacktestSummarySchema

router = APIRouter(prefix="/backtests", tags=["backtests"])


def _loads_json(raw: Optional[str]) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@router.get("", response_model=BacktestListSchema)
async def list_backtests(league: Optional[str] = None, limit: int = 20):
    """List recent backtest runs."""
    from api.app import get_prophet

    prophet = get_prophet()
    rows = await prophet.db.list_backtests(league_code=league.upper() if league else None, limit=limit)

    return BacktestListSchema(
        backtests=[
            BacktestSummarySchema(
                run_id=row.run_id,
                created_at=row.created_at,
                league_code=row.league_code,
                date_from=row.date_from,
                date_to=row.date_to,
                total_matches=row.total_matches,
                correct_predictions=row.correct_predictions,
                accuracy=row.accuracy,
                total_bets=row.total_bets,
                winning_bets=row.winning_bets,
                roi=row.roi,
                profit_loss=row.profit_loss,
                avg_brier_score=row.avg_brier_score,
            )
            for row in rows
        ],
        total=len(rows),
    )


@router.get("/{run_id}", response_model=BacktestDetailSchema)
async def get_backtest(run_id: str):
    """Get a single backtest run with config/report payloads."""
    from api.app import get_prophet

    prophet = get_prophet()
    row = await prophet.db.get_backtest(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Backtest not found")

    return BacktestDetailSchema(
        run_id=row.run_id,
        created_at=row.created_at,
        league_code=row.league_code,
        date_from=row.date_from,
        date_to=row.date_to,
        total_matches=row.total_matches,
        correct_predictions=row.correct_predictions,
        accuracy=row.accuracy,
        total_bets=row.total_bets,
        winning_bets=row.winning_bets,
        roi=row.roi,
        profit_loss=row.profit_loss,
        avg_brier_score=row.avg_brier_score,
        avg_confidence=row.avg_confidence,
        avg_edge=row.avg_edge,
        model_weights_used=_loads_json(row.model_weights_used),
        config_snapshot=_loads_json(row.config_snapshot),
        report=_loads_json(row.report_json),
    )
