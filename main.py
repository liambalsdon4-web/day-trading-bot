from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config.settings import settings
from db.database import init_db
from api.routes import router
from core.engine import TradingEngine


def _build_feed():
    if settings.alpaca_api_key and settings.stock_symbols:
        from feeds.alpaca_feed import AlpacaFeed
        return AlpacaFeed()
    from feeds.yfinance_feed import YFinanceFeed
    return YFinanceFeed()


def _build_stock_broker(price_cache: dict):
    if settings.alpaca_api_key:
        from brokers.alpaca_broker import AlpacaBroker
        return AlpacaBroker()
    from brokers.paper_broker import PaperBroker
    return PaperBroker(price_cache)


def _build_crypto_broker(price_cache: dict):
    try:
        import ccxt  # noqa
        if settings.crypto_symbols:
            from brokers.ccxt_broker import CCXTBroker
            return CCXTBroker(price_cache)
    except ImportError:
        pass
    from brokers.paper_broker import PaperBroker
    return PaperBroker(price_cache)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()

    feed = _build_feed()
    all_symbols = settings.stock_symbols + settings.crypto_symbols

    engine = TradingEngine(
        feed=feed,
        stock_broker=_build_stock_broker(feed._latest_price),
        crypto_broker=_build_crypto_broker(feed._latest_price),
    )
    app.state.engine = engine

    feed_task = asyncio.create_task(feed.start(all_symbols))
    # Small delay so the feed gets at least one data pull before first tick
    await asyncio.sleep(5)
    await engine.restore_state()
    await engine.start()

    yield

    await engine.stop()
    feed_task.cancel()
    try:
        await feed_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Day Trading Bot", lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=False)
