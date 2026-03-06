import pandas as pd
import numpy as np

class InstitutionalZones:
    """
    Detects Order Blocks and Fair Value Gaps (FVG).
    """
    def __init__(self, fvg_min_size=0.0):
        # fvg_min_size can require a minimum absolute size of the imbalance
        self.fvg_min_size = fvg_min_size

    def detect_fvg(self, df):
        """
        Detects Fair Value Gaps.
        Bullish FVG: Low of candle[i] > High of candle[i-2]
        Bearish FVG: High of candle[i] < Low of candle[i-2]
        """
        df['fvg_bullish'] = False
        df['fvg_bearish'] = False
        df['fvg_bull_top'] = np.nan
        df['fvg_bull_bottom'] = np.nan
        df['fvg_bear_top'] = np.nan
        df['fvg_bear_bottom'] = np.nan
        
        # Shift to compare candle 1 with candle 3
        # In Pandas, iloc[i] is candle 3, iloc[i-2] is candle 1
        high_lag2 = df['high'].shift(2)
        low_lag2 = df['low'].shift(2)
        
        # Bullish FVG conditions
        bullish_fvg = df['low'] > high_lag2
        df.loc[bullish_fvg, 'fvg_bullish'] = True
        df.loc[bullish_fvg, 'fvg_bull_top'] = df['low']
        df.loc[bullish_fvg, 'fvg_bull_bottom'] = high_lag2
        
        # Bearish FVG conditions
        bearish_fvg = df['high'] < low_lag2
        df.loc[bearish_fvg, 'fvg_bearish'] = True
        df.loc[bearish_fvg, 'fvg_bear_top'] = low_lag2
        df.loc[bearish_fvg, 'fvg_bear_bottom'] = df['high']
        
        return df

    def detect_order_blocks(self, df):
        """
        Detects Order Blocks.
        Bullish: Last bearish candle before a strong bullish move.
        Bearish: Last bullish candle before a strong bearish move.
        We proxy "strong move" by checking if the subsequent move creates an FVG 
        or breaks structure (simple momentum check here).
        """
        df['ob_bullish'] = False
        df['ob_bearish'] = False
        df['ob_top'] = np.nan
        df['ob_bottom'] = np.nan
        
        # Check for FVG existence to confirm displacement
        if 'fvg_bullish' not in df.columns:
            df = self.detect_fvg(df)
            
        is_bearish_candle = df['close'] < df['open']
        is_bullish_candle = df['close'] > df['open']
        
        for i in range(2, len(df)):
            if df['fvg_bullish'].iloc[i]:
                # Look backwards from the FVG for the last bearish candle (the order block)
                for j in range(i-1, max(-1, i-5), -1):
                    if is_bearish_candle.iloc[j]:
                        df.at[j, 'ob_bullish'] = True
                        df.at[j, 'ob_top'] = df['high'].iloc[j]
                        df.at[j, 'ob_bottom'] = df['low'].iloc[j]
                        break
                        
            if df['fvg_bearish'].iloc[i]:
                for j in range(i-1, max(-1, i-5), -1):
                    if is_bullish_candle.iloc[j]:
                        df.at[j, 'ob_bearish'] = True
                        df.at[j, 'ob_top'] = df['high'].iloc[j]
                        df.at[j, 'ob_bottom'] = df['low'].iloc[j]
                        break
                        
        return df

    def is_in_zone(self, price, zone_top, zone_bottom):
        """Helper to check if price is inside a zone"""
        return zone_bottom <= price <= zone_top
