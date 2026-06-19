from __future__ import annotations
import os
from brokers.base import AbstractBroker
from config.settings import settings


class AlpacaBroker(AbstractBroker):
    """Alpaca Markets broker for stocks. Defaults to paper trading."""

    def __init__(self):
        if settings.mode == "live" and not settings.alpaca_paper:
            assert os.getenv("CONFIRM_LIVE_TRADING") == "YES_I_UNDERSTAND", (
                "Set CONFIRM_LIVE_TRADING=YES_I_UNDERSTAND in .env to enable live stock trading"
            )
            base_url = "https://api.alpaca.markets"
        else:
            base_url = "https://paper-api.alpaca.markets"

        from alpaca.trading.client import TradingClient
        from alpaca.data.historical import StockHistoricalDataClient
        self._trading = TradingClient(
            settings.alpaca_api_key, settings.alpaca_secret_key,
            paper=(base_url == "https://paper-api.alpaca.markets"),
        )
        self._data = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)

    async def place_order(self, symbol: str, side: str, qty: float,
                          stop_loss: float | None = None,
                          take_profit: float | None = None) -> dict:
        import asyncio
        from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        order_side = OrderSide.BUY if side == "BUY" else OrderSide.SELL
        legs = {}
        if stop_loss:
            legs["stop_loss"] = StopLossRequest(stop_price=stop_loss)
        if take_profit:
            legs["take_profit"] = TakeProfitRequest(limit_price=take_profit)

        req = MarketOrderRequest(symbol=symbol, qty=qty, side=order_side,
                                 time_in_force=TimeInForce.DAY, **legs)
        order = await asyncio.to_thread(self._trading.submit_order, req)
        return {"id": str(order.id), "symbol": symbol, "side": side,
                "qty": float(qty), "status": str(order.status)}

    async def close_position(self, symbol: str, qty: float, current_price: float) -> dict:
        import asyncio
        result = await asyncio.to_thread(self._trading.close_position, symbol)
        return {"id": str(result.id), "symbol": symbol, "side": "SELL",
                "qty": float(qty), "filled_price": current_price, "status": "filled"}

    async def get_current_price(self, symbol: str) -> float:
        import asyncio
        from alpaca.data.requests import StockLatestQuoteRequest
        req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quotes = await asyncio.to_thread(self._data.get_stock_latest_quote, req)
        quote = quotes.get(symbol)
        if quote:
            return float(quote.ask_price or quote.bid_price or 0)
        return 0.0
