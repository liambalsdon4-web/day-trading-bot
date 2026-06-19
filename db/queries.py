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


async def get_daily_summary(date_str: str) -> dict:
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT symbol, realized_pnl FROM trades
               WHERE DATE(closed_at) = ? AND realized_pnl IS NOT NULL
               ORDER BY closed_at ASC""",
            (date_str,),
        ) as cursor:
            rows = await cursor.fetchall()

    empty = {
        "date": date_str, "total_trades": 0, "winning_trades": 0,
        "losing_trades": 0, "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
        "risk_reward_ratio": 0.0, "total_realized_pnl": 0.0, "max_drawdown": 0.0,
        "best_trade_symbol": None, "best_trade_pnl": None,
        "worst_trade_symbol": None, "worst_trade_pnl": None,
    }
    if not rows:
        return empty

    pnls = [(r["symbol"], r["realized_pnl"]) for r in rows]
    wins = [(s, p) for s, p in pnls if p > 0]
    losses = [(s, p) for s, p in pnls if p < 0]

    avg_win = sum(p for _, p in wins) / len(wins) if wins else 0.0
    avg_loss = sum(p for _, p in losses) / len(losses) if losses else 0.0

    # Max drawdown from running cumulative PnL during the day
    peak = running = max_dd = 0.0
    for _, p in pnls:
        running += p
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd

    best = max(pnls, key=lambda x: x[1])
    worst = min(pnls, key=lambda x: x[1])

    return {
        "date": date_str,
        "total_trades": len(pnls),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate": len(wins) / len(pnls),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "risk_reward_ratio": avg_win / abs(avg_loss) if avg_loss != 0 else 0.0,
        "total_realized_pnl": sum(p for _, p in pnls),
        "max_drawdown": max_dd,
        "best_trade_symbol": best[0],
        "best_trade_pnl": best[1],
        "worst_trade_symbol": worst[0],
        "worst_trade_pnl": worst[1],
    }
