from __future__ import annotations
import json
import aiosqlite
from datetime import datetime
from api.models import Trade, SignalScore
from config.settings import settings


async def insert_trade(trade: Trade) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            """INSERT OR REPLACE INTO trades
               (id, symbol, asset_class, side, qty, price, total_value,
                mode, signal_score, timestamp, exit_price, realized_pnl, closed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                trade.id, trade.symbol, trade.asset_class, trade.side,
                trade.qty, trade.price, trade.total_value, trade.mode,
                trade.signal_score, trade.timestamp.isoformat(),
                trade.exit_price, trade.realized_pnl,
                trade.closed_at.isoformat() if trade.closed_at else None,
            ),
        )
        await db.commit()


async def close_trade(trade_id: str, exit_price: float, realized_pnl: float) -> None:
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "UPDATE trades SET exit_price=?, realized_pnl=?, closed_at=? WHERE id=?",
            (exit_price, realized_pnl, datetime.utcnow().isoformat(), trade_id),
        )
        await db.commit()


async def get_recent_trades(limit: int = 50, offset: int = 0) -> list[Trade]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
    trades = []
    for r in rows:
        trades.append(
            Trade(
                id=r["id"], symbol=r["symbol"], asset_class=r["asset_class"],
                side=r["side"], qty=r["qty"], price=r["price"],
                total_value=r["total_value"], mode=r["mode"],
                signal_score=r["signal_score"] or 0.0,
                timestamp=datetime.fromisoformat(r["timestamp"]),
                exit_price=r["exit_price"], realized_pnl=r["realized_pnl"],
                closed_at=datetime.fromisoformat(r["closed_at"]) if r["closed_at"] else None,
            )
        )
    return trades


async def insert_signal(signal: SignalScore) -> None:
    votes_json = json.dumps([v.model_dump() for v in signal.votes])
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            "INSERT INTO signals (symbol, timestamp, net_score, action, votes_json) VALUES (?,?,?,?,?)",
            (signal.symbol, signal.timestamp.isoformat(), signal.net_score, signal.action, votes_json),
        )
        await db.commit()


async def upsert_portfolio_snapshot(total_value: float, cash: float, day_pnl: float, num_trades: int) -> None:
    date_str = datetime.utcnow().date().isoformat()
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(
            """INSERT OR REPLACE INTO portfolio_snapshots (date, total_value, cash, day_pnl, num_trades)
               VALUES (?,?,?,?,?)""",
            (date_str, total_value, cash, day_pnl, num_trades),
        )
        await db.commit()


async def get_portfolio_history(days: int = 30) -> list[dict]:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM portfolio_snapshots ORDER BY date DESC LIMIT ?", (days,)
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]
