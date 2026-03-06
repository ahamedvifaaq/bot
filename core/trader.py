import hashlib
import hmac
import logging
import os
import time
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class BinanceFuturesTrader:
    """
    Executes trades on Binance USD-M Futures Testnet.
    Places market orders with stop-loss and take-profit using 20x leverage.
    """

    def __init__(self):
        self.api_key = os.getenv("BINANCE_FUTURES_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_FUTURES_API_SECRET", "")
        self.base_url = os.getenv(
            "BINANCE_FUTURES_URL", "https://testnet.binancefuture.com"
        )
        self.leverage = int(os.getenv("TRADE_LEVERAGE", "20"))
        self.trade_usdt = float(os.getenv("TRADE_USDT_SIZE", "100"))
        self.enabled = bool(self.api_key and self.api_secret)

        if not self.enabled:
            logger.warning(
                "⚠️  Futures trading DISABLED — set BINANCE_FUTURES_API_KEY and "
                "BINANCE_FUTURES_API_SECRET in .env to enable auto-trading."
            )

    # ------------------------------------------------------------------ #
    #  Low-level helpers                                                  #
    # ------------------------------------------------------------------ #

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _headers(self):
        return {"X-MBX-APIKEY": self.api_key}

    def _request(self, method, path, params=None):
        params = params or {}
        params = self._sign(params)
        url = f"{self.base_url}{path}"
        resp = requests.request(
            method, url, params=params, headers=self._headers(), timeout=10
        )
        data = resp.json()
        if resp.status_code != 200:
            logger.error(f"Binance API error [{resp.status_code}]: {data}")
        return data, resp.status_code

    # ------------------------------------------------------------------ #
    #  Account helpers                                                    #
    # ------------------------------------------------------------------ #

    def set_leverage(self, symbol: str):
        data, status = self._request("POST", "/fapi/v1/leverage", {
            "symbol": symbol,
            "leverage": self.leverage,
        })
        if status == 200:
            logger.info(f"✅ Leverage set to {self.leverage}x for {symbol}")
        return data

    def set_margin_type(self, symbol: str, margin_type="ISOLATED"):
        data, status = self._request("POST", "/fapi/v1/marginType", {
            "symbol": symbol,
            "marginType": margin_type,
        })
        # 4046 = "No need to change margin type" (already set)
        if status == 200 or (isinstance(data, dict) and data.get("code") == -4046):
            logger.info(f"✅ Margin type: {margin_type} for {symbol}")
        return data

    def get_symbol_info(self, symbol: str):
        """Fetch precision info for a futures symbol."""
        data, _ = self._request("GET", "/fapi/v1/exchangeInfo", {})
        if "symbols" in data:
            for s in data["symbols"]:
                if s["symbol"] == symbol:
                    return s
        return None

    def _round_qty(self, quantity: float, symbol_info: dict) -> float:
        """Round quantity to allowed step size."""
        for f in symbol_info.get("filters", []):
            if f["filterType"] == "LOT_SIZE":
                step = float(f["stepSize"])
                precision = len(f["stepSize"].rstrip("0").split(".")[-1])
                return round(quantity - (quantity % step), precision)
        return round(quantity, 3)

    def _round_price(self, price: float, symbol_info: dict) -> float:
        """Round price to allowed tick size."""
        for f in symbol_info.get("filters", []):
            if f["filterType"] == "PRICE_FILTER":
                tick = float(f["tickSize"])
                precision = len(f["tickSize"].rstrip("0").split(".")[-1])
                return round(price - (price % tick), precision)
        return round(price, 2)

    # ------------------------------------------------------------------ #
    #  Trade execution                                                    #
    # ------------------------------------------------------------------ #

    def execute_signal(self, signal: dict):
        """
        Takes a signal dict from SignalGenerator and places:
        1. A MARKET entry order
        2. A STOP_MARKET stop-loss
        3. A TAKE_PROFIT_MARKET at TP1
        """
        if not self.enabled:
            logger.info("🔕 Trade skipped — futures trading not enabled (no API keys).")
            return None

        symbol = signal["PAIR"]
        side = "BUY" if signal["TYPE"] == "BUY" else "SELL"
        close_side = "SELL" if side == "BUY" else "BUY"
        entry = signal["ENTRY"]
        sl = signal["STOP_LOSS"]

        # Parse TP string "tp1 / tp2 / tp3"
        tp_parts = signal["TAKE_PROFIT"].split(" / ")
        tp1 = float(tp_parts[0].strip())

        try:
            # Fetch symbol info for precision
            sym_info = self.get_symbol_info(symbol)
            if not sym_info:
                logger.error(f"Symbol {symbol} not found on exchange")
                return None

            # Set leverage & margin
            self.set_leverage(symbol)
            self.set_margin_type(symbol)

            # Calculate quantity: (trade_usdt * leverage) / entry_price
            notional = self.trade_usdt * self.leverage
            quantity = notional / entry
            quantity = self._round_qty(quantity, sym_info)
            sl_price = self._round_price(sl, sym_info)
            tp_price = self._round_price(tp1, sym_info)

            logger.info(
                f"📤 Placing {side} order: {symbol} | Qty: {quantity} | "
                f"SL: {sl_price} | TP1: {tp_price}"
            )

            # 1. Market entry
            entry_resp, entry_status = self._request("POST", "/fapi/v1/order", {
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                "quantity": quantity,
            })

            if entry_status != 200:
                logger.error(f"Entry order failed: {entry_resp}")
                return entry_resp

            logger.info(f"✅ Entry filled: {entry_resp.get('orderId')}")

            # 2. Stop-loss
            sl_resp, _ = self._request("POST", "/fapi/v1/order", {
                "symbol": symbol,
                "side": close_side,
                "type": "STOP_MARKET",
                "stopPrice": sl_price,
                "closePosition": "true",
            })
            logger.info(f"🛑 Stop-loss placed at {sl_price}: {sl_resp.get('orderId', sl_resp)}")

            # 3. Take-profit
            tp_resp, _ = self._request("POST", "/fapi/v1/order", {
                "symbol": symbol,
                "side": close_side,
                "type": "TAKE_PROFIT_MARKET",
                "stopPrice": tp_price,
                "closePosition": "true",
            })
            logger.info(f"🎯 Take-profit placed at {tp_price}: {tp_resp.get('orderId', tp_resp)}")

            return {
                "entry": entry_resp,
                "stop_loss": sl_resp,
                "take_profit": tp_resp,
            }

        except Exception as e:
            logger.error(f"Trade execution error: {e}", exc_info=True)
            return None
