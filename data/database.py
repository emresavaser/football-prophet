"""Database manager with async SQLAlchemy session handling."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import select, and_, func, Integer
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from .models import Base, Team, Match, Odds, Prediction, BacktestResult, ValueBet


class DatabaseManager:
    """Async SQLite database manager for Football Prophet."""

    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    def session(self) -> AsyncSession:
        return self.session_factory()

    # ── Team CRUD ──────────────────────────────────────────────

    async def upsert_team(self, name: str, league_code: str, **kwargs) -> Team:
        async with self.session() as s:
            stmt = select(Team).where(
                and_(Team.name == name, Team.league_code == league_code)
            )
            result = await s.execute(stmt)
            team = result.scalar_one_or_none()
            if team:
                for k, v in kwargs.items():
                    if hasattr(team, k) and v is not None:
                        setattr(team, k, v)
            else:
                team = Team(name=name, league_code=league_code, **kwargs)
                s.add(team)
            await s.commit()
            await s.refresh(team)
            return team

    async def get_team(self, team_id: int) -> Optional[Team]:
        async with self.session() as s:
            return await s.get(Team, team_id)

    async def get_team_by_name(self, name: str, league_code: str) -> Optional[Team]:
        async with self.session() as s:
            stmt = select(Team).where(
                and_(Team.name == name, Team.league_code == league_code)
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def get_teams_by_league(self, league_code: str) -> Sequence[Team]:
        async with self.session() as s:
            stmt = select(Team).where(Team.league_code == league_code).order_by(Team.name)
            result = await s.execute(stmt)
            return result.scalars().all()

    # ── Match CRUD ─────────────────────────────────────────────

    async def upsert_match(self, external_id: str, **kwargs) -> Match:
        async with self.session() as s:
            stmt = select(Match).where(Match.external_id == external_id)
            result = await s.execute(stmt)
            match = result.scalar_one_or_none()
            if match:
                for k, v in kwargs.items():
                    if hasattr(match, k) and v is not None:
                        setattr(match, k, v)
            else:
                match = Match(external_id=external_id, **kwargs)
                s.add(match)
            await s.commit()
            await s.refresh(match)
            return match

    async def get_match(self, match_id: int) -> Optional[Match]:
        async with self.session() as s:
            return await s.get(Match, match_id)

    async def get_match_by_external_id(self, external_id: str) -> Optional[Match]:
        async with self.session() as s:
            stmt = select(Match).where(Match.external_id == external_id)
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def get_upcoming_matches(
        self, league_code: Optional[str] = None, days_ahead: int = 7
    ) -> Sequence[Match]:
        async with self.session() as s:
            now = datetime.utcnow()
            end = now + timedelta(days=days_ahead)
            conditions = [
                Match.match_date >= now,
                Match.match_date <= end,
                Match.status == "SCHEDULED",
            ]
            if league_code:
                conditions.append(Match.league_code == league_code)
            stmt = select(Match).where(and_(*conditions)).order_by(Match.match_date)
            result = await s.execute(stmt)
            return result.scalars().all()

    async def get_team_matches(
        self,
        team_id: int,
        limit: int = 20,
        finished_only: bool = True,
    ) -> Sequence[Match]:
        async with self.session() as s:
            conditions = [
                (Match.home_team_id == team_id) | (Match.away_team_id == team_id)
            ]
            if finished_only:
                conditions.append(Match.status == "FINISHED")
            stmt = (
                select(Match)
                .where(and_(*conditions))
                .order_by(Match.match_date.desc())
                .limit(limit)
            )
            result = await s.execute(stmt)
            return result.scalars().all()

    async def get_h2h_matches(
        self, team1_id: int, team2_id: int, limit: int = 10
    ) -> Sequence[Match]:
        async with self.session() as s:
            stmt = (
                select(Match)
                .where(
                    and_(
                        Match.status == "FINISHED",
                        (
                            (Match.home_team_id == team1_id) & (Match.away_team_id == team2_id)
                        ) | (
                            (Match.home_team_id == team2_id) & (Match.away_team_id == team1_id)
                        ),
                    )
                )
                .order_by(Match.match_date.desc())
                .limit(limit)
            )
            result = await s.execute(stmt)
            return result.scalars().all()

    async def get_league_matches(
        self,
        league_code: str,
        season: Optional[str] = None,
        finished_only: bool = True,
    ) -> Sequence[Match]:
        async with self.session() as s:
            conditions = [Match.league_code == league_code]
            if season:
                conditions.append(Match.season == season)
            if finished_only:
                conditions.append(Match.status == "FINISHED")
            stmt = select(Match).where(and_(*conditions)).order_by(Match.match_date)
            result = await s.execute(stmt)
            return result.scalars().all()

    async def get_finished_unscored(self) -> Sequence[Match]:
        """Matches finished but no prediction result yet."""
        async with self.session() as s:
            subq = select(Prediction.match_id).where(Prediction.is_correct.isnot(None))
            stmt = (
                select(Match)
                .where(
                    and_(
                        Match.status == "FINISHED",
                        Match.home_score.isnot(None),
                        ~Match.id.in_(subq),
                    )
                )
            )
            result = await s.execute(stmt)
            return result.scalars().all()

    # ── Odds CRUD ──────────────────────────────────────────────

    async def save_odds(self, match_id: int, **kwargs) -> Odds:
        async with self.session() as s:
            odds = Odds(match_id=match_id, **kwargs)
            s.add(odds)
            await s.commit()
            await s.refresh(odds)
            return odds

    async def get_latest_odds(self, match_id: int) -> Optional[Odds]:
        async with self.session() as s:
            stmt = (
                select(Odds)
                .where(Odds.match_id == match_id)
                .order_by(Odds.timestamp.desc())
                .limit(1)
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def get_odds_history(self, match_id: int) -> Sequence[Odds]:
        async with self.session() as s:
            stmt = (
                select(Odds)
                .where(Odds.match_id == match_id)
                .order_by(Odds.timestamp.asc(), Odds.id.asc())
            )
            result = await s.execute(stmt)
            return result.scalars().all()

    # ── Prediction CRUD ────────────────────────────────────────

    async def save_prediction(self, **kwargs) -> Prediction:
        async with self.session() as s:
            pred = Prediction(**kwargs)
            s.add(pred)
            await s.commit()
            await s.refresh(pred)
            return pred

    async def get_predictions_for_match(self, match_id: int) -> Sequence[Prediction]:
        async with self.session() as s:
            stmt = (
                select(Prediction)
                .where(Prediction.match_id == match_id)
                .order_by(Prediction.created_at.desc())
            )
            result = await s.execute(stmt)
            return result.scalars().all()

    async def save_value_bets(self, prediction_id: int, match_id: int, value_bets: Sequence[dict]) -> Sequence[ValueBet]:
        async with self.session() as s:
            records = [
                ValueBet(
                    prediction_id=prediction_id,
                    match_id=match_id,
                    **payload,
                )
                for payload in value_bets
            ]
            s.add_all(records)
            await s.commit()
            for record in records:
                await s.refresh(record)
            return records

    async def get_value_bets_for_prediction(self, prediction_id: int) -> Sequence[ValueBet]:
        async with self.session() as s:
            stmt = (
                select(ValueBet)
                .where(ValueBet.prediction_id == prediction_id)
                .order_by(ValueBet.created_at.asc(), ValueBet.id.asc())
            )
            result = await s.execute(stmt)
            return result.scalars().all()

    async def get_pending_predictions(self) -> Sequence[Prediction]:
        """Return only the latest prediction per match (is_correct=None)."""
        async with self.session() as s:
            # Subquery: max prediction id per match
            latest = (
                select(func.max(Prediction.id).label("max_id"))
                .where(Prediction.is_correct.is_(None))
                .group_by(Prediction.match_id)
                .subquery()
            )
            stmt = select(Prediction).where(Prediction.id.in_(select(latest.c.max_id)))
            result = await s.execute(stmt)
            return result.scalars().all()

    async def update_prediction_result(
        self, prediction_id: int, outcome: str, is_correct: bool, brier: float
    ) -> None:
        async with self.session() as s:
            pred = await s.get(Prediction, prediction_id)
            if pred:
                pred.result_outcome = outcome
                pred.is_correct = is_correct
                pred.brier_score = brier
                await s.commit()

    async def get_value_bets(self, upcoming_only: bool = True) -> Sequence[ValueBet]:
        async with self.session() as s:
            conditions = []
            if upcoming_only:
                conditions.append(Prediction.is_correct.is_(None))
            stmt = (
                select(ValueBet)
                .join(Prediction, Prediction.id == ValueBet.prediction_id)
                .where(and_(*conditions))
                .order_by(ValueBet.edge.desc(), ValueBet.created_at.desc())
            )
            result = await s.execute(stmt)
            return result.scalars().all()

    async def update_value_bet_closing(
        self,
        value_bet_id: int,
        closing_odds: float,
        closing_implied_prob: float,
        clv: float,
    ) -> None:
        async with self.session() as s:
            value_bet = await s.get(ValueBet, value_bet_id)
            if value_bet:
                value_bet.closing_odds = closing_odds
                value_bet.closing_implied_prob = closing_implied_prob
                value_bet.clv = clv
                await s.commit()

    async def settle_value_bet(
        self,
        value_bet_id: int,
        *,
        result: str,
        won: bool,
        push: bool,
        pnl: float,
        settled_at: Optional[datetime] = None,
        closing_odds: Optional[float] = None,
        closing_implied_prob: Optional[float] = None,
        clv: Optional[float] = None,
    ) -> None:
        async with self.session() as s:
            value_bet = await s.get(ValueBet, value_bet_id)
            if value_bet:
                value_bet.result = result
                value_bet.won = won
                value_bet.push = push
                value_bet.pnl = pnl
                value_bet.settled_at = settled_at or datetime.utcnow()
                if closing_odds is not None:
                    value_bet.closing_odds = closing_odds
                if closing_implied_prob is not None:
                    value_bet.closing_implied_prob = closing_implied_prob
                if clv is not None:
                    value_bet.clv = clv
                await s.commit()

    # ── Backtest CRUD ──────────────────────────────────────────

    async def save_backtest_result(self, **kwargs) -> BacktestResult:
        async with self.session() as s:
            bt = BacktestResult(**kwargs)
            s.add(bt)
            await s.commit()
            await s.refresh(bt)
            return bt

    async def list_backtests(
        self,
        league_code: Optional[str] = None,
        limit: int = 20,
    ) -> Sequence[BacktestResult]:
        async with self.session() as s:
            conditions = []
            if league_code:
                conditions.append(BacktestResult.league_code == league_code)

            stmt = select(BacktestResult)
            if conditions:
                stmt = stmt.where(and_(*conditions))
            stmt = stmt.order_by(BacktestResult.created_at.desc(), BacktestResult.id.desc()).limit(limit)
            result = await s.execute(stmt)
            return result.scalars().all()

    async def get_backtest(self, run_id: str) -> Optional[BacktestResult]:
        async with self.session() as s:
            stmt = (
                select(BacktestResult)
                .where(BacktestResult.run_id == run_id)
                .order_by(BacktestResult.created_at.desc(), BacktestResult.id.desc())
                .limit(1)
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    # ── Stats ──────────────────────────────────────────────────

    async def get_model_accuracy(self, days: int = 30) -> dict:
        async with self.session() as s:
            since = datetime.utcnow() - timedelta(days=days)
            stmt = select(
                func.count(Prediction.id).label("total"),
                func.sum(func.cast(Prediction.is_correct, Integer)).label("correct"),
                func.avg(Prediction.brier_score).label("avg_brier"),
            ).where(
                and_(
                    Prediction.is_correct.isnot(None),
                    Prediction.created_at >= since,
                )
            )
            result = await s.execute(stmt)
            row = result.one()
            total = row.total or 0
            correct = row.correct or 0
            return {
                "total": total,
                "correct": correct,
                "accuracy": correct / total if total > 0 else 0.0,
                "avg_brier": float(row.avg_brier) if row.avg_brier else 0.0,
            }
