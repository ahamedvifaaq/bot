import asyncio
import logging
import threading
from core.data_ingestion import BinanceDataFeed
from core.data_manager import DataManager
from core.features import FeatureExtractor
from core.market_structure import MarketStructure
from core.liquidity import LiquidityEngine
from core.order_blocks import InstitutionalZones
from core.signal_generator import SignalGenerator
from core.trader import BinanceFuturesTrader
from delivery.api import start_api, broadcast_signal
import dotenv

dotenv.load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TradingSystemController:
    def __init__(self):
        self.symbols = ["BTCUSDT", "ETHUSDT"]
        self.intervals = ["5m", "15m", "1h"]

        self.data_manager = DataManager(self.symbols, self.intervals)
        self.data_feed = BinanceDataFeed(self.symbols, self.intervals)

        self.market_struct = MarketStructure()
        self.liquidity = LiquidityEngine()
        self.institutional = InstitutionalZones()
        self.signal_gen = SignalGenerator(min_probability=65.0)
        self.trader = BinanceFuturesTrader()

        self.data_feed.register_callback(self.on_candle_close)
        self.signal_count = 0

    async def on_candle_close(self, symbol, interval, kline_data):
        """Pipeline triggered every time a candle closes on the websocket."""
        self.data_manager.update_candle(symbol, interval, kline_data)
        df_raw = self.data_manager.get_dataframe(symbol, interval)

        if len(df_raw) < 50:
            return

        try:
            # Feature extraction
            df = FeatureExtractor.apply_all_features(df_raw)

            # Market structure
            df = self.market_struct.classify_structure(df)

            # Liquidity
            df = self.liquidity.detect_equal_levels(df)
            df = self.liquidity.detect_sweeps(df)

            # Order blocks & FVGs
            df = self.institutional.detect_fvg(df)
            df = self.institutional.detect_order_blocks(df)

            # Signal evaluation
            signal = self.signal_gen.check_signals(df, symbol, interval)

            if signal:
                self.signal_count += 1
                logger.info(
                    f"\n{'='*60}\n"
                    f"🚨 SIGNAL #{self.signal_count}\n"
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

                # Broadcast to dashboard
                await broadcast_signal(signal)

                # Execute trade on Binance Futures Testnet
                trade_result = self.trader.execute_signal(signal)
                if trade_result:
                    logger.info(f"💰 Trade executed successfully!")
                    signal["TRADE_STATUS"] = "EXECUTED"
                    signal["ORDER_ID"] = trade_result.get("entry", {}).get("orderId", "N/A")
                else:
                    signal["TRADE_STATUS"] = "SKIPPED"

        except Exception as e:
            logger.error(f"Pipeline error for {symbol} {interval}: {e}", exc_info=True)

    async def run(self):
        logger.info("=" * 60)
        logger.info("🏦 Institutional Signal Engine Starting...")
        logger.info(f"   Leverage: {self.trader.leverage}x")
        logger.info(f"   Trade size: {self.trader.trade_usdt} USDT")
        logger.info(f"   Auto-trade: {'ENABLED ✅' if self.trader.enabled else 'DISABLED (no API keys)'}")
        logger.info("=" * 60)

        # Seed historical data
        self.data_manager.fetch_historical_data()

        logger.info("Historical data loaded. Starting live WebSocket stream...")
        logger.info("Dashboard available at: http://localhost:8000")

        # Start live stream
        await self.data_feed.start()


def run_background_api():
    try:
        start_api()
    except Exception as e:
        logger.error(f"API failed to start: {e}")


if __name__ == "__main__":
    api_thread = threading.Thread(target=run_background_api, daemon=True)
    api_thread.start()

    controller = TradingSystemController()
    try:
        asyncio.run(controller.run())
    except KeyboardInterrupt:
        logger.info("System shut down.")
