"""Backtest result analysis and comparison tool."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table

from config.settings import Config
from data.database import DatabaseManager

console = Console()


async def analyze_backtests():
    config = Config()

    console.print("[bold cyan]Football Prophet - Backtest Analyzer[/]\n")

    db = DatabaseManager(config.database_url)
    await db.init_db()

    try:
        # Fetch all backtest results
        async with db.session() as s:
            from sqlalchemy import select
            from data.models import BacktestResult
            stmt = select(BacktestResult).order_by(BacktestResult.created_at.desc()).limit(20)
            result = await s.execute(stmt)
            backtests = result.scalars().all()

        if not backtests:
            console.print("[yellow]No backtest results found. Run a backtest first.[/]")
            return

        table = Table(title="Backtest Results", show_header=True, header_style="bold")
        table.add_column("Run ID")
        table.add_column("League")
        table.add_column("Matches", justify="right")
        table.add_column("Accuracy", justify="right")
        table.add_column("Brier", justify="right")
        table.add_column("Bets", justify="right")
        table.add_column("Win Rate", justify="right")
        table.add_column("ROI", justify="right")
        table.add_column("P/L", justify="right")

        for bt in backtests:
            bet_wr = f"{bt.winning_bets/bt.total_bets:.0%}" if bt.total_bets else "N/A"
            roi_color = "green" if (bt.roi or 0) > 0 else "red"
            pl = bt.profit_loss or 0

            table.add_row(
                bt.run_id,
                bt.league_code or "?",
                str(bt.total_matches or 0),
                f"{bt.accuracy:.1%}" if bt.accuracy else "N/A",
                f"{bt.avg_brier_score:.4f}" if bt.avg_brier_score else "N/A",
                str(bt.total_bets or 0),
                bet_wr,
                f"[{roi_color}]{bt.roi:.1%}[/{roi_color}]" if bt.roi is not None else "N/A",
                f"[{roi_color}]{'+' if pl >= 0 else ''}{pl:.2f}[/{roi_color}]",
            )

        console.print(table)

        # Best/worst runs
        if len(backtests) > 1:
            best = max(backtests, key=lambda b: b.accuracy or 0)
            worst = min(backtests, key=lambda b: b.accuracy or 1)
            console.print(f"\n[green]Best accuracy:[/] {best.run_id} ({best.accuracy:.1%})")
            console.print(f"[red]Worst accuracy:[/] {worst.run_id} ({worst.accuracy:.1%})")

            if any(b.roi for b in backtests):
                best_roi = max(backtests, key=lambda b: b.roi or -999)
                console.print(f"[green]Best ROI:[/] {best_roi.run_id} ({best_roi.roi:.1%})")

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(analyze_backtests())
