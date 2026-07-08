from __future__ import annotations
import asyncio
import uuid
from datetime import datetime, timezone, date
import pytz
from api.models import Portfolio, Position, Trade, SignalScore, BotStatus
from config.settings import settings
from core import signal_scorer, risk_manager
from db import queries


def _is_market_hours() -> bool:
    if settings.force_run:
        return True
    tz = pytz.timezone(settings.market_timezone)
    now = datetime.now(tz)
    if now.weekday() >= 5:
        return False
    open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_time <= now <= close_time


def _init_portfolio() -> Portfolio:
    return Portfolio(
        mode=settings.mode,
        cash=settings.starting_capital,
        total_value=settings.starting_capital,
        starting_capital=settings.starting_capital,
        total_pnl=0.0,
        total_pnl_pct=0.0,
        day_pnl=0.0,
        day_pnl_pct=0.0,
        positions=[],
        max_positions=settings.max_positions,
        daily_loss_limit_pct=settings.daily_loss_limit_pct,
        daily_loss_used_pct=0.0,
    )


class TradingEngine:
    def __init__(self, feed, stock_broker, crypto_broker):
        self._feed = feed
        self._stock_broker = stock_broker
        self._crypto_broker = crypto_broker
        self.running = False
        self._task: asyncio.Task | None = None
        self.last_tick_at: datetime | None = None
        self.errors: list[str] = []
        self.portfolio: Portfolio = _init_portfolio()
        self.current_signals: dict[str, SignalScore] = {}
        self._day_open_value: float = settings.starting_capital
        self._current_day: date = datetime.now(timezone.utc).date()

    def get_status(self) -> BotStatus:
        return BotStatus(
            running=self.running,
            mode=settings.mode,
            market_open=_is_market_hours(),
            stock_symbols=settings.stock_symbols,
            crypto_symbols=settings.crypto_symbols,
            last_tick_at=self.last_tick_at,
            tick_interval_seconds=settings.tick_interval_seconds,
            errors=self.errors[-10:],
        )

    async def restore_state(self) -> None:
        snapshot = await queries.get_last_portfolio_snapshot()
        open_trades = await queries.get_open_trades()

        if snapshot:
            self.portfolio.cash = snapshot["cash"]
            self.portfolio.total_value = snapshot["total_value"]
        elif open_trades:
            self.portfolio.cash = self.portfolio.starting_capital - sum(t.total_value for t in open_trades)
            self.portfolio.total_value = self.portfolio.cash + sum(t.total_value for t in open_trades)

        self.portfolio.total_pnl = self.portfolio.total_value - self.portfolio.starting_capital
        self.portfolio.total_pnl_pct = self.portfolio.total_pnl / self.portfolio.starting_capital
        self._day_open_value = self.portfolio.total_value

        for trade in open_trades:
            position = Position(
                trade_id=trade.id,
                symbol=trade.symbol, asset_class=trade.asset_class,
                qty=trade.qty, entry_price=trade.price, current_price=trade.price,
                stop_loss_price=risk_manager.calc_stop_loss(trade.price),
                take_profit_price=risk_manager.calc_take_profit(trade.price),
                unrealized_pnl=0.0, unrealized_pnl_pct=0.0,
                opened_at=trade.timestamp,
                highest_price=trade.price, atr_at_entry=0.0,
            )
            self.portfolio.positions.append(position)

    async def start(self) -> None:
        self.running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def manual_tick(self) -> None:
        await self._tick()
        self.last_tick_at = datetime.now(timezone.utc)

    async def _loop(self) -> None:
        while self.running:
            try:
                await self._tick()
                self.last_tick_at = datetime.now(timezone.utc)
            except Exception as e:
                self.errors.append(f"{datetime.now(timezone.utc)}: {e}")
                self.errors = self.errors[-50:]
            await asyncio.sleep(settings.tick_interval_seconds)

    async def _tick(self) -> None:
        # Reset day stats on new trading day
        today = datetime.now(timezone.utc).date()
        if today != self._current_day:
            self._current_day = today
            self._day_open_value = self.portfolio.total_value
            self.portfolio.day_pnl = 0.0
            self.portfolio.day_pnl_pct = 0.0
            self.portfolio.daily_loss_used_pct = 0.0

        all_symbols = [
            (s, "stock") for s in settings.stock_symbols
        ] + [
            (s, "crypto") for s in settings.crypto_symbols
        ]

        for symbol, asset_class in all_symbols:
            # Skip stock processing outside market hours
            if asset_class == "stock" and not _is_market_hours():
                continue
            try:
                await self._process_symbol(symbol, asset_class)
            except Exception as e:
                self.errors.append(f"{datetime.now(timezone.utc)} [{symbol}]: {e}")
                self.errors = self.errors[-50:]

        self._update_portfolio_value()
        await queries.upsert_portfolio_snapshot(
            self.portfolio.total_value,
            self.portfolio.cash,
            self.portfolio.day_pnl,
            num_trades=0,
        )

    async def _process_symbol(self, symbol: str, asset_class: str) -> None:
        ohlcv = self._feed.get_ohlcv(symbol)
        if ohlcv is None or len(ohlcv) < 30:
            return

        signal = signal_scorer.score_symbol(symbol, ohlcv, asset_class)
        self.current_signals[symbol] = signal
        await queries.insert_signal(signal)

        broker = self._stock_broker if asset_class == "stock" else self._crypto_broker
        current_price = self._feed.get_price(symbol)
        if current_price <= 0:
            return

        # Check existing position for exit
        existing = next((p for p in self.portfolio.positions if p.symbol == symbol), None)
        if existing:
            existing.current_price = current_price
            existing.unrealized_pnl = (current_price - existing.entry_price) * existing.qty
            existing.unrealized_pnl_pct = (current_price - existing.entry_price) / existing.entry_price

            # Trail the stop up behind the high (uses the fresh ATR from this tick).
            risk_manager.update_trailing_stop(existing, current_price, signal.atr)

            exit_reason = risk_manager.check_exit(existing, signal, current_price)
            if exit_reason:
                await self._close_position(existing, current_price, exit_reason, broker)
            return

        # Check for new entry
        if signal.action != "BUY":
            return

        can_trade, reason = risk_manager.can_enter(self.portfolio)
        if not can_trade:
            return

        est_stop = risk_manager.calc_stop_loss(current_price, signal.atr)
        qty = risk_manager.size_position(self.portfolio, current_price, est_stop)
        if qty <= 0 or qty * current_price > self.portfolio.cash:
            return

        order = await broker.place_order(
            symbol, "BUY", qty,
            stop_loss=est_stop,
            take_profit=risk_manager.calc_take_profit(current_price, signal.atr),
        )
        filled_price = order.get("filled_price", current_price)
        order_id = order.get("id", str(uuid.uuid4()))

        # Anchor the real stop/target to the actual fill price.
        stop = risk_manager.calc_stop_loss(filled_price, signal.atr)
        tp = risk_manager.calc_take_profit(filled_price, signal.atr)

        cost = filled_price * qty
        self.portfolio.cash -= cost

        position = Position(
            trade_id=order_id,
            symbol=symbol, asset_class=asset_class, qty=qty,
            entry_price=filled_price, current_price=filled_price,
            stop_loss_price=stop, take_profit_price=tp,
            unrealized_pnl=0.0, unrealized_pnl_pct=0.0,
            opened_at=datetime.now(timezone.utc),
            highest_price=filled_price, atr_at_entry=signal.atr,
        )
        self.portfolio.positions.append(position)

        trade = Trade(
            id=order_id,
            symbol=symbol, asset_class=asset_class,
            side="BUY", qty=qty, price=filled_price,
            total_value=cost, mode=settings.mode,
            signal_score=signal.net_score,
            timestamp=datetime.now(timezone.utc),
        )
        await queries.insert_trade(trade)

    async def _close_position(self, position: Position, current_price: float,
                               reason: str, broker) -> None:
        try:
            order = await broker.close_position(position.symbol, position.qty, current_price)
            filled_price = order.get("filled_price", current_price)
        except Exception as e:
            # Broker doesn't know this position (ghost from DB restore or external close).
            # Mark it out at the current price and RETURN its value to cash, so local
            # accounting stays balanced. Previously this dropped the position's value
            # without crediting cash — a silent leak that showed up as phantom losses.
            realized_pnl = (current_price - position.entry_price) * position.qty
            self.portfolio.cash += current_price * position.qty
            self.portfolio.positions = [p for p in self.portfolio.positions if p.symbol != position.symbol]
            await queries.close_trade(position.trade_id, current_price, realized_pnl)
            self.errors.append(f"{datetime.now(timezone.utc)} [{position.symbol}] removed ghost position: {e}")
            self.errors = self.errors[-50:]
            return

        realized_pnl = (filled_price - position.entry_price) * position.qty
        self.portfolio.cash += filled_price * position.qty

        # Update daily loss tracking
        if realized_pnl < 0:
            loss_pct = abs(realized_pnl) / self.portfolio.total_value
            self.portfolio.daily_loss_used_pct += loss_pct

        # Update the original BUY trade record with exit info
        await queries.close_trade(
            trade_id=position.trade_id,
            exit_price=filled_price,
            realized_pnl=realized_pnl,
        )

        # Record SELL trade
        sell_trade = Trade(
            id=str(uuid.uuid4()),
            symbol=position.symbol, asset_class=position.asset_class,
            side="SELL", qty=position.qty, price=filled_price,
            total_value=filled_price * position.qty, mode=settings.mode,
            signal_score=self.current_signals.get(position.symbol, SignalScore(
                symbol=position.symbol, asset_class=position.asset_class,
                timestamp=datetime.now(timezone.utc), votes=[], bull_score=0,
                bear_score=0, net_score=0, action="HOLD", confidence=0,
            )).net_score,
            timestamp=datetime.now(timezone.utc),
            exit_price=filled_price,
            realized_pnl=realized_pnl,
            closed_at=datetime.now(timezone.utc),
        )
        await queries.insert_trade(sell_trade)
        self.portfolio.positions = [p for p in self.portfolio.positions if p.symbol != position.symbol]

    def _update_portfolio_value(self) -> None:
        positions_value = sum(p.current_price * p.qty for p in self.portfolio.positions)
        self.portfolio.total_value = self.portfolio.cash + positions_value
        self.portfolio.total_pnl = self.portfolio.total_value - self.portfolio.starting_capital
        self.portfolio.total_pnl_pct = self.portfolio.total_pnl / self.portfolio.starting_capital
        self.portfolio.day_pnl = self.portfolio.total_value - self._day_open_value
        self.portfolio.day_pnl_pct = self.portfolio.day_pnl / self._day_open_value if self._day_open_value else 0.0

    def force_close_position(self, symbol: str) -> bool:
        pos = next((p for p in self.portfolio.positions if p.symbol == symbol), None)
        return pos is not None

    async def execute_force_close(self, symbol: str) -> bool:
        pos = next((p for p in self.portfolio.positions if p.symbol == symbol), None)
        if not pos:
            return False
        broker = self._stock_broker if pos.asset_class == "stock" else self._crypto_broker
        price = self._feed.get_price(symbol) or pos.current_price
        await self._close_position(pos, price, "FORCE_CLOSE", broker)
        return True
