from __future__ import annotations
from typing import Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Trading mode ──────────────────────────────────────────────────
    mode: Literal["paper", "live"] = "paper"

    # ── Symbols ───────────────────────────────────────────────────────
    stock_symbols: list[str] = ["AAPL", "TSLA", "NVDA"]
    crypto_symbols: list[str] = ["BTC-USD", "ETH-USD"]

    # ── Alpaca (stocks) ───────────────────────────────────────────────
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True

    # ── Crypto (CCXT / Binance) ───────────────────────────────────────
    crypto_exchange: str = "binance"
    binance_api_key: str = ""
    binance_secret: str = ""

    # ── Live-mode safety gate ─────────────────────────────────────────
    confirm_live_trading: str = ""

    # ── Loop timing ───────────────────────────────────────────────────
    tick_interval_seconds: int = 60
    market_timezone: str = "America/New_York"
    force_run: bool = False

    # ── Risk parameters ───────────────────────────────────────────────
    starting_capital: float = 10_000.0
    max_positions: int = 5
    risk_per_trade_pct: float = 0.01
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.02
    max_position_hours: float = 4.0
    daily_loss_limit_pct: float = 0.02

    # ── Signal thresholds ─────────────────────────────────────────────
    buy_threshold: float = 40.0
    sell_threshold: float = -40.0

    # ── Data ──────────────────────────────────────────────────────────
    db_path: str = "./data/trading.db"
    ohlcv_bars: int = 100
    port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
