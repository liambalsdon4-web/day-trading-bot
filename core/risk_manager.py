from __future__ import annotations
from datetime import datetime, timezone
from api.models import Portfolio, Position, SignalScore
from config.settings import settings


def can_enter(portfolio: Portfolio) -> tuple[bool, str]:
    if len(portfolio.positions) >= portfolio.max_positions:
        return False, f"Max positions ({portfolio.max_positions}) reached"
    if portfolio.daily_loss_used_pct >= portfolio.daily_loss_limit_pct:
        return False, f"Daily loss limit reached ({portfolio.daily_loss_used_pct * 100:.2f}%)"
    return True, ""


def calc_stop_loss(entry_price: float, atr: float | None = None) -> float:
    """ATR-based stop; falls back to a fixed % when ATR is unavailable (e.g. on restart)."""
    if atr and atr > 0:
        return round(entry_price - settings.atr_stop_mult * atr, 6)
    return round(entry_price * (1 - settings.fallback_stop_pct), 6)


def calc_take_profit(entry_price: float, atr: float | None = None) -> float:
    if atr and atr > 0:
        return round(entry_price + settings.atr_target_mult * atr, 6)
    # Keep the fallback at the same reward:risk ratio as the ATR version
    rr = settings.atr_target_mult / settings.atr_stop_mult
    return round(entry_price * (1 + settings.fallback_stop_pct * rr), 6)


def size_position(portfolio: Portfolio, entry_price: float, stop_price: float) -> float:
    """Risk a fixed % of equity based on the actual stop distance (volatility-adjusted).

    qty = (equity * risk%) / (entry - stop). Capped by max notional and available cash.
    """
    stop_dist = entry_price - stop_price
    if stop_dist <= 0 or entry_price <= 0:
        return 0.0
    risk_capital = portfolio.total_value * settings.risk_per_trade_pct
    qty = risk_capital / stop_dist
    max_notional_qty = (portfolio.total_value * settings.max_notional_pct) / entry_price
    cash_qty = portfolio.cash / entry_price
    qty = min(qty, max_notional_qty, cash_qty)
    return round(qty, 6) if qty > 0 else 0.0


def update_trailing_stop(position: Position, current_price: float, atr: float | None) -> None:
    """Ratchet the stop up behind the high once the trade is in profit (never down)."""
    if current_price > position.highest_price:
        position.highest_price = current_price
    if atr and atr > 0 and position.highest_price > position.entry_price:
        trail = position.highest_price - settings.atr_trail_mult * atr
        if trail > position.stop_loss_price:
            position.stop_loss_price = round(trail, 6)


def check_exit(position: Position, signal: SignalScore, current_price: float) -> str | None:
    """Returns an exit reason or None."""
    if current_price <= position.stop_loss_price:
        return "STOP_LOSS"
    if current_price >= position.take_profit_price:
        return "TAKE_PROFIT"
    if signal.action == "SELL" and signal.confidence >= 0.35:
        return "SIGNAL_REVERSAL"
    hours_held = (datetime.now(timezone.utc) - position.opened_at).total_seconds() / 3600
    if hours_held >= settings.max_position_hours:
        pnl_pct = position.unrealized_pnl_pct
        if pnl_pct > 0:
            return "TIME_EXIT_PROFIT"
        if pnl_pct >= -0.01:
            return "TIME_EXIT_BREAKEVEN"
        # Significantly negative — let the (trailing) stop handle it.
    return None
