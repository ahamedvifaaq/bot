import pandas as pd
import numpy as np

class FeatureExtractor:
    """
    Extracts features from OHLCV dataframes for signals and ML models.
    Calculates moving averages, ATR, volume features, and candlestick properties.
    """
    @staticmethod
    def calculate_ema(df, periods=[20, 50, 200]):
        """Calculate Exponential Moving Averages."""
        for period in periods:
            df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        return df

    @staticmethod
    def calculate_atr(df, period=14):
        """Calculate Average True Range."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        
        df[f'atr_{period}'] = true_range.rolling(period).mean()
        return df

    @staticmethod
    def extract_candle_features(df):
        """
        Extract candlestick properties:
        - Body size
        - Upper wick length
        - Lower wick length
        - Ratios
        """
        df['body_size'] = np.abs(df['close'] - df['open'])
        df['upper_wick'] = df['high'] - np.maximum(df['open'], df['close'])
        df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
        df['total_length'] = df['high'] - df['low']
        
        # Avoid division by zero
        epsilon = 1e-8
        df['body_ratio'] = df['body_size'] / (df['total_length'] + epsilon)
        df['upper_wick_ratio'] = df['upper_wick'] / (df['total_length'] + epsilon)
        df['lower_wick_ratio'] = df['lower_wick'] / (df['total_length'] + epsilon)
        
        # Identify strong rejection candles (e.g., pin bars)
        df['is_bullish_rejection'] = (df['lower_wick_ratio'] > 0.6) & (df['body_ratio'] < 0.3)
        df['is_bearish_rejection'] = (df['upper_wick_ratio'] > 0.6) & (df['body_ratio'] < 0.3)
        
        return df

    @staticmethod
    def calculate_volume_features(df, period=20):
        """Calculate volume spikes relative to moving average."""
        df['volume_ma'] = df['volume'].rolling(period).mean()
        df['volume_spike_ratio'] = df['volume'] / (df['volume_ma'] + 1e-8)
        df['is_volume_spike'] = df['volume_spike_ratio'] > 2.0  # Spike defined as 2x average
        return df
        
    @staticmethod
    def calculate_momentum(df, period=14):
        """Calculate simple momentum velocity (ROC)."""
        df[f'roc_{period}'] = ((df['close'] - df['close'].shift(period)) / df['close'].shift(period)) * 100
        return df

    @classmethod
    def apply_all_features(cls, df):
        """Applies all feature extractions cleanly to a copy of the dataframe."""
        df_feat = df.copy()
        df_feat = cls.calculate_ema(df_feat)
        df_feat = cls.calculate_atr(df_feat)
        df_feat = cls.extract_candle_features(df_feat)
        df_feat = cls.calculate_volume_features(df_feat)
        df_feat = cls.calculate_momentum(df_feat)
        
        # Drop rows with NaNs from rolling calculations to ensure clean ML/Signal data
        df_feat.dropna(inplace=True)
        return df_feat
