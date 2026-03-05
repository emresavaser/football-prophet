"""CLI command handlers."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from bot.core import FootballProphet
from config.settings import Config
from config.leagues import LEAGUES, get_all_league_codes
from .formatter import CLIFormatter, console


class CLICommands:
    """High-level CLI command implementations."""

    def __init__(self, config: Config):
        self.config = config
        self.formatter = CLIFormatter()

    async def _warmup_brain_with_real_data(self, prophet: FootballProphet, league_code: str) -> None:
        """Warm up brain by fetching historical matches from the real API or TheSportsDB."""
        console.print(f"[dim]Fetching historical data for {league_code}...[/]")

        past_matches = []
        tsdb_adapter = None
        try:
            if prophet.data_source:
                past_matches = await prophet.data_source.fetch_matches(league_code)

            # Fallback to TheSportsDB if no data_source or no results
            if not past_matches:
                from data_sources.thesportsdb import TheSportsDBAdapter
                tsdb_adapter = TheSportsDBAdapter()
                past_matches = await tsdb_adapter.fetch_matches(league_code)
        except Exception as e:
            console.print(f"[dim]Could not fetch history for {league_code}: {e}[/]")
            return
        finally:
            if tsdb_adapter:
                await tsdb_adapter.close()

        finished = [m for m in past_matches if m.status == "FINISHED" and m.home_score is not None]
        if not finished:
            return

        console.print(f"[dim]Warming up brain with {len(finished)} historical matches for {league_code}...[/]")

        for rm in finished:
            home_team = await prophet.db.upsert_team(name=rm.home_team, league_code=league_code)
            away_team = await prophet.db.upsert_team(name=rm.away_team, league_code=league_code)

            await prophet.db.upsert_match(
                external_id=rm.external_id,
                league_code=league_code,
                season=rm.season,
                matchday=rm.matchday,
                match_date=rm.match_date,
                status=rm.status,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                home_score=rm.home_score,
                away_score=rm.away_score,
            )

            prophet.memory.update_after_match(
                home_team.id, away_team.id,
                rm.home_score, rm.away_score,
                league_code,
            )

            elo_model = prophet.ensemble.models.get("elo")
            if elo_model and hasattr(elo_model, "update_ratings"):
                elo_model.update_ratings(home_team.id, away_team.id, rm.home_score, rm.away_score)

        prophet.strength_calc.update_all(league_code)

        for team_id, profile in prophet.memory.team_profiles.items():
            results = profile.last_5_results
            if results:
                pts = sum(3 if r == "W" else 1 if r == "D" else 0 for r in results)
                profile.form_score = pts / (len(results) * 3)

        league_avg = prophet.memory.get_league_avg(league_code)
        console.print(
            f"[dim]Brain ready for {league_code}: "
            f"avg {league_avg.avg_goals_per_match:.2f} goals/match, "
            f"home win {league_avg.home_win_pct:.0%}[/]"
        )

    async def _warmup_brain_with_demo(self, prophet: FootballProphet, league_code: str) -> None:
        """Warm up brain memory by processing past demo matches."""
        from data_sources.demo_provider import DemoDataProvider
        from analysis.indicators.team_strength import TeamStrengthCalculator

        demo = DemoDataProvider()
        past_matches = await demo.fetch_matches(league_code)

        console.print(f"[dim]Warming up brain with {len(past_matches)} historical matches...[/]")

        for rm in past_matches:
            if rm.status != "FINISHED" or rm.home_score is None:
                continue

            # Upsert teams
            home_team = await prophet.db.upsert_team(name=rm.home_team, league_code=league_code)
            away_team = await prophet.db.upsert_team(name=rm.away_team, league_code=league_code)

            # Upsert match
            await prophet.db.upsert_match(
                external_id=rm.external_id,
                league_code=league_code,
                season=rm.season,
                matchday=rm.matchday,
                match_date=rm.match_date,
                status=rm.status,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                home_score=rm.home_score,
                away_score=rm.away_score,
            )

            # Update brain memory
            prophet.memory.update_after_match(
                home_team.id, away_team.id,
                rm.home_score, rm.away_score,
                league_code,
            )

            # Update ELO
            elo_model = prophet.ensemble.models.get("elo")
            if elo_model and hasattr(elo_model, "update_ratings"):
                elo_model.update_ratings(home_team.id, away_team.id, rm.home_score, rm.away_score)

            # Save odds
            odds_data = demo.get_odds(rm.external_id)
            if odds_data:
                await prophet.db.save_odds(
                    match_id=(await prophet.db.upsert_match(external_id=rm.external_id)).id,
                    home_win=odds_data.get("home_win"),
                    draw=odds_data.get("draw"),
                    away_win=odds_data.get("away_win"),
                    over_25=odds_data.get("over_25"),
                    under_25=odds_data.get("under_25"),
                )

        # Update team strengths
        prophet.strength_calc.update_all(league_code)

        # Update form scores
        for team_id, profile in prophet.memory.team_profiles.items():
            results = profile.last_5_results
            if results:
                pts = sum(3 if r == "W" else 1 if r == "D" else 0 for r in results)
                profile.form_score = pts / (len(results) * 3)

        teams_count = len(prophet.memory.team_profiles)
        league_avg = prophet.memory.get_league_avg(league_code)
        console.print(
            f"[dim]Brain ready: {teams_count} teams, "
            f"avg {league_avg.avg_goals_per_match:.2f} goals/match, "
            f"home win {league_avg.home_win_pct:.0%}[/]\n"
        )

    async def predict_league(self, league_code: str, demo: bool = False) -> None:
        """Generate predictions for upcoming matches in a league."""
        prophet = FootballProphet(self.config)
        await prophet.initialize()

        try:
            if demo:
                from data_sources.demo_provider import DemoDataProvider

                # Warm up brain with past data
                await self._warmup_brain_with_demo(prophet, league_code)

                # Get upcoming demo matches
                demo_source = DemoDataProvider()
                upcoming_raw = await demo_source.fetch_upcoming_matches(league_code)

                league_name = LEAGUES.get(league_code)
                display_name = league_name.name if league_name else league_code
                console.print(f"[bold cyan]Predictions for {display_name} (Demo Mode)[/]\n")

                predictions = []
                value_bets_all = []
                for rm in upcoming_raw:
                    home_team = await prophet.db.upsert_team(name=rm.home_team, league_code=league_code)
                    away_team = await prophet.db.upsert_team(name=rm.away_team, league_code=league_code)

                    match = await prophet.db.upsert_match(
                        external_id=rm.external_id,
                        league_code=league_code,
                        season=rm.season,
                        match_date=rm.match_date,
                        status="SCHEDULED",
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                    )

                    # Get demo odds
                    odds_dict = demo_source.get_odds(rm.external_id) or {}

                    prediction, value_bets = await prophet.prediction_manager.predict_match(
                        match_id=match.id,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        league_code=league_code,
                        odds=odds_dict,
                        home_team_name=rm.home_team,
                        away_team_name=rm.away_team,
                    )

                    predictions.append({
                        "home_team": rm.home_team,
                        "away_team": rm.away_team,
                        "predicted_outcome": prediction.predicted_outcome,
                        "most_likely_score": prediction.most_likely_score,
                        "home_win_prob": prediction.home_win_prob,
                        "draw_prob": prediction.draw_prob,
                        "away_win_prob": prediction.away_win_prob,
                        "confidence": prediction.confidence,
                        "is_value_bet": len(value_bets) > 0,
                    })

                    for vb in value_bets:
                        value_bets_all.append({
                            "home_team": rm.home_team,
                            "away_team": rm.away_team,
                            "market": vb.market,
                            "odds": vb.odds,
                            "model_prob": vb.model_prob,
                            "fair_prob": vb.fair_prob,
                            "implied_prob": vb.implied_prob,
                            "edge": vb.edge,
                            "ev": vb.ev,
                            "kelly_stake": vb.kelly_stake,
                        })

                self.formatter.prediction_table(predictions)

                if value_bets_all:
                    console.print()
                    self.formatter.value_bet_table(value_bets_all)

                # Show model weights
                console.print(f"\n[bold]Ensemble Weights:[/]")
                for name, w in sorted(prophet.ensemble.weights.items(), key=lambda x: x[1], reverse=True):
                    bar = "#" * int(w * 40)
                    console.print(f"  [cyan]{name:10s}[/] {w:.3f} [green]{bar}[/]")

            else:
                if not prophet.scheduler:
                    console.print("[red]No data source configured. Set API keys in .env or use --demo[/]")
                    return

                league_name = LEAGUES.get(league_code)
                display_name = league_name.name if league_name else league_code

                # Warm up brain with historical data if team profiles are sparse
                league_teams = [
                    tid for tid, p in prophet.memory.team_profiles.items()
                    if p.league_code == league_code and len(p.last_5_results) > 0
                ]
                if len(league_teams) < 6:
                    await self._warmup_brain_with_real_data(prophet, league_code)

                console.print(f"[cyan]Scanning {display_name} matches...[/]")
                upcoming = await prophet.scheduler.scan_upcoming(days_ahead=7)

                league_matches = [m for m in upcoming if m["league_code"] == league_code]
                if not league_matches:
                    console.print("[yellow]No upcoming matches found.[/]")
                    return

                predictions = []
                for match_info in league_matches:
                    prediction, value_bets = await prophet.prediction_manager.predict_match(
                        match_id=match_info["match_id"],
                        home_team_id=match_info["home_team_id"],
                        away_team_id=match_info["away_team_id"],
                        league_code=match_info["league_code"],
                        home_team_name=match_info["home_team"],
                        away_team_name=match_info["away_team"],
                    )
                    predictions.append({
                        "home_team": match_info["home_team"],
                        "away_team": match_info["away_team"],
                        "predicted_outcome": prediction.predicted_outcome,
                        "most_likely_score": prediction.most_likely_score,
                        "home_win_prob": prediction.home_win_prob,
                        "draw_prob": prediction.draw_prob,
                        "away_win_prob": prediction.away_win_prob,
                        "confidence": prediction.confidence,
                        "is_value_bet": len(value_bets) > 0,
                    })

                self.formatter.prediction_table(predictions)

        finally:
            await prophet.shutdown()

    async def run_backtest(
        self,
        league_code: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        demo: bool = False,
    ) -> None:
        """Run historical backtest."""
        prophet = FootballProphet(self.config)
        await prophet.initialize()

        try:
            if demo:
                # Seed DB with demo data first
                await self._warmup_brain_with_demo(prophet, league_code)
                console.print(f"[cyan]Running backtest for {league_code} (Demo Mode)...[/]")
            else:
                # Warmup brain with real data (TheSportsDB or configured API)
                await self._warmup_brain_with_real_data(prophet, league_code)
                console.print(f"[cyan]Running backtest for {league_code}...[/]")

            dt_from = datetime.fromisoformat(from_date) if from_date else None
            dt_to = datetime.fromisoformat(to_date) if to_date else None

            result = await prophet.backtest_engine.run_backtest(
                league_code=league_code,
                date_from=dt_from,
                date_to=dt_to,
            )

            self.formatter.backtest_report(result)

        finally:
            await prophet.shutdown()

    async def run_risk_report(
        self,
        league_code: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        demo: bool = False,
    ) -> None:
        """Run backtest and display comprehensive risk report."""
        prophet = FootballProphet(self.config)
        await prophet.initialize()

        try:
            if demo:
                await self._warmup_brain_with_demo(prophet, league_code)
                console.print(f"[cyan]Running risk analysis for {league_code} (Demo Mode)...[/]")
            else:
                console.print(f"[cyan]Running risk analysis for {league_code}...[/]")

            dt_from = datetime.fromisoformat(from_date) if from_date else None
            dt_to = datetime.fromisoformat(to_date) if to_date else None

            result = await prophet.backtest_engine.run_backtest(
                league_code=league_code,
                date_from=dt_from,
                date_to=dt_to,
            )

            self.formatter.risk_report(result)

        finally:
            await prophet.shutdown()

    async def run_collect(
        self,
        league_code: str,
        seasons: Optional[list[str]] = None,
    ) -> None:
        """Collect historical data from TheSportsDB."""
        from data_sources.thesportsdb import TheSportsDBAdapter
        from data_sources.historical_collector import HistoricalDataCollector
        from data.database import DatabaseManager

        config = self.config
        db = DatabaseManager(config.database_url)
        await db.init_db()

        adapter = TheSportsDBAdapter()
        collector = HistoricalDataCollector(db=db, adapter=adapter)

        try:
            if league_code.upper() == "ALL":
                codes = get_all_league_codes()
            else:
                codes = [league_code.upper()]

            console.print(f"[bold cyan]Collecting historical data...[/]")
            console.print(f"[dim]Leagues: {', '.join(codes)}[/]")
            if seasons:
                console.print(f"[dim]Seasons: {', '.join(seasons)}[/]")

            await collector.collect(league_codes=codes, seasons=seasons)

        finally:
            await collector.close()
            await db.close()

    async def run_full_backtest(
        self,
        league_code: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        seasons: Optional[list[str]] = None,
    ) -> None:
        """Full pipeline: collect real data -> train brain -> backtest."""
        from data_sources.thesportsdb import TheSportsDBAdapter
        from data_sources.historical_collector import HistoricalDataCollector

        prophet = FootballProphet(self.config)
        await prophet.initialize()

        adapter = TheSportsDBAdapter()
        collector = HistoricalDataCollector(db=prophet.db, adapter=adapter)

        try:
            lc = league_code.upper()
            league_info = LEAGUES.get(lc)
            display_name = league_info.name if league_info else lc

            # Step 1: Collect data
            console.print(f"[bold cyan]Step 1/3: Collecting real data for {display_name}...[/]")
            await collector.collect(league_codes=[lc], seasons=seasons)

            # Step 2: Train brain with real data
            console.print(f"\n[bold cyan]Step 2/3: Training brain with real data...[/]")
            await self._warmup_brain_with_real_data(prophet, lc)

            # Step 3: Run backtest
            console.print(f"\n[bold cyan]Step 3/3: Running backtest...[/]")
            dt_from = datetime.fromisoformat(from_date) if from_date else None
            dt_to = datetime.fromisoformat(to_date) if to_date else None

            result = await prophet.backtest_engine.run_backtest(
                league_code=lc,
                date_from=dt_from,
                date_to=dt_to,
            )

            self.formatter.backtest_report(result)

        finally:
            await collector.close()
            await prophet.shutdown()

    async def show_value_bets(self) -> None:
        """Show current value bets."""
        prophet = FootballProphet(self.config)
        await prophet.initialize()

        try:
            value_preds = await prophet.db.get_value_bets(upcoming_only=True)

            value_bets = []
            for pred in value_preds:
                match = await prophet.db.get_match(pred.match_id)
                if not match:
                    continue

                home_team = await prophet.db.get_team(match.home_team_id)
                away_team = await prophet.db.get_team(match.away_team_id)

                value_bets.append({
                    "home_team": home_team.name if home_team else "?",
                    "away_team": away_team.name if away_team else "?",
                    "market": pred.value_bet_market,
                    "odds": 0,
                    "model_prob": pred.home_win_prob if pred.value_bet_market == "home_win" else pred.away_win_prob,
                    "implied_prob": 0,
                    "edge": pred.edge or 0,
                    "ev": pred.ev or 0,
                    "kelly_stake": pred.kelly_stake or 0,
                })

            self.formatter.value_bet_table(value_bets)

        finally:
            await prophet.shutdown()

    async def show_status(self) -> None:
        """Show bot status."""
        prophet = FootballProphet(self.config)
        await prophet.initialize()

        try:
            self.formatter.status_panel(prophet.state.to_dict())

            # Model accuracy
            accuracy = await prophet.db.get_model_accuracy(days=30)
            console.print(f"\n[bold]30-Day Accuracy:[/] {accuracy['accuracy']:.1%} "
                          f"({accuracy['correct']}/{accuracy['total']})")
            console.print(f"[bold]Avg Brier Score:[/] {accuracy['avg_brier']:.4f}")

            # Brain info
            brain_info = prophet.persistence.get_state_info()
            console.print(f"\n[bold]Brain State:[/] "
                          f"{'Loaded' if brain_info['exists'] else 'Fresh'} "
                          f"({brain_info.get('size_bytes', 0) / 1024:.1f} KB, "
                          f"{brain_info.get('backups', 0)} backups)")

        finally:
            await prophet.shutdown()
