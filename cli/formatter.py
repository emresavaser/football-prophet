"""Rich table formatters for CLI output."""

from __future__ import annotations

import io
import sys
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

# Force UTF-8 output to avoid cp1254 encoding errors on Turkish Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console(force_terminal=True)


class CLIFormatter:
    """Rich formatting utilities for CLI output."""

    @staticmethod
    def prediction_table(predictions: list[dict]) -> None:
        """Display predictions in a rich table."""
        table = Table(
            title="Match Predictions",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Match", style="white", min_width=30)
        table.add_column("Pred", style="bold", justify="center")
        table.add_column("Score", justify="center")
        table.add_column("H%", justify="right", style="green")
        table.add_column("D%", justify="right", style="yellow")
        table.add_column("A%", justify="right", style="red")
        table.add_column("Conf", justify="right")
        table.add_column("Value", justify="center")

        for p in predictions:
            outcome = p.get("predicted_outcome", "?")
            color = {"HOME": "green", "DRAW": "yellow", "AWAY": "red"}.get(outcome, "white")
            is_value = "[bold green]YES[/]" if p.get("is_value_bet") else "[dim]no[/]"

            table.add_row(
                f"{p.get('home_team', '?')} vs {p.get('away_team', '?')}",
                f"[{color}]{outcome}[/{color}]",
                p.get("most_likely_score", "?-?"),
                f"{p.get('home_win_prob', 0):.0%}",
                f"{p.get('draw_prob', 0):.0%}",
                f"{p.get('away_win_prob', 0):.0%}",
                f"{p.get('confidence', 0):.0%}",
                is_value,
            )

        console.print(table)

    @staticmethod
    def value_bet_table(value_bets: list[dict]) -> None:
        """Display value bets with Fair% column."""
        if not value_bets:
            console.print("[yellow]No value bets found.[/]")
            return

        table = Table(
            title="Value Bets",
            show_header=True,
            header_style="bold green",
        )
        table.add_column("Match", style="white", min_width=25)
        table.add_column("Market", justify="center")
        table.add_column("Odds", justify="right")
        table.add_column("Model%", justify="right", style="cyan")
        table.add_column("Fair%", justify="right", style="magenta")
        table.add_column("Imp%", justify="right", style="dim")
        table.add_column("Edge", justify="right", style="bold green")
        table.add_column("EV", justify="right", style="bold")
        table.add_column("Kelly%", justify="right")

        for vb in value_bets:
            fair_prob = vb.get("fair_prob", vb.get("implied_prob", 0))
            table.add_row(
                f"{vb.get('home_team', '?')} vs {vb.get('away_team', '?')}",
                vb.get("market", "?"),
                f"{vb.get('odds', 0):.2f}",
                f"{vb.get('model_prob', 0):.1%}",
                f"{fair_prob:.1%}",
                f"{vb.get('implied_prob', 0):.1%}",
                f"+{vb.get('edge', 0):.1%}",
                f"+{vb.get('ev', 0):.3f}",
                f"{vb.get('kelly_stake', 0):.1%}",
            )

        console.print(table)

    @staticmethod
    def backtest_report(result: dict) -> None:
        """Display backtest results with drawdown and MC metrics."""
        console.print(Panel(
            f"[bold]Backtest Report[/] - Run ID: {result.get('run_id', '?')}",
            style="blue",
        ))

        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan", min_width=20)
        table.add_column("Value", style="white")

        rows = [
            ("League", result.get("league_code", "?")),
            ("Period", f"{result.get('date_from', '?')} -> {result.get('date_to', '?')}"),
            ("Total Matches", str(result.get("total_matches", 0))),
            ("Predicted", str(result.get("predicted_matches", 0))),
            ("Correct", str(result.get("correct_predictions", 0))),
            ("Accuracy", f"{result.get('accuracy', 0):.1%}"),
            ("Avg Brier Score", f"{result.get('avg_brier_score', 0):.4f}"),
            ("Value Bets", str(result.get("value_bets", 0))),
            ("Winning Bets", str(result.get("winning_bets", 0))),
            ("Settled Bets", str(result.get("settled_bets", 0))),
            ("Hit Rate", f"{result.get('hit_rate', 0):.1%}"),
            ("Total Staked", f"{result.get('total_staked', 0):.2f}"),
            ("P/L", f"{'+'if result.get('profit_loss',0)>=0 else ''}{result.get('profit_loss', 0):.2f}"),
            ("ROI", f"{result.get('roi', 0):.1%}"),
            ("Avg CLV", f"{result.get('avg_clv', 0):.2%}"),
            ("Final Bankroll", f"{result.get('final_bankroll', 0):.2f}"),
        ]

        # Drawdown metrics
        max_dd = result.get("max_drawdown", 0)
        if max_dd > 0:
            rows.append(("Max Drawdown", f"{max_dd:.1%}"))
        dd_halts = result.get("drawdown_halts", 0)
        if dd_halts > 0:
            rows.append(("Drawdown Halts", str(dd_halts)))

        for metric, value in rows:
            table.add_row(metric, value)

        console.print(table)

        # Model weights
        weights = result.get("model_weights_final", {})
        if weights:
            console.print("\n[bold]Final Model Weights:[/]")
            for name, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
                bar = "[green]" + "#" * int(w * 50) + "[/]"
                console.print(f"  {name:10s} {w:.3f} {bar}")

        market_breakdown = result.get("value_bets_by_market", {})
        if market_breakdown:
            console.print("\n[bold]Market Breakdown:[/]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Market", style="cyan")
            table.add_column("Bets", justify="right")
            table.add_column("Wins", justify="right")
            table.add_column("Hit Rate", justify="right")
            table.add_column("Staked", justify="right")
            table.add_column("P/L", justify="right")
            table.add_column("ROI", justify="right")
            table.add_column("Avg CLV", justify="right")

            for market, stats in market_breakdown.items():
                table.add_row(
                    market,
                    str(stats.get("total_bets", 0)),
                    str(stats.get("wins", 0)),
                    f"{stats.get('hit_rate', 0):.1%}",
                    f"{stats.get('total_staked', 0):.2f}",
                    f"{stats.get('total_pnl', 0):+.2f}",
                    f"{stats.get('roi', 0):.1%}",
                    f"{stats.get('avg_clv', 0):.2%}",
                )
            console.print(table)

        # Monte Carlo results
        mc = result.get("monte_carlo")
        if mc:
            CLIFormatter.monte_carlo_table(mc)

        # Slippage stats
        slip = result.get("slippage_stats")
        if slip:
            console.print("\n[bold]Slippage Stats:[/]")
            console.print(f"  Avg Slippage: {slip.get('avg_slippage_bps', 0):.1f} bps")
            console.print(f"  No-Fill Rate: {slip.get('p_no_fill', 0):.1%}")
            console.print(f"  Fills: {slip.get('n_fills', 0)}/{slip.get('n_total', 0)}")

    @staticmethod
    def monte_carlo_table(mc: dict) -> None:
        """Display Monte Carlo ruin simulation results."""
        console.print("\n")
        table = Table(
            title="Monte Carlo Ruin Simulation",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Metric", style="cyan", min_width=25)
        table.add_column("Value", style="white", justify="right")

        p_ruin = mc.get("p_ruin", 0)
        ruin_color = "green" if p_ruin < 0.05 else "yellow" if p_ruin < 0.15 else "red"

        table.add_row("Ruin Probability", f"[{ruin_color}]{p_ruin:.2%}[/{ruin_color}]")
        table.add_row("Simulated Paths", str(mc.get("n_paths", 0)))
        table.add_row("Bets per Path", str(mc.get("n_bets_per_path", 0)))
        table.add_row("Mean Terminal Equity", f"{mc.get('mean_terminal_equity', 0):,.2f}")
        table.add_row("Median Terminal Equity", f"{mc.get('median_terminal_equity', 0):,.2f}")
        table.add_row("P1 Terminal Equity", f"{mc.get('p1_terminal_equity', 0):,.2f}")
        table.add_row("P5 Terminal Equity", f"{mc.get('p5_terminal_equity', 0):,.2f}")
        table.add_row("P95 Terminal Equity", f"{mc.get('p95_terminal_equity', 0):,.2f}")

        console.print(table)

    @staticmethod
    def risk_report(result: dict) -> None:
        """Display comprehensive risk report."""
        console.print(Panel(
            "[bold]Risk Analysis Report[/]",
            style="magenta",
        ))

        # Backtest summary
        CLIFormatter.backtest_report(result)

        # Guard state
        guard = result.get("guard_final")
        if guard:
            console.print("\n[bold]DrawdownGuard Final State:[/]")
            console.print(f"  Equity: {guard.get('equity', 0):,.2f}")
            console.print(f"  Peak: {guard.get('peak', 0):,.2f}")
            console.print(f"  Current DD: {guard.get('dd', 0):.2%}")
            console.print(f"  Stake Multiplier: {guard.get('stake_multiplier', 1):.2f}")

    @staticmethod
    def status_panel(state_dict: dict) -> None:
        """Display bot status."""
        stats = state_dict.get("scan_stats", {})
        health = state_dict.get("model_health", {})

        table = Table(title="Prophet Status", show_header=True, header_style="bold")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="white")

        table.add_row("Active Predictions", str(len(state_dict.get("active_predictions", {}))))
        table.add_row("Matches Scanned", str(stats.get("matches_scanned", 0)))
        table.add_row("Predictions Made", str(stats.get("predictions_made", 0)))
        table.add_row("Value Bets Found", str(stats.get("value_bets_found", 0)))

        console.print(table)

        if health:
            console.print("\n[bold]Model Health:[/]")
            for name, h in health.items():
                acc = h.get("accuracy", 0)
                total = h.get("total", 0)
                streak = h.get("streak", 0)
                streak_str = f"+{streak}" if streak > 0 else str(streak)
                console.print(f"  {name:10s} acc={acc:.1%} total={total} streak={streak_str}")
