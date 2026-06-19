from __future__ import annotations
from abc import ABC, abstractmethod


class AbstractBroker(ABC):
    @abstractmethod
    async def place_order(self, symbol: str, side: str, qty: float,
                          stop_loss: float | None = None,
                          take_profit: float | None = None) -> dict:
        ...

    @abstractmethod
    async def close_position(self, symbol: str, qty: float, current_price: float) -> dict:
        ...

    @abstractmethod
    async def get_current_price(self, symbol: str) -> float:
        ...
