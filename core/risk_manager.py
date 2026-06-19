from __future__ import annotations
from api.models import Portfolio, Position, SignalScore
from config.settings import settings


def can_enter(portfolio: Portfolio) -> tuple[bool, str]:
    if len(portfolio.positions) >= portfolio.max_positions:
        return False, f"Max positions ({portfolio.max_positions}) reached"
    if portfolio.daily_loss_used_pct >= portfolio.daily_loss_limit_pct:
        return False, f"Daily loss limit reached ({portfolio.daily_loss_used_pct * 100:.2f}%)"
    return True, ""


def size_position(portfolio: Portfolio, price: float) -> float:
    """Fixed-fractional: risk 1% of capital per trade."""
    risk_capital = portfolio.total_value * settings.risk_per_trade_pct
    qty = risk_capital / (price * settings.stop_loss_pct)
    # Never spend more than 20% of cash on one trade
    max_qty = (portfolio.cash * 0.20) / price
    qty = min(qty, max_qty)
    if qty <= 0:
        return 0.0
    return round(qty, 6)


def calc_stop_loss(entry_price: float) -> float:
    return round(entry_price * (1 - settings.stop_loss_pct), 6)


def calc_take_profit(entry_price: float) -> float:
    return round(entry_price * (1 + settings.take_profit_pct), 6)


def check_exit(position: Position, signal: SignalScore, current_price: float) -> str | None:
    """Returns exit reason string or None if position should stay open."""
    if current_price <= position.stop_loss_price:
        return "STOP_LOSS"
    if current_price >= position.take_profit_price:
        return "TAKE_PROFIT"
    if signal.action == "SELL" and signal.confidence >= 0.4:
        return "SIGNAL_REVERSAL"
    return None
