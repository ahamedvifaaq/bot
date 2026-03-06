import pandas as pd
import numpy as np

class MarketStructure:
    """
    Detects swing highs, swing lows, and determines market trends (Bullish, Bearish, Ranging).
    """
    def __init__(self, swing_length=5):
        self.swing_length = swing_length

    def find_swings(self, df):
        """Identifies pivot highs and lows in the dataframe."""
        df['is_swing_high'] = False
        df['is_swing_low'] = False
        
        # A pivot is valid if it's the highest/lowest in a window (left_len = right_len = swing_length)
        # Note: We can only confirm a pivot n periods AFTER it happens
        
        rolling_max = df['high'].rolling(window=2*self.swing_length+1, center=True).max()
        rolling_min = df['low'].rolling(window=2*self.swing_length+1, center=True).min()
        
        df.loc[df['high'] == rolling_max, 'is_swing_high'] = True
        df.loc[df['low'] == rolling_min, 'is_swing_low'] = True
        
        return df

    def classify_structure(self, df):
        """Assigns HH, HL, LH, LL labels to valid swings and sets market trend state."""
        df = self.find_swings(df)
        
        df['struct_label'] = None
        df['trend'] = 'RANGING'
        
        last_high = None
        last_low = None
        current_trend = 'RANGING'
        
        labels = []
        trends = []
        
        for i in range(len(df)):
            high_val = df['high'].iloc[i]
            low_val = df['low'].iloc[i]
            is_sh = df['is_swing_high'].iloc[i]
            is_sl = df['is_swing_low'].iloc[i]
            
            label = None
            
            if is_sh:
                if last_high is None:
                    label = 'SH'
                elif high_val > last_high:
                    label = 'HH'
                else:
                    label = 'LH'
                last_high = high_val
                
            if is_sl:
                if last_low is None:
                    label = 'SL'
                elif low_val > last_low:
                    label = 'HL'
                else:
                    label = 'LL'
                last_low = low_val
                
            labels.append(label)
            
            # Trend determination logic based on recent swings
            # Bullish = Forming HH and HL
            # Bearish = Forming LH and LL
            if label == 'HH' and last_low is not None:
                current_trend = 'BULLISH'
            elif label == 'LL' and last_high is not None:
                current_trend = 'BEARISH'
            # (Ranging definition can be refined based on crossing highs/lows)
            
            trends.append(current_trend)
            
        df['struct_label'] = labels
        df['trend'] = trends
        
        return df
