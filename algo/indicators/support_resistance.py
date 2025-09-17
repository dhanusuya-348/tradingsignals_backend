#indicators\support_resistance.py

import pandas as pd
import numpy as np
from scipy.signal import argrelextrema

def get_support_resistance_levels(df, window=20, order=5):
    """
    Detects support and resistance levels using local minima and maxima.
    
    Args:
        df (pd.DataFrame): Historical price DataFrame with 'close' column.
        window (int): Rolling window to smooth noise (optional).
        order (int): How many candles to consider on each side for local extrema.

    Returns:
        dict: {'support': [list of floats], 'resistance': [list of floats]}
    """
    if df.empty or 'close' not in df.columns:
        return {'support': [], 'resistance': []}

    close_series = df['close'].rolling(window=window).mean() if window > 1 else df['close']

    # Find local minima (support) and maxima (resistance)
    local_min_idx = argrelextrema(close_series.values, np.less_equal, order=order)[0]
    local_max_idx = argrelextrema(close_series.values, np.greater_equal, order=order)[0]

    support_levels = sorted(set([round(df['low'].iloc[i], 2) for i in local_min_idx]))
    resistance_levels = sorted(set([round(df['high'].iloc[i], 2) for i in local_max_idx]))

    return {
        'support': support_levels,
        'resistance': resistance_levels
    }
