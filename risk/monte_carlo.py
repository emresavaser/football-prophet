"""Monte Carlo ruin probability simulation for betting strategies.

Simulates N independent paths of bet outcomes using historical (model_prob,
decimal_odds) pairs. For each path the same bet sequence is replayed but
outcomes are re-drawn as Bernoulli(model_prob).

Adapted from soccer-edge risk/monte_carlo.py — import paths updated.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from .kelly import DrawdownGuard, StakingPolicy


def simulate_ruin_probability(
    model_probs: np.ndarray,
    decimal_odds: np.ndarray,
    policy: StakingPolicy,
    guard: DrawdownGuard | None = None,
    initial_bankroll: float = 1_000.0,
    n_paths: int = 2_000,
    ruin_threshold: float = 0.0,
    seed: int = 42,
) -> dict[str, Any]:
    """Monte Carlo ruin probability simulation.

    Returns dict with p_ruin, mean/median/p1/p5/p95 terminal equity, n_paths, n_bets_per_path.
    """
    model_probs = np.asarray(model_probs, dtype=float)
    decimal_odds = np.asarray(decimal_odds, dtype=float)

    if len(model_probs) != len(decimal_odds):
        raise ValueError("model_probs and decimal_odds must have the same length")

    n_bets = len(model_probs)
    if n_bets == 0:
        return {
            "p_ruin": 0.0,
            "mean_terminal_equity": initial_bankroll,
            "median_terminal_equity": initial_bankroll,
            "p1_terminal_equity": initial_bankroll,
            "p5_terminal_equity": initial_bankroll,
            "p95_terminal_equity": initial_bankroll,
            "n_paths": n_paths,
            "n_bets_per_path": 0,
        }

    rng = np.random.default_rng(seed)
    terminal_bankrolls = np.empty(n_paths, dtype=float)

    for path_idx in range(n_paths):
        bankroll = initial_bankroll
        pnl_history = np.empty(n_bets, dtype=float)
        n_recorded = 0

        path_guard: DrawdownGuard | None = (
            copy.deepcopy(guard) if guard is not None else None
        )
        if path_guard is not None:
            path_guard.reset(initial_bankroll)

        for bet_idx in range(n_bets):
            p = model_probs[bet_idx]
            odds = decimal_odds[bet_idx]

            multiplier = (
                path_guard.stake_multiplier() if path_guard is not None else 1.0
            )
            if multiplier <= 0.0:
                break

            raw_stake = policy.stake(p, odds, bankroll, pnl_history[:n_recorded])
            stake = raw_stake * multiplier

            if stake <= 0.0:
                continue

            win = rng.random() < p
            pnl = stake * (odds - 1.0) if win else -stake
            bankroll += pnl

            pnl_history[n_recorded] = pnl
            n_recorded += 1

            if path_guard is not None:
                path_guard.update(bankroll)

            if bankroll <= ruin_threshold:
                break

        terminal_bankrolls[path_idx] = bankroll

    n_ruined = int(np.sum(terminal_bankrolls <= ruin_threshold))

    return {
        "p_ruin": round(n_ruined / n_paths, 6),
        "mean_terminal_equity": round(float(np.mean(terminal_bankrolls)), 4),
        "median_terminal_equity": round(float(np.median(terminal_bankrolls)), 4),
        "p1_terminal_equity": round(float(np.percentile(terminal_bankrolls, 1)), 4),
        "p5_terminal_equity": round(float(np.percentile(terminal_bankrolls, 5)), 4),
        "p95_terminal_equity": round(float(np.percentile(terminal_bankrolls, 95)), 4),
        "n_paths": n_paths,
        "n_bets_per_path": n_bets,
    }
