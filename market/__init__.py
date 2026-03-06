"""Market microstructure module — slippage simulation and odds movement model."""

from .slippage import FillResult, simulate_fill_odds, compute_slippage_metrics
from .odds_movement import OddsMovementModel, MovementBucket

__all__ = [
    "FillResult",
    "simulate_fill_odds",
    "compute_slippage_metrics",
    "OddsMovementModel",
    "MovementBucket",
]
