"""Bookmaker margin (vig) removal utilities.

Three methods to recover fair (vig-free) probabilities from decimal odds:

Multiplicative (market-normalisation):
    p_i = pi_i / S

Additive (equal-margin removal):
    p_i = pi_i - (S - 1) / n

Shin (1993) insider-trading model:
    Iteratively find z in (0, 1) such that sum(f(z, pi_i)) = 1.

Adapted from soccer-edge eval/vig.py — standalone, zero internal dependencies.
"""

from __future__ import annotations

from typing import Literal

import numpy as np


def overround(implied_probs: np.ndarray) -> float:
    """Compute bookmaker overround S = sum(1/o_i)."""
    return float(np.sum(implied_probs))


def remove_vig_multiplicative(implied_probs: np.ndarray) -> np.ndarray:
    """Multiplicative (market-normalisation) vig removal: p_i = pi_i / S."""
    s = overround(implied_probs)
    if s <= 0:
        raise ValueError("overround must be positive")
    return implied_probs / s


def remove_vig_additive(implied_probs: np.ndarray) -> np.ndarray:
    """Additive (equal-margin) vig removal: p_i = pi_i - (S - 1) / n."""
    s = overround(implied_probs)
    n = len(implied_probs)
    if n == 0:
        raise ValueError("implied_probs must be non-empty")
    margin_share = (s - 1.0) / n
    fair = implied_probs - margin_share
    fair = np.clip(fair, 0.0, None)
    total = fair.sum()
    if total <= 0:
        raise ValueError("All additive-adjusted probabilities are <= 0")
    return fair / total


def remove_vig_shin(
    implied_probs: np.ndarray,
    tol: float = 1e-10,
    max_iter: int = 1_000,
) -> np.ndarray:
    """Shin (1993) insider-trading vig removal via Brent's method."""
    from scipy.optimize import brentq

    s = overround(implied_probs)
    if abs(s - 1.0) < 1e-12:
        return implied_probs.copy()

    pi = implied_probs

    def _sum_fair(z: float) -> float:
        numerator = np.sqrt(z ** 2 + 4.0 * (1.0 - z) * pi ** 2 / s) - z
        denominator = 2.0 * (1.0 - z)
        return float(np.sum(numerator / denominator)) - 1.0

    z_star = brentq(_sum_fair, 0.0, 1.0 - 1e-9, xtol=tol, maxiter=max_iter)

    numerator = np.sqrt(z_star ** 2 + 4.0 * (1.0 - z_star) * pi ** 2 / s) - z_star
    fair = numerator / (2.0 * (1.0 - z_star))
    return fair / fair.sum()


def remove_vig(
    implied_probs: np.ndarray,
    method: Literal["multiplicative", "additive", "shin"] = "shin",
) -> np.ndarray:
    """Dispatcher: apply the specified vig removal method."""
    if method == "multiplicative":
        return remove_vig_multiplicative(implied_probs)
    if method == "additive":
        return remove_vig_additive(implied_probs)
    if method == "shin":
        return remove_vig_shin(implied_probs)
    raise ValueError(
        f"Unknown vig removal method {method!r}. "
        "Expected 'multiplicative', 'additive', or 'shin'."
    )


def fair_probabilities(
    home_odds: float,
    draw_odds: float,
    away_odds: float,
    method: str = "shin",
) -> tuple[float, float, float, float]:
    """Compute fair probabilities for a 3-way market.

    Returns
    -------
    (fair_home, fair_draw, fair_away, overround_value)
    """
    implied = np.array([1.0 / home_odds, 1.0 / draw_odds, 1.0 / away_odds])
    ov = overround(implied)
    fair = remove_vig(implied, method=method)
    return float(fair[0]), float(fair[1]), float(fair[2]), ov


def fair_probabilities_2way(
    odds_a: float,
    odds_b: float,
    method: str = "shin",
) -> tuple[float, float, float]:
    """Compute fair probabilities for a 2-way market (over/under, BTTS).

    Returns
    -------
    (fair_a, fair_b, overround_value)
    """
    implied = np.array([1.0 / odds_a, 1.0 / odds_b])
    ov = overround(implied)
    fair = remove_vig(implied, method=method)
    return float(fair[0]), float(fair[1]), ov
