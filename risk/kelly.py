"""Kelly criterion staking with fractional Kelly, staking policies, and DrawdownGuard.

Adapted from soccer-edge risk/kelly.py — removed soccer_edge.config dependency.
"""

from __future__ import annotations

import numpy as np


# ========================================================= standalone function

def kelly_fraction(p: float, b: float, f_max: float = 1.0) -> float:
    """Full Kelly fraction, clamped to [0, f_max].

    f* = (b*p - q) / b  where q = 1 - p.
    """
    if p <= 0.0 or p >= 1.0 or b <= 0.0:
        return 0.0
    q = 1.0 - p
    f_star = (b * p - q) / b
    if f_star <= 0.0:
        return 0.0
    return min(f_star, f_max)


# =========================================================== staking policies

class StakingPolicy:
    """Base class for all staking policies."""

    name: str = "base"

    def stake(
        self,
        model_prob: float,
        decimal_odds: float,
        bankroll: float,
        profit_history: np.ndarray,
    ) -> float:
        raise NotImplementedError


class FlatPolicy(StakingPolicy):
    """Flat staking: always bet 1 unit."""

    name: str = "flat"

    def stake(self, model_prob: float, decimal_odds: float,
              bankroll: float, profit_history: np.ndarray) -> float:
        return 1.0


class _KellyScaledPolicy(StakingPolicy):
    """Internal base for multiplicative Kelly variants."""

    _scale: float = 1.0

    def __init__(self, f_max: float = 0.05) -> None:
        self.f_max = f_max

    def stake(self, model_prob: float, decimal_odds: float,
              bankroll: float, profit_history: np.ndarray) -> float:
        b = decimal_odds - 1.0
        f_full = kelly_fraction(model_prob, b, f_max=1.0)
        f = min(f_full * self._scale, self.f_max)
        return max(0.0, f * bankroll)


class KellyFullPolicy(_KellyScaledPolicy):
    """Full Kelly staking."""
    name: str = "kelly_full"
    _scale: float = 1.0


class KellyHalfPolicy(_KellyScaledPolicy):
    """Half-Kelly staking (50% of full Kelly)."""
    name: str = "kelly_half"
    _scale: float = 0.5


class KellyQuarterPolicy(_KellyScaledPolicy):
    """Quarter-Kelly staking (25% of full Kelly)."""
    name: str = "kelly_quarter"
    _scale: float = 0.25


class VolatilityTargetedPolicy(StakingPolicy):
    """Kelly stake scaled to hit a target per-bet return volatility."""

    name: str = "vol_targeted"

    def __init__(self, target_vol: float = 0.05, window: int = 20,
                 f_max: float = 0.05) -> None:
        self.target_vol = target_vol
        self.window = window
        self.f_max = f_max

    def stake(self, model_prob: float, decimal_odds: float,
              bankroll: float, profit_history: np.ndarray) -> float:
        b = decimal_odds - 1.0
        base_kelly = kelly_fraction(model_prob, b, f_max=1.0)
        if base_kelly <= 0.0:
            return 0.0

        if len(profit_history) >= 2:
            recent = profit_history[-self.window:]
            frac_returns = recent / max(bankroll, 1.0)
            vol = float(np.std(frac_returns))
        else:
            vol = 0.0

        if vol <= 0.0:
            target_fraction = self.f_max
        else:
            target_fraction = min(self.target_vol / vol, self.f_max)

        f = min(base_kelly, target_fraction)
        return max(0.0, f * bankroll)


# =========================================================== DrawdownGuard

class DrawdownGuard:
    """Tiered stake-reduction policy based on current drawdown from peak.

    dd <= soft_threshold     -> multiplier = 1.0
    soft < dd < hard_limit   -> linear ramp from 1 -> 0
    dd >= hard_limit         -> multiplier = 0.0 (halt)
    """

    def __init__(
        self,
        soft_threshold: float = 0.10,
        hard_limit: float = 0.25,
        initial_bankroll: float = 1_000.0,
    ) -> None:
        if hard_limit <= soft_threshold:
            raise ValueError(
                f"hard_limit ({hard_limit}) must be > soft_threshold ({soft_threshold})"
            )
        self.soft_threshold = soft_threshold
        self.hard_limit = hard_limit
        self._equity = initial_bankroll
        self._peak = initial_bankroll

    def update(self, bankroll: float) -> None:
        """Update current equity and (non-decreasing) peak."""
        self._equity = bankroll
        if bankroll > self._peak:
            self._peak = bankroll

    def current_drawdown(self) -> float:
        """Current drawdown as a fraction of peak."""
        if self._peak <= 0.0:
            return 0.0
        return max(0.0, (self._peak - self._equity) / self._peak)

    def stake_multiplier(self) -> float:
        """Stake multiplier in [0, 1] based on current drawdown."""
        dd = self.current_drawdown()
        if dd <= self.soft_threshold:
            return 1.0
        if dd >= self.hard_limit:
            return 0.0
        return (self.hard_limit - dd) / (self.hard_limit - self.soft_threshold)

    def guard_state(self) -> dict[str, float]:
        """Snapshot of current guard state."""
        return {
            "equity": round(self._equity, 4),
            "peak": round(self._peak, 4),
            "dd": round(self.current_drawdown(), 6),
            "stake_multiplier": round(self.stake_multiplier(), 6),
        }

    def reset(self, initial_bankroll: float | None = None) -> None:
        """Reset guard state."""
        if initial_bankroll is not None:
            self._equity = initial_bankroll
            self._peak = initial_bankroll
        else:
            self._peak = self._equity


class KellyStaker:
    """Compute fractional Kelly stake sizes."""

    def __init__(self, kelly_fraction: float = 0.25,
                 max_bet_fraction: float = 0.05) -> None:
        self.kelly_fraction = kelly_fraction
        self.max_bet_fraction = max_bet_fraction

    def kelly_fraction_bet(self, predicted_prob: float,
                           decimal_odds: float) -> float:
        b = decimal_odds - 1.0
        p = predicted_prob
        q = 1.0 - p
        if b <= 0 or p <= 0 or p >= 1:
            return 0.0
        full_kelly = (b * p - q) / b
        if full_kelly <= 0:
            return 0.0
        return min(full_kelly * self.kelly_fraction, self.max_bet_fraction)

    def stake(self, bankroll: float, predicted_prob: float,
              decimal_odds: float) -> float:
        fraction = self.kelly_fraction_bet(predicted_prob, decimal_odds)
        return round(bankroll * fraction, 2)


# =========================================================== policy factory

STAKING_POLICIES: dict[str, type[StakingPolicy]] = {
    "flat": FlatPolicy,
    "kelly_full": KellyFullPolicy,
    "kelly_half": KellyHalfPolicy,
    "kelly_quarter": KellyQuarterPolicy,
    "vol_targeted": VolatilityTargetedPolicy,
}


def get_staking_policy(name: str, **kwargs) -> StakingPolicy:
    """Factory to create a staking policy by name."""
    cls = STAKING_POLICIES.get(name)
    if cls is None:
        raise ValueError(f"Unknown staking policy: {name!r}. Options: {list(STAKING_POLICIES)}")
    if cls is FlatPolicy:
        return cls()
    return cls(**kwargs)
