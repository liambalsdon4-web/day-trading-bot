from __future__ import annotations
from typing import Literal, Optional
from datetime import datetime
from pydantic import BaseModel


class IndicatorVote(BaseModel):
    indicator: str
    vote: Literal["bullish", "bearish", "neutral"]
    value: float
    weight: float
    reason: str


class SignalScore(BaseModel):
    symbol: str
    asset_class: Literal["stock", "crypto"]
    timestamp: datetime
    votes: list[IndicatorVote]
    bull_score: float
    bear_score: float
    net_score: float
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float


class Position(BaseModel):
    symbol: str
    asset_class: Literal["stock", "crypto"]
    qty: float
    entry_price: float
    current_price: float
    stop_loss_price: float
    take_profit_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    opened_at: datetime


class Trade(BaseModel):
    id: str
    symbol: str
    asset_class: Literal["stock", "crypto"]
    side: Literal["BUY", "SELL"]
    qty: float
    price: float
    total_value: float
    mode: Literal["paper", "live"]
    signal_score: float
    timestamp: datetime
    exit_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    closed_at: Optional[datetime] = None


class Portfolio(BaseModel):
    mode: Literal["paper", "live"]
    cash: float
    total_value: float
    starting_capital: float
    total_pnl: float
    total_pnl_pct: float
    day_pnl: float
    day_pnl_pct: float
    positions: list[Position]
    max_positions: int
    daily_loss_limit_pct: float
    daily_loss_used_pct: float


class BotStatus(BaseModel):
    running: bool
    mode: Literal["paper", "live"]
    market_open: bool
    stock_symbols: list[str]
    crypto_symbols: list[str]
    last_tick_at: Optional[datetime]
    tick_interval_seconds: int
    errors: list[str]


class DashboardResponse(BaseModel):
    status: BotStatus
    portfolio: Portfolio
    recent_signals: list[SignalScore]
    recent_trades: list[Trade]


class DailySummary(BaseModel):
    date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    risk_reward_ratio: float
    total_realized_pnl: float
    max_drawdown: float
    best_trade_symbol: Optional[str] = None
    best_trade_pnl: Optional[float] = None
    worst_trade_symbol: Optional[str] = None
    worst_trade_pnl: Optional[float] = None
