from __future__ import annotations
import uuid
from datetime import datetime, timezone
from brokers.base import AbstractBroker
from config.settings import settings


class PaperBroker(AbstractBroker):
    """Simulates order execution in-memory, including realistic slippage + fees.

    Buys fill slightly above the quote and sells slightly below, so paper results
    reflect the real cost of crossing the spread (issue that made paper look better
    than live).
    """

    def __init__(self, current_prices: dict):
        # Shared reference to the engine's live price cache
        self._prices = current_prices
        self._cost = (settings.slippage_bps + settings.fee_bps) / 10_000.0

    async def place_order(self, symbol: str, side: str, qty: float,
                          stop_loss: float | None = None,
                          take_profit: float | None = None) -> dict:
        price = self._prices.get(symbol, 0.0)
        # Buys pay up, sells receive less.
        filled = price * (1 + self._cost) if side == "BUY" else price * (1 - self._cost)
        return {
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "filled_price": round(filled, 6),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "filled",
        }

    async def close_position(self, symbol: str, qty: float, current_price: float) -> dict:
        filled = current_price * (1 - self._cost)  # closing a long = selling
        return {
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "side": "SELL",
            "qty": qty,
            "filled_price": round(filled, 6),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "filled",
        }

    async def get_current_price(self, symbol: str) -> float:
        return self._prices.get(symbol, 0.0)
