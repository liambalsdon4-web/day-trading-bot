from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from api.models import DashboardResponse, BotStatus, Portfolio, SignalScore, Trade, DailySummary
from db import queries

router = APIRouter(prefix="/api")


def _engine(request: Request):
    return request.app.state.engine


@router.get("/health")
async def health(request: Request):
    eng = _engine(request)
    return {"status": "ok", "mode": eng.portfolio.mode, "running": eng.running}


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(request: Request):
    eng = _engine(request)
    recent_trades = await queries.get_recent_trades(limit=20)
    return DashboardResponse(
        status=eng.get_status(),
        portfolio=eng.portfolio,
        recent_signals=list(eng.current_signals.values()),
        recent_trades=recent_trades,
    )


@router.get("/status", response_model=BotStatus)
async def status(request: Request):
    return _engine(request).get_status()


@router.get("/portfolio", response_model=Portfolio)
async def portfolio(request: Request):
    return _engine(request).portfolio


@router.get("/positions")
async def positions(request: Request):
    return _engine(request).portfolio.positions


@router.get("/signals", response_model=list[SignalScore])
async def signals(request: Request):
    return list(_engine(request).current_signals.values())


@router.get("/signals/{symbol}", response_model=SignalScore)
async def signal_detail(symbol: str, request: Request):
    eng = _engine(request)
    sig = eng.current_signals.get(symbol)
    if not sig:
        raise HTTPException(status_code=404, detail=f"No signal for {symbol}")
    return sig


@router.get("/trades", response_model=list[Trade])
async def trades(request: Request, limit: int = 50, offset: int = 0):
    return await queries.get_recent_trades(limit=limit, offset=offset)


@router.get("/history")
async def history(days: int = 30):
    return await queries.get_portfolio_history(days=days)


@router.get("/summary/daily", response_model=DailySummary)
async def daily_summary_today():
    from datetime import date as _date
    return await queries.get_daily_summary(_date.today().isoformat())


@router.get("/summary/daily/{date_str}", response_model=DailySummary)
async def daily_summary_by_date(date_str: str):
    return await queries.get_daily_summary(date_str)


@router.post("/bot/start")
async def bot_start(request: Request):
    eng = _engine(request)
    if eng.running:
        return {"message": "Bot already running"}
    await eng.start()
    return {"message": "Bot started"}


@router.post("/bot/stop")
async def bot_stop(request: Request):
    eng = _engine(request)
    await eng.stop()
    return {"message": "Bot stopped"}


@router.post("/bot/tick")
async def bot_tick(request: Request):
    eng = _engine(request)
    await eng.manual_tick()
    return {"message": "Tick executed", "signals": list(eng.current_signals.keys())}


@router.delete("/positions/{symbol}")
async def force_close(symbol: str, request: Request):
    eng = _engine(request)
    success = await eng.execute_force_close(symbol)
    if not success:
        raise HTTPException(status_code=404, detail=f"No open position for {symbol}")
    return {"message": f"Position {symbol} closed"}


@router.get("/config")
async def config_view(request: Request):
    from config.settings import settings
    return {
        "mode": settings.mode,
        "stock_symbols": settings.stock_symbols,
        "crypto_symbols": settings.crypto_symbols,
        "tick_interval_seconds": settings.tick_interval_seconds,
        "max_positions": settings.max_positions,
        "starting_capital": settings.starting_capital,
        "risk_per_trade_pct": settings.risk_per_trade_pct,
        "stop_loss_pct": settings.stop_loss_pct,
        "take_profit_pct": settings.take_profit_pct,
        "daily_loss_limit_pct": settings.daily_loss_limit_pct,
        "buy_threshold": settings.buy_threshold,
        "sell_threshold": settings.sell_threshold,
        "max_position_hours": settings.max_position_hours,
        "has_alpaca_key": bool(settings.alpaca_api_key),
        "has_binance_key": bool(settings.binance_api_key),
    }
