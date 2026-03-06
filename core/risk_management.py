class RiskManagement:
    """
    Calculates Stop Loss (SL) and Take Profit (TP) levels based on risk.
    """
    def __init__(self, max_risk_percentage=1.0):
        self.max_risk_percentage = max_risk_percentage

    def calculate_trade_parameters(self, entry_price, signal_type, sweep_extreme):
        """
        Calculates SL and TP levels based on 1R, 2R, 3R.
        sweep_extreme: The lowest/highest point of the liquidity sweep for the exact SL.
        """
        if signal_type == "BUY":
            sl = sweep_extreme # Stop loss below the sweep low
            risk_distance = entry_price - sl
            
            # Avoid divide by zero
            if risk_distance <= 0:
                risk_distance = entry_price * 0.005 # 0.5% default fallback
                sl = entry_price - risk_distance
                
            tp1 = entry_price + (risk_distance * 1)
            tp2 = entry_price + (risk_distance * 2)
            tp3 = entry_price + (risk_distance * 3)
            
        elif signal_type == "SELL":
            sl = sweep_extreme # Stop loss above the sweep high
            risk_distance = sl - entry_price
            
            if risk_distance <= 0:
                risk_distance = entry_price * 0.005 # 0.5% default fallback
                sl = entry_price + risk_distance
                
            tp1 = entry_price - (risk_distance * 1)
            tp2 = entry_price - (risk_distance * 2)
            tp3 = entry_price - (risk_distance * 3)
        else:
            return None
            
        return {
            "entry": round(entry_price, 4),
            "stop_loss": round(sl, 4),
            "tp1": round(tp1, 4),
            "tp2": round(tp2, 4),
            "tp3": round(tp3, 4),
            "risk_per_trade_percent": self.max_risk_percentage
        }
