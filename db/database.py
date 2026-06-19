from __future__ import annotations
import os
import aiosqlite
from config.settings import settings

_CREATE_TRADES = """
CREATE TABLE IF NOT EXISTS trades (
    id           TEXT PRIMARY KEY,
    symbol       TEXT NOT NULL,
    asset_class  TEXT NOT NULL,
    side         TEXT NOT NULL,
    qty          REAL NOT NULL,
    price        REAL NOT NULL,
    total_value  REAL NOT NULL,
    mode         TEXT NOT NULL,
    signal_score REAL,
    timestamp    TEXT NOT NULL,
    exit_price   REAL,
    realized_pnl REAL,
    closed_at    TEXT
);
"""

_CREATE_SIGNALS = """
CREATE TABLE IF NOT EXISTS signals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol     TEXT NOT NULL,
    timestamp  TEXT NOT NULL,
    net_score  REAL,
    action     TEXT,
    votes_json TEXT
);
"""

_CREATE_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    date        TEXT PRIMARY KEY,
    total_value REAL,
    cash        REAL,
    day_pnl     REAL,
    num_trades  INTEGER
);
"""


async def init_db() -> None:
    os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)
    async with aiosqlite.connect(settings.db_path) as db:
        await db.execute(_CREATE_TRADES)
        await db.execute(_CREATE_SIGNALS)
        await db.execute(_CREATE_SNAPSHOTS)
        await db.commit()
