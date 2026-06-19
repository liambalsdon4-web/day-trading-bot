from __future__ import annotations
import uuid
from datetime import datetime, timezone
from brokers.base import AbstractBroker


class PaperBroker(AbstractBroker):
    """Simulates order execution entirely in-memory. No API calls."""

    def __init__(self, current_prices: dict):
        # Shared reference to the engine's live price cache
        self._prices = current_prices

    async def place_order(self, symbol: str, side: str, qty: float,
                          stop_loss: float | None = None,
                          take_profit: float | None = None) -> dict:
        price = self._prices.get(symbol, 0.0)
        return {
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "filled_price": price,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "filled",
        }

    async def close_position(self, symbol: str, qty: float, current_price: float) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "symbol": symbol,
            "side": "SELL",
            "qty": qty,
            "filled_price": current_price,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "filled",
        }

    async def get_current_price(self, symbol: str) -> float:
        return self._prices.get(symbol, 0.0)
