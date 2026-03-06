import asyncio
import json
import logging
import os
import websockets
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BinanceDataFeed:
    """
    Connects to Binance Combined Stream WebSocket for real-time OHLCV kline data.
    Uses the /stream?streams= endpoint for multiple symbols/intervals.
    """

    def __init__(self, symbols=None, intervals=None):
        self.ws_base = os.getenv("BINANCE_WS_URL", "wss://stream.binance.com:9443")
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT"]
        self.intervals = intervals or ["5m", "15m", "1h"]
        self.callbacks = []

    def _build_stream_url(self):
        streams = []
        for sym in self.symbols:
            for intv in self.intervals:
                streams.append(f"{sym.lower()}@kline_{intv}")
        return f"{self.ws_base}/stream?streams={'/'.join(streams)}"

    def register_callback(self, callback):
        self.callbacks.append(callback)

    async def _process_message(self, message):
        try:
            data = json.loads(message)

            # Combined stream wraps payload in {"stream": ..., "data": {...}}
            if "data" in data:
                data = data["data"]

            if data.get("e") == "kline":
                kline = data["k"]
                symbol = kline["s"]
                interval = kline["i"]

                kline_data = {
                    "timestamp": pd.to_datetime(kline["t"], unit="ms"),
                    "open": float(kline["o"]),
                    "high": float(kline["h"]),
                    "low": float(kline["l"]),
                    "close": float(kline["c"]),
                    "volume": float(kline["v"]),
                    "is_closed": kline["x"],
                }

                if kline_data["is_closed"]:
                    logger.info(
                        f"[{symbol} {interval}] Candle CLOSED | "
                        f"O={kline_data['open']:.2f} H={kline_data['high']:.2f} "
                        f"L={kline_data['low']:.2f} C={kline_data['close']:.2f} "
                        f"V={kline_data['volume']:.2f}"
                    )
                    for cb in self.callbacks:
                        await cb(symbol, interval, kline_data)

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def start(self):
        url = self._build_stream_url()
        logger.info(f"Connecting to Binance WebSocket: {url}")

        reconnect_delay = 5
        while True:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    logger.info("✅ Connected to Binance WebSocket!")
                    while True:
                        msg = await ws.recv()
                        await self._process_message(msg)
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"WebSocket closed: {e}. Reconnecting in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
            except Exception as e:
                logger.error(f"WebSocket error: {e}. Reconnecting in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)


if __name__ == "__main__":
    async def demo_cb(sym, intv, data):
        print(f"[{sym} {intv}] Closed Candle: {data}")

    feed = BinanceDataFeed(symbols=["BTCUSDT"], intervals=["5m"])
    feed.register_callback(demo_cb)
    asyncio.run(feed.start())
