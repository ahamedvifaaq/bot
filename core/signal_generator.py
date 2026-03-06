import logging
from core.risk_management import RiskManagement
from ml.predictor import MLPredictor

logger = logging.getLogger(__name__)


class SignalGenerator:
    """
    Evaluates combined technical factors to generate BUY or SELL signals.
    """

    def __init__(self, min_probability=65.0):
        self.min_probability = min_probability
        self.risk_manager = RiskManagement()
        self.predictor = MLPredictor()

    def check_signals(self, df, symbol, interval):
        """
        BUY: Bullish trend + (Sweep OR OB/FVG) + (Rejection OR Volume Spike)
        SELL: Bearish trend + (Sweep OR OB/FVG) + (Rejection OR Volume Spike)
        """
        if len(df) < 5:
            return None

        i = len(df) - 1
        row = df.iloc[i]

        signal = None
        sweep_extreme = None

        # --- BUY conditions ---
        is_bullish_trend = row.get("trend") == "BULLISH"
        is_bull_sweep = bool(row.get("sweep_bullish", False))
        in_bull_ob = bool(row.get("ob_bullish", False)) or bool(row.get("fvg_bullish", False))
        is_bull_rejection = bool(row.get("is_bullish_rejection", False))
        is_vol_spike = bool(row.get("is_volume_spike", False))

        # --- SELL conditions ---
        is_bearish_trend = row.get("trend") == "BEARISH"
        is_bear_sweep = bool(row.get("sweep_bearish", False))
        in_bear_ob = bool(row.get("ob_bearish", False)) or bool(row.get("fvg_bearish", False))
        is_bear_rejection = bool(row.get("is_bearish_rejection", False))

        buy_condition = is_bullish_trend and (is_bull_sweep or in_bull_ob) and (is_bull_rejection or is_vol_spike)
        sell_condition = is_bearish_trend and (is_bear_sweep or in_bear_ob) and (is_bear_rejection or is_vol_spike)

        if buy_condition:
            signal = "BUY"
            atr = row.get("atr_14", row["close"] * 0.005)
            sweep_extreme = row["low"] - (atr * 0.5)
        elif sell_condition:
            signal = "SELL"
            atr = row.get("atr_14", row["close"] * 0.005)
            sweep_extreme = row["high"] + (atr * 0.5)

        if not signal:
            return None

        # ML probability gate
        features = self.predictor.extract_features_for_inference(df, i)
        probability = self.predictor.predict_probability(features, signal)

        if probability < self.min_probability:
            logger.info(f"⛔ Signal rejected: probability {probability}% < {self.min_probability}%")
            return None

        # Risk management
        entry_price = row["close"]
        trade_params = self.risk_manager.calculate_trade_parameters(entry_price, signal, sweep_extreme)
        if not trade_params:
            return None

        final_signal = {
            "PAIR": symbol,
            "TIMEFRAME": interval,
            "TYPE": signal,
            "ENTRY": trade_params["entry"],
            "STOP_LOSS": trade_params["stop_loss"],
            "TAKE_PROFIT": f"{trade_params['tp1']} / {trade_params['tp2']} / {trade_params['tp3']}",
            "PROBABILITY": f"{probability}%",
            "TIMESTAMP": str(row.get("timestamp", "")),
        }
        return final_signal
