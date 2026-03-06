import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import dotenv

dotenv.load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# --- Shared state ---
active_signals = []
connected_clients = set()


async def broadcast_signal(signal_data: dict):
    """Broadcast a new signal to all connected WebSocket clients."""
    active_signals.append(signal_data)
    if len(active_signals) > 100:
        active_signals.pop(0)

    dead = set()
    for client in connected_clients:
        try:
            await client.send_json(signal_data)
        except Exception:
            dead.add(client)
    for c in dead:
        connected_clients.discard(c)


# --- Trading engine background task ---
async def run_trading_engine():
    """Runs the full trading pipeline as a background asyncio task."""
    from core.data_ingestion import BinanceDataFeed
    from core.data_manager import DataManager
    from core.features import FeatureExtractor
    from core.market_structure import MarketStructure
    from core.liquidity import LiquidityEngine
    from core.order_blocks import InstitutionalZones
    from core.signal_generator import SignalGenerator
    from core.trader import BinanceFuturesTrader

    symbols = ["BTCUSDT", "ETHUSDT"]
    intervals = ["5m", "15m", "1h"]

    data_manager = DataManager(symbols, intervals)
    data_feed = BinanceDataFeed(symbols, intervals)
    market_struct = MarketStructure()
    liquidity = LiquidityEngine()
    institutional = InstitutionalZones()
    signal_gen = SignalGenerator(min_probability=65.0)
    trader = BinanceFuturesTrader()
    signal_count = 0

    async def on_candle_close(symbol, interval, kline_data):
        nonlocal signal_count
        data_manager.update_candle(symbol, interval, kline_data)
        df_raw = data_manager.get_dataframe(symbol, interval)

        if len(df_raw) < 50:
            return

        try:
            df = FeatureExtractor.apply_all_features(df_raw)
            df = market_struct.classify_structure(df)
            df = liquidity.detect_equal_levels(df)
            df = liquidity.detect_sweeps(df)
            df = institutional.detect_fvg(df)
            df = institutional.detect_order_blocks(df)

            signal = signal_gen.check_signals(df, symbol, interval)

            if signal:
                signal_count += 1
                logger.info(
                    f"\n{'='*60}\n"
                    f"SIGNAL #{signal_count}\n"
                    f"  PAIR:        {signal['PAIR']}\n"
                    f"  TIMEFRAME:   {signal['TIMEFRAME']}\n"
                    f"  TYPE:        {signal['TYPE']}\n"
                    f"  ENTRY:       {signal['ENTRY']}\n"
                    f"  STOP LOSS:   {signal['STOP_LOSS']}\n"
                    f"  TAKE PROFIT: {signal['TAKE_PROFIT']}\n"
                    f"  PROBABILITY: {signal['PROBABILITY']}\n"
                    f"  TIME:        {signal['TIMESTAMP']}\n"
                    f"{'='*60}"
                )
                await broadcast_signal(signal)

                trade_result = trader.execute_signal(signal)
                if trade_result:
                    logger.info("Trade executed successfully!")
                    signal["TRADE_STATUS"] = "EXECUTED"
                    signal["ORDER_ID"] = trade_result.get("entry", {}).get("orderId", "N/A")
                else:
                    signal["TRADE_STATUS"] = "SKIPPED"

        except Exception as e:
            logger.error(f"Pipeline error for {symbol} {interval}: {e}", exc_info=True)

    data_feed.register_callback(on_candle_close)

    logger.info("=" * 60)
    logger.info("Institutional Signal Engine Starting...")
    logger.info(f"   Leverage: {trader.leverage}x")
    logger.info(f"   Trade size: {trader.trade_usdt} USDT")
    logger.info(f"   Auto-trade: {'ENABLED' if trader.enabled else 'DISABLED (no API keys)'}")
    logger.info("=" * 60)

    data_manager.fetch_historical_data()
    logger.info("Historical data loaded. Starting live WebSocket stream...")

    await data_feed.start()


# --- FastAPI lifespan: starts trading engine as background task ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_trading_engine())
    logger.info("Trading engine started as background task.")
    yield
    task.cancel()
    logger.info("Trading engine stopped.")


# --- FastAPI app ---
app = FastAPI(title="Crypto Signal Engine API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/signals")
async def get_signals():
    return {"status": "success", "data": active_signals[-50:]}


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "signals_count": len(active_signals)}


@app.post("/api/webhook")
async def receive_webhook(payload: dict):
    return {"status": "received"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        for sig in active_signals[-10:]:
            await websocket.send_json(sig)
        while True:
            await websocket.receive_text()
    except Exception:
        connected_clients.discard(websocket)


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    import pathlib
    html_path = pathlib.Path(__file__).parent / "delivery" / "dashboard.html"
    return html_path.read_text()
