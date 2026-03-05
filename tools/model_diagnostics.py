"""Model performance diagnostics and analysis."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table

from config.settings import Config
from brain.persistence import BrainPersistence

console = Console()


async def run_diagnostics():
    config = Config()

    console.print("[bold cyan]Football Prophet - Model Diagnostics[/]\n")

    # Load brain
    persistence = BrainPersistence(config.brain_state_dir)
    loaded = persistence.load()

    if not loaded:
        console.print("[yellow]No brain state found. Run the bot first to build data.[/]")
        return

    state, memory, learner = loaded

    # Model weights
    console.print("[bold]Current Model Weights:[/]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Model", min_width=12)
    table.add_column("Weight", justify="right")
    table.add_column("Bar", min_width=30)

    for name, w in sorted(learner.model_weights.items(), key=lambda x: x[1], reverse=True):
        bar = "[green]" + "#" * int(w * 50) + "[/]"
        table.add_row(name, f"{w:.3f}", bar)

    console.print(table)

    # Per-model performance
    perf = learner.get_model_performance()
    if perf:
        console.print("\n[bold]Model Performance:[/]")
        perf_table = Table(show_header=True, header_style="bold")
        perf_table.add_column("Model")
        perf_table.add_column("Avg Brier", justify="right")
        perf_table.add_column("Best Brier", justify="right")
        perf_table.add_column("Worst Brier", justify="right")
        perf_table.add_column("Predictions", justify="right")

        for name, p in perf.items():
            perf_table.add_row(
                name,
                f"{p['avg_brier']:.4f}",
                f"{p['best_brier']:.4f}",
                f"{p['worst_brier']:.4f}",
                str(p['total_predictions']),
            )

        console.print(perf_table)

    # Calibration
    calibration = learner.get_calibration_curve()
    if calibration:
        console.print("\n[bold]Calibration Curve (predicted confidence → actual accuracy):[/]")
        cal_table = Table(show_header=True, header_style="bold")
        cal_table.add_column("Confidence Bin", justify="center")
        cal_table.add_column("Actual Accuracy", justify="right")
        cal_table.add_column("Calibration", justify="center")

        for bin_key, actual in sorted(calibration.items()):
            predicted = float(bin_key)
            diff = actual - predicted
            if abs(diff) < 0.05:
                status = "[green]Good[/]"
            elif diff > 0:
                status = "[yellow]Under-confident[/]"
            else:
                status = "[red]Over-confident[/]"

            cal_table.add_row(bin_key, f"{actual:.1%}", status)

        console.print(cal_table)

    # Memory stats
    console.print(f"\n[bold]Memory Stats:[/]")
    console.print(f"  Teams tracked: {len(memory.team_profiles)}")
    console.print(f"  Leagues tracked: {len(memory.league_averages)}")
    console.print(f"  H2H pairs: {len(memory.h2h_cache)}")
    console.print(f"  Total predictions: {learner.total_predictions}")
    console.print(f"  Overall Brier: {learner.overall_brier:.4f}")

    # State
    console.print(f"\n[bold]Runtime State:[/]")
    console.print(f"  Active predictions: {len(state.active_predictions)}")
    console.print(f"  Scanned: {state.scan_stats.matches_scanned}")
    console.print(f"  Predicted: {state.scan_stats.predictions_made}")
    console.print(f"  Value bets: {state.scan_stats.value_bets_found}")

    # Model health
    console.print(f"\n[bold]Model Health:[/]")
    for name, health in state.model_health.items():
        streak = health.streak
        streak_str = f"+{streak}" if streak > 0 else str(streak)
        error = f" [red]err={health.last_error}[/]" if health.last_error else ""
        console.print(
            f"  {name:10s} acc={health.accuracy:.1%} "
            f"({health.correct_predictions}/{health.total_predictions}) "
            f"streak={streak_str}{error}"
        )


if __name__ == "__main__":
    asyncio.run(run_diagnostics())
