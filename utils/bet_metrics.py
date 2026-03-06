"""Helpers for aggregating bet-level performance metrics."""

from __future__ import annotations

from typing import Any


def _get_value(item: Any, key: str, default=None):
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def aggregate_bet_metrics(bets: list[Any]) -> dict:
    settled_bets = [
        bet for bet in bets
        if _get_value(bet, "result") in {"WIN", "LOSS", "PUSH"}
    ]
    graded_bets = [bet for bet in settled_bets if not _get_value(bet, "push", False)]
    clv_values = [
        _get_value(bet, "clv") for bet in bets
        if _get_value(bet, "clv") is not None
    ]

    def stake_amount(bet: Any) -> float:
        return float(_get_value(bet, "stake", _get_value(bet, "kelly_stake", 0.0)) or 0.0)

    total_staked = round(sum(stake_amount(bet) for bet in settled_bets), 4)
    total_pnl = round(sum(float(_get_value(bet, "pnl", 0.0) or 0.0) for bet in settled_bets), 4)

    by_market = {}
    for market in sorted({_get_value(bet, "market", "") for bet in bets if _get_value(bet, "market", "")}):
        market_bets = [bet for bet in bets if _get_value(bet, "market") == market]
        market_settled = [bet for bet in market_bets if _get_value(bet, "result") in {"WIN", "LOSS", "PUSH"}]
        market_graded = [bet for bet in market_settled if not _get_value(bet, "push", False)]
        market_staked = round(sum(stake_amount(bet) for bet in market_settled), 4)
        market_pnl = round(sum(float(_get_value(bet, "pnl", 0.0) or 0.0) for bet in market_settled), 4)
        market_clv = [_get_value(bet, "clv") for bet in market_bets if _get_value(bet, "clv") is not None]
        by_market[market] = {
            "total_bets": len(market_bets),
            "settled_bets": len(market_settled),
            "wins": sum(1 for bet in market_settled if _get_value(bet, "won", False)),
            "pushes": sum(1 for bet in market_settled if _get_value(bet, "push", False)),
            "hit_rate": (
                sum(1 for bet in market_graded if _get_value(bet, "won", False)) / len(market_graded)
                if market_graded else 0.0
            ),
            "total_staked": market_staked,
            "total_pnl": market_pnl,
            "roi": (market_pnl / market_staked) if market_staked > 0 else 0.0,
            "avg_clv": (sum(market_clv) / len(market_clv)) if market_clv else 0.0,
        }

    return {
        "total_bets": len(bets),
        "settled_bets": len(settled_bets),
        "wins": sum(1 for bet in settled_bets if _get_value(bet, "won", False)),
        "pushes": sum(1 for bet in settled_bets if _get_value(bet, "push", False)),
        "hit_rate": (
            sum(1 for bet in graded_bets if _get_value(bet, "won", False)) / len(graded_bets)
            if graded_bets else 0.0
        ),
        "total_staked": total_staked,
        "total_pnl": total_pnl,
        "roi": (total_pnl / total_staked) if total_staked > 0 else 0.0,
        "avg_clv": (sum(clv_values) / len(clv_values)) if clv_values else 0.0,
        "by_market": by_market,
    }
