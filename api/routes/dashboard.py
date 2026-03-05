"""Dashboard API endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_stats():
    """Get overall system statistics."""
    from api.app import get_prophet
    prophet = get_prophet()

    accuracy = await prophet.db.get_model_accuracy(days=30)
    brain_info = prophet.persistence.get_state_info()
    cache_stats = prophet.cache.stats

    return {
        "accuracy_30d": accuracy,
        "brain": {
            "teams_tracked": len(prophet.memory.team_profiles),
            "leagues_tracked": len(prophet.memory.league_averages),
            "h2h_pairs": len(prophet.memory.h2h_cache),
            "state_file": brain_info,
        },
        "cache": cache_stats,
        "state": {
            "active_predictions": len(prophet.state.active_predictions),
            "scan_stats": prophet.state.scan_stats.to_dict(),
        },
    }


@router.get("/model-performance")
async def get_model_performance():
    """Get per-model performance metrics."""
    from api.app import get_prophet
    prophet = get_prophet()

    return {
        "weights": prophet.learner.model_weights,
        "performance": prophet.learner.get_model_performance(),
        "calibration": prophet.learner.get_calibration_curve(),
        "total_predictions": prophet.learner.total_predictions,
        "overall_brier": prophet.learner.overall_brier,
        "model_health": {k: v.to_dict() for k, v in prophet.state.model_health.items()},
    }


@router.get("/roi")
async def get_roi():
    """Get ROI and betting performance."""
    from api.app import get_prophet
    prophet = get_prophet()

    accuracy = await prophet.db.get_model_accuracy(days=30)
    value_bets = await prophet.db.get_value_bets(upcoming_only=False)

    total_bets = len(value_bets)
    correct = sum(1 for vb in value_bets if vb.is_correct)

    return {
        "prediction_accuracy": accuracy,
        "value_bets_total": total_bets,
        "value_bets_correct": correct,
        "value_bet_accuracy": correct / total_bets if total_bets > 0 else 0.0,
        "bankroll": prophet.config.bankroll,
    }
