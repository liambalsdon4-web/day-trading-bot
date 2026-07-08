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
    risk_per_trade_pct: float = 0.0075   # risk 0.75% of equity per trade (via ATR stop)
    max_notional_pct: float = 0.30       # cap any single position at 30% of equity
    max_position_hours: float = 6.0
    daily_loss_limit_pct: float = 0.03

    # ── ATR-based stops / targets / trailing ──────────────────────────
    atr_period: int = 14
    atr_stop_mult: float = 1.5           # stop  = entry - 1.5 * ATR
    atr_target_mult: float = 3.0         # target = entry + 3.0 * ATR  (≈2:1 reward:risk)
    atr_trail_mult: float = 2.0          # trail stop this many ATRs behind the high (once in profit)
    fallback_stop_pct: float = 0.02      # used only when ATR is unavailable (e.g. on restart)

    # ── Regime + signal thresholds ────────────────────────────────────
    adx_trend_threshold: float = 22.0    # ADX >= this ⇒ trending regime (else range/mean-reversion)
    trend_only_entries: bool = True      # only BUY in a confirmed uptrend regime (cuts range chop)
    buy_threshold: float = 35.0
    sell_threshold: float = -35.0

    # ── Execution costs (paper realism) ───────────────────────────────
    slippage_bps: float = 5.0            # 5 bps slippage each side
    fee_bps: float = 2.0                 # 2 bps fee each side

    # ── Data ──────────────────────────────────────────────────────────
    db_path: str = "./data/trading.db"
    ohlcv_bars: int = 200                # more history for EMA50 / ADX context
    port: int = 8000
    open_browser: bool = True            # auto-open the dashboard when the bot starts

    # extra="ignore" so retired/unknown keys in .env (e.g. STOP_LOSS_PCT) don't crash startup
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
