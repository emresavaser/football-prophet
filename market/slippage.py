"""Exchange slippage and fill simulation.

Models execution risks: no-fill and slippage when placing bets.
Adapted from soccer-edge market/slippage.py — standalone, zero internal dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class FillResult:
    """Result of a single simulated exchange fill attempt."""
    offered_odds: float
    fill_odds: float
    filled: bool
    slippage_bps: float


def simulate_fill_odds(
    offered_odds: float,
    market: str,
    match_id: str,
    minute: int,
    *,
    seed: int = 42,
    max_slippage_bps: float = 150.0,
    p_no_fill_base: float = 0.05,
) -> FillResult:
    """Simulate an exchange fill for one bet.

    Deterministic: same (seed, match_id, minute, market) -> same result.
    """
    hash_key = abs(hash((seed, match_id, minute, market))) % (2 ** 31)
    rng = np.random.default_rng(hash_key)

    if rng.uniform() < p_no_fill_base:
        return FillResult(
            offered_odds=offered_odds,
            fill_odds=offered_odds,
            filled=False,
            slippage_bps=0.0,
        )

    if max_slippage_bps <= 0.0:
        slippage_bps = 0.0
    else:
        slippage_bps = float(
            rng.triangular(0.0, max_slippage_bps / 2.0, max_slippage_bps)
        )
    fill_odds = max(1.01, offered_odds * (1.0 - slippage_bps / 10_000.0))

    return FillResult(
        offered_odds=offered_odds,
        fill_odds=fill_odds,
        filled=True,
        slippage_bps=slippage_bps,
    )


def compute_slippage_metrics(fill_results: list[FillResult]) -> dict[str, Any]:
    """Aggregate fill statistics across multiple simulated orders."""
    if not fill_results:
        return {
            "avg_slippage_bps": float("nan"),
            "p_no_fill": float("nan"),
            "p_improve": 0.0,
            "n_fills": 0,
            "n_total": 0,
        }

    n = len(fill_results)
    filled = [r for r in fill_results if r.filled]
    n_filled = len(filled)
    filled_slippage = [r.slippage_bps for r in filled]

    return {
        "avg_slippage_bps": float(np.mean(filled_slippage)) if filled_slippage else float("nan"),
        "p_no_fill": round((n - n_filled) / n, 6),
        "p_improve": 0.0,
        "n_fills": n_filled,
        "n_total": n,
    }
