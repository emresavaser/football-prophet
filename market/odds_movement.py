"""Empirical odds movement model for in-match betting.

Models how decimal odds drift between signal generation and bet placement.
Adapted from soccer-edge market/odds_movement.py — standalone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


_ODDS_BUCKETS: list[tuple[float, float]] = [
    (1.0, 2.0),
    (2.0, 3.5),
    (3.5, 6.0),
    (6.0, 12.0),
    (12.0, 25.0),
]


@dataclass
class MovementBucket:
    """Empirical log-drift distribution for one (market, odds_bucket) group."""
    market: str
    bucket_idx: int
    n_obs: int
    mean_drift: float
    std_drift: float
    p5_drift: float
    p95_drift: float


class OddsMovementModel:
    """Empirical bucketed model of in-match odds drift over latency_minutes."""

    def __init__(self, latency_minutes: int = 1, seed: int = 42) -> None:
        self.latency_minutes = latency_minutes
        self.seed = seed
        self._buckets: dict[tuple[str, int], MovementBucket] = {}
        self._global_stats: dict[str, tuple[float, float]] = {}
        self._rng = np.random.default_rng(seed)
        self._fitted = False

    def fit(self, odds_df: pd.DataFrame) -> "OddsMovementModel":
        """Fit bucket statistics from in-match odds DataFrame."""
        required = {"match_id", "minute", "market", "decimal_odds"}
        missing = required - set(odds_df.columns)
        if missing:
            raise KeyError(f"odds_df missing columns: {sorted(missing)}")

        bucket_drifts: dict[tuple[str, int], list[float]] = {}
        market_drifts: dict[str, list[float]] = {}

        for (match_id, market), grp in odds_df.groupby(
            ["match_id", "market"], sort=False
        ):
            grp = grp.sort_values("minute")
            minutes = grp["minute"].values
            prices = grp["decimal_odds"].values

            min_to_price: dict[int, float] = {
                int(m): float(p) for m, p in zip(minutes, prices)
            }

            for m, p_t in zip(minutes, prices):
                m_future = int(m) + self.latency_minutes
                if m_future not in min_to_price:
                    continue
                p_tk = min_to_price[m_future]
                if p_t <= 0 or p_tk <= 0:
                    continue
                log_drift = float(np.log(p_tk / p_t))
                bidx = self.bucket_index(float(p_t))
                key = (str(market), bidx)
                bucket_drifts.setdefault(key, []).append(log_drift)
                market_drifts.setdefault(str(market), []).append(log_drift)

        self._buckets = {}
        for (market, bidx), drifts in bucket_drifts.items():
            arr = np.array(drifts, dtype=float)
            self._buckets[(market, bidx)] = MovementBucket(
                market=market,
                bucket_idx=bidx,
                n_obs=len(arr),
                mean_drift=float(arr.mean()),
                std_drift=float(arr.std()),
                p5_drift=float(np.percentile(arr, 5)),
                p95_drift=float(np.percentile(arr, 95)),
            )

        self._global_stats = {}
        for market, drifts in market_drifts.items():
            arr = np.array(drifts, dtype=float)
            self._global_stats[market] = (float(arr.mean()), float(arr.std()))

        self._fitted = True
        return self

    def predict_drift(self, market: str, current_odds: float,
                      rng: np.random.Generator | None = None) -> float:
        """Sample a log-drift for (market, current_odds) from fitted buckets."""
        _rng = rng if rng is not None else self._rng
        bidx = self.bucket_index(current_odds)
        key = (market, bidx)

        if key in self._buckets:
            b = self._buckets[key]
            if b.std_drift <= 0:
                return b.mean_drift
            return float(_rng.normal(b.mean_drift, b.std_drift))

        if market in self._global_stats:
            mean_g, std_g = self._global_stats[market]
            if std_g <= 0:
                return mean_g
            return float(_rng.normal(mean_g, std_g))

        return 0.0

    def adjusted_odds(self, market: str, current_odds: float,
                      rng: np.random.Generator | None = None) -> float:
        """Return current_odds * exp(drift), clipped to [1.01, 50.0]."""
        drift = self.predict_drift(market, current_odds, rng)
        return float(np.clip(current_odds * np.exp(drift), 1.01, 50.0))

    @staticmethod
    def bucket_index(odds: float) -> int:
        for i, (lo, hi) in enumerate(_ODDS_BUCKETS):
            if lo <= odds < hi:
                return i
        return len(_ODDS_BUCKETS) - 1

    def __repr__(self) -> str:
        status = "fitted" if self._fitted else "unfitted"
        return (
            f"OddsMovementModel(latency_minutes={self.latency_minutes}, "
            f"seed={self.seed}, status={status!r}, "
            f"n_buckets={len(self._buckets)})"
        )
