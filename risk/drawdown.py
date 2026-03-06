"""Thin factory wrapper for DrawdownGuard creation."""

from __future__ import annotations

from .kelly import DrawdownGuard


def create_drawdown_guard(
    soft_threshold: float = 0.10,
    hard_limit: float = 0.25,
    initial_bankroll: float = 1_000.0,
) -> DrawdownGuard:
    """Create a DrawdownGuard with the given parameters."""
    return DrawdownGuard(
        soft_threshold=soft_threshold,
        hard_limit=hard_limit,
        initial_bankroll=initial_bankroll,
    )
