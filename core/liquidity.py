import pandas as pd
import numpy as np

class LiquidityEngine:
    """
    Detects Liquidity pools (EQH, EQL) and Liquidity Sweeps
    """
    def __init__(self, tolerance=0.001):
        self.tolerance = tolerance # 0.1% tolerance for "equal" highs/lows

    def detect_equal_levels(self, df):
        """Identifies Equal Highs (EQH) and Equal Lows (EQL) based on swings."""
        # Simple implementation: scanning recent swings to find matches within tolerance
        df['is_eqh'] = False
        df['is_eql'] = False
        df['liquidity_level'] = None
        
        # We need the swings from MarketStructure
        if 'is_swing_high' not in df.columns or 'is_swing_low' not in df.columns:
            return df
            
        recent_highs = []
        recent_lows = []
        
        for i in range(len(df)):
            if df['is_swing_high'].iloc[i]:
                high_price = df['high'].iloc[i]
                # Check against recent highs
                for rh in recent_highs[-5:]: # Check last 5 swings
                    if abs(rh - high_price) / high_price <= self.tolerance:
                        df.at[i, 'is_eqh'] = True
                        df.at[i, 'liquidity_level'] = (rh + high_price) / 2
                recent_highs.append(high_price)
                
            if df['is_swing_low'].iloc[i]:
                low_price = df['low'].iloc[i]
                for rl in recent_lows[-5:]:
                    if abs(rl - low_price) / low_price <= self.tolerance:
                        df.at[i, 'is_eql'] = True
                        df.at[i, 'liquidity_level'] = (rl + low_price) / 2
                recent_lows.append(low_price)
                
        return df

    def detect_sweeps(self, df):
        """
        Detects sweeps: Wick pokes above EQH / below EQL but body closes inside.
        Requires 'detect_equal_levels' to be run first or supply liquidity zones.
        """
        df['sweep_bullish'] = False # price swept below support/EQL and rejected up
        df['sweep_bearish'] = False # price swept above resistance/EQH and rejected down
        
        # We look back at defined liquidity levels (e.g. recent EQH/EQLs)
        # For a live signal we check if the current candle swept a known liquidity magnet
        known_liquidity = df['liquidity_level'].dropna().tolist()
        
        for i in range(len(df)):
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]
            close = df['close'].iloc[i]
            open_p = df['open'].iloc[i]
            
            # Check for sweep of any known level
            for level in known_liquidity:
                # Bearish sweep: High > Level, but Close < Level
                if high > level and max(open_p, close) < level:
                    df.at[i, 'sweep_bearish'] = True
                    
                # Bullish sweep: Low < Level, but Close > Level
                if low < level and min(open_p, close) > level:
                    df.at[i, 'sweep_bullish'] = True
                    
        return df
