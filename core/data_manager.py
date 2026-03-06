import os
import requests
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class DataManager:
    """
    Manages historical and live OHLCV data for multiple symbols and intervals.
    """

    def __init__(self, symbols, intervals, limit=1000):
        self.symbols = symbols
        self.intervals = intervals
        self.limit = limit
        self.base_url = os.getenv("BINANCE_REST_URL", "https://api.binance.com/api/v3")
        self.data = {}

    def fetch_historical_data(self):
        logger.info("Fetching historical data for seeding...")
        for sym in self.symbols:
            for intv in self.intervals:
                key = f"{sym}_{intv}"
                url = f"{self.base_url}/klines"
                params = {"symbol": sym, "interval": intv, "limit": self.limit}
                try:
                    response = requests.get(url, params=params, timeout=30)
                    response.raise_for_status()
                    klines = response.json()

                    df = pd.DataFrame(
                        klines,
                        columns=[
                            "timestamp", "open", "high", "low", "close", "volume",
                            "close_time", "quote_asset_volume", "number_of_trades",
                            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore",
                        ],
                    )
                    df = df[["timestamp", "open", "high", "low", "close", "volume"]]
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                    for col in ["open", "high", "low", "close", "volume"]:
                        df[col] = df[col].astype(float)

                    self.data[key] = df
                    logger.info(f"✅ Loaded {len(df)} candles for {key}")
                except Exception as e:
                    logger.error(f"Failed to fetch historical data for {key}: {e}")

    def update_candle(self, symbol, interval, kline_data):
        key = f"{symbol}_{interval}"
        if key not in self.data:
            return

        df = self.data[key]
        timestamp = kline_data["timestamp"]

        if len(df) > 0 and df.iloc[-1]["timestamp"] == timestamp:
            df.loc[df.index[-1], ["open", "high", "low", "close", "volume"]] = [
                kline_data["open"], kline_data["high"], kline_data["low"],
                kline_data["close"], kline_data["volume"],
            ]
        else:
            new_row = pd.DataFrame([{
                "timestamp": timestamp,
                "open": kline_data["open"],
                "high": kline_data["high"],
                "low": kline_data["low"],
                "close": kline_data["close"],
                "volume": kline_data["volume"],
            }])
            self.data[key] = pd.concat([df, new_row], ignore_index=True)

            if len(self.data[key]) > self.limit + 100:
                self.data[key] = self.data[key].iloc[-self.limit :].reset_index(drop=True)

    def get_dataframe(self, symbol, interval):
        key = f"{symbol}_{interval}"
        return self.data.get(key, pd.DataFrame()).copy()
