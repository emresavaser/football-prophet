"""SQLAlchemy ORM models for Football Prophet."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text,
    ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    short_name = Column(String(50))
    league_code = Column(String(10), nullable=False, index=True)
    country = Column(String(100))
    external_id_fd = Column(Integer)       # football-data.org ID
    external_id_apif = Column(Integer)     # API-Football ID
    elo_rating = Column(Float, default=1500.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    home_matches = relationship("Match", foreign_keys="Match.home_team_id", back_populates="home_team")
    away_matches = relationship("Match", foreign_keys="Match.away_team_id", back_populates="away_team")

    __table_args__ = (
        UniqueConstraint("name", "league_code", name="uq_team_league"),
    )

    def __repr__(self) -> str:
        return f"<Team {self.name} ({self.league_code})>"


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(100), unique=True)
    league_code = Column(String(10), nullable=False, index=True)
    season = Column(String(10))                    # e.g. "2024-25"
    matchday = Column(Integer)
    match_date = Column(DateTime, nullable=False, index=True)
    status = Column(String(20), default="SCHEDULED")  # SCHEDULED, LIVE, FINISHED, POSTPONED

    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    home_score = Column(Integer)
    away_score = Column(Integer)
    home_ht_score = Column(Integer)
    away_ht_score = Column(Integer)

    # Stats
    home_shots = Column(Integer)
    away_shots = Column(Integer)
    home_shots_on_target = Column(Integer)
    away_shots_on_target = Column(Integer)
    home_possession = Column(Float)
    away_possession = Column(Float)
    home_corners = Column(Integer)
    away_corners = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_matches")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_matches")
    odds = relationship("Odds", back_populates="match", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="match", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_match_date_league", "match_date", "league_code"),
    )

    @property
    def result(self) -> Optional[str]:
        if self.home_score is None or self.away_score is None:
            return None
        if self.home_score > self.away_score:
            return "HOME"
        elif self.home_score < self.away_score:
            return "AWAY"
        return "DRAW"

    @property
    def total_goals(self) -> Optional[int]:
        if self.home_score is None or self.away_score is None:
            return None
        return self.home_score + self.away_score

    def __repr__(self) -> str:
        return f"<Match {self.home_team_id} vs {self.away_team_id} ({self.match_date})>"


class Odds(Base):
    __tablename__ = "odds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    bookmaker = Column(String(100), default="average")
    timestamp = Column(DateTime, default=datetime.utcnow)

    home_win = Column(Float)
    draw = Column(Float)
    away_win = Column(Float)

    over_25 = Column(Float)
    under_25 = Column(Float)

    btts_yes = Column(Float)
    btts_no = Column(Float)

    match = relationship("Match", back_populates="odds")

    @property
    def home_implied_prob(self) -> Optional[float]:
        return 1.0 / self.home_win if self.home_win else None

    @property
    def draw_implied_prob(self) -> Optional[float]:
        return 1.0 / self.draw if self.draw else None

    @property
    def away_implied_prob(self) -> Optional[float]:
        return 1.0 / self.away_win if self.away_win else None

    @property
    def bookmaker_margin(self) -> Optional[float]:
        if not all([self.home_win, self.draw, self.away_win]):
            return None
        return (1/self.home_win + 1/self.draw + 1/self.away_win) - 1.0

    def __repr__(self) -> str:
        return f"<Odds match={self.match_id} H={self.home_win} D={self.draw} A={self.away_win}>"


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Probabilities
    home_win_prob = Column(Float, nullable=False)
    draw_prob = Column(Float, nullable=False)
    away_win_prob = Column(Float, nullable=False)

    # Score prediction
    predicted_home_goals = Column(Float)
    predicted_away_goals = Column(Float)
    most_likely_score = Column(String(10))  # e.g. "2-1"

    # Over/Under
    over_25_prob = Column(Float)
    btts_prob = Column(Float)

    # Confidence & model info
    confidence = Column(Float, nullable=False)
    model_breakdown = Column(Text)  # JSON string of per-model predictions

    # Result tracking
    result_outcome = Column(String(10))   # HOME, DRAW, AWAY
    is_correct = Column(Boolean)
    brier_score = Column(Float)

    # Value bet info
    is_value_bet = Column(Boolean, default=False)
    value_bet_market = Column(String(20))  # "home_win", "draw", "away_win", etc.
    edge = Column(Float)
    kelly_stake = Column(Float)
    ev = Column(Float)

    match = relationship("Match", back_populates="predictions")
    value_bets = relationship("ValueBet", back_populates="prediction", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Prediction match={self.match_id} conf={self.confidence:.2f}>"


class ValueBet(Base):
    __tablename__ = "value_bets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    market = Column(String(20), nullable=False, index=True)
    model_prob = Column(Float, nullable=False)
    implied_prob = Column(Float, nullable=False)
    fair_prob = Column(Float)
    overround = Column(Float)
    odds = Column(Float, nullable=False)
    ev = Column(Float, nullable=False)
    edge = Column(Float, nullable=False, index=True)
    kelly_stake = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)

    closing_odds = Column(Float)
    closing_implied_prob = Column(Float)
    clv = Column(Float)
    result = Column(String(10))
    won = Column(Boolean)
    push = Column(Boolean, default=False)
    pnl = Column(Float)
    settled_at = Column(DateTime)

    prediction = relationship("Prediction", back_populates="value_bets")
    match = relationship("Match")

    def __repr__(self) -> str:
        return f"<ValueBet match={self.match_id} market={self.market} edge={self.edge:.4f}>"


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    league_code = Column(String(10))
    date_from = Column(DateTime)
    date_to = Column(DateTime)

    total_matches = Column(Integer)
    correct_predictions = Column(Integer)
    accuracy = Column(Float)

    total_bets = Column(Integer)
    winning_bets = Column(Integer)
    roi = Column(Float)
    profit_loss = Column(Float)

    avg_brier_score = Column(Float)
    avg_confidence = Column(Float)
    avg_edge = Column(Float)

    model_weights_used = Column(Text)  # JSON
    config_snapshot = Column(Text)
    report_json = Column(Text)

    def __repr__(self) -> str:
        return f"<BacktestResult {self.run_id} acc={self.accuracy:.2%}>"
