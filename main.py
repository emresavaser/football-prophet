"""Football Prophet - Professional Match Prediction System.

Usage:
    python main.py --mode predict --league PL --demo
    python main.py --mode predict --league PL
    python main.py --mode backtest --league PL --from-date 2024-01-01
    python main.py --mode risk-report --league PL --demo
    python main.py --mode collect --league PL
    python main.py --mode collect --league ALL --seasons 2023-2024,2024-2025
    python main.py --mode full-backtest --league PL
    python main.py --mode api --port 8000
    python main.py --mode daemon --notify-value-bets
    python main.py --mode status
    python main.py --mode value-bets
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Config
from config.leagues import get_all_league_codes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Football Prophet - Professional Match Prediction System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["predict", "backtest", "api", "daemon", "status", "value-bets", "risk-report", "collect", "full-backtest"],
        default="predict",
        help="Operation mode",
    )
    parser.add_argument("--league", type=str, default="PL", help="League code (PL, PD, SA, BL1, FL1, TSL)")
    parser.add_argument("--match-id", type=int, help="Specific match ID for prediction")
    parser.add_argument("--from-date", type=str, help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", type=str, help="Backtest end date (YYYY-MM-DD)")
    parser.add_argument("--port", type=int, default=8000, help="API server port")
    parser.add_argument("--notify-value-bets", action="store_true", help="Enable Telegram notifications")
    parser.add_argument("--demo", action="store_true", help="Use demo data (no API keys needed)")
    parser.add_argument("--seasons", type=str, default=None, help="Comma-separated seasons (e.g. 2023-2024,2024-2025)")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = Config()
    config.log_level = args.log_level

    if args.mode == "predict":
        from cli.commands import CLICommands
        cmd = CLICommands(config)
        asyncio.run(cmd.predict_league(args.league.upper(), demo=args.demo))

    elif args.mode == "backtest":
        from cli.commands import CLICommands
        cmd = CLICommands(config)
        asyncio.run(cmd.run_backtest(
            league_code=args.league.upper(),
            from_date=args.from_date,
            to_date=args.to_date,
            demo=args.demo,
        ))

    elif args.mode == "api":
        import uvicorn
        from api.app import create_app
        app = create_app(config)
        uvicorn.run(app, host="0.0.0.0", port=args.port)

    elif args.mode == "daemon":
        from bot.runner import run_daemon
        run_daemon(config)

    elif args.mode == "status":
        from cli.commands import CLICommands
        cmd = CLICommands(config)
        asyncio.run(cmd.show_status())

    elif args.mode == "value-bets":
        from cli.commands import CLICommands
        cmd = CLICommands(config)
        asyncio.run(cmd.show_value_bets())

    elif args.mode == "risk-report":
        from cli.commands import CLICommands
        cmd = CLICommands(config)
        asyncio.run(cmd.run_risk_report(
            league_code=args.league.upper(),
            from_date=args.from_date,
            to_date=args.to_date,
            demo=args.demo,
        ))

    elif args.mode == "collect":
        from cli.commands import CLICommands
        cmd = CLICommands(config)
        seasons = args.seasons.split(",") if args.seasons else None
        asyncio.run(cmd.run_collect(
            league_code=args.league.upper(),
            seasons=seasons,
        ))

    elif args.mode == "full-backtest":
        from cli.commands import CLICommands
        cmd = CLICommands(config)
        seasons = args.seasons.split(",") if args.seasons else None
        asyncio.run(cmd.run_full_backtest(
            league_code=args.league.upper(),
            from_date=args.from_date,
            to_date=args.to_date,
            seasons=seasons,
        ))


if __name__ == "__main__":
    main()
