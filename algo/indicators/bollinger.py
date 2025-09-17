# indicators/bollinger.py

import pandas as pd

def calculate_bollinger_bands(df, window=20, num_std_dev=2):
    if df is None or df.empty or "close" not in df.columns:
        return "within_range"

    close = df["close"]
    sma = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    upper_band = sma + num_std_dev * std
    lower_band = sma - num_std_dev * std

    latest_price = close.iloc[-1]
    prev_price = close.iloc[-2] if len(close) > 1 else latest_price
    
    # Get band values
    latest_upper = upper_band.iloc[-1]
    latest_lower = lower_band.iloc[-1]
    prev_upper = upper_band.iloc[-2] if len(upper_band) > 1 else latest_upper
    prev_lower = lower_band.iloc[-2] if len(lower_band) > 1 else latest_lower

    # More sophisticated breakout detection
    # Check for sustained breakout, not just single candle
    upper_breach = latest_price > latest_upper
    lower_breach = latest_price < latest_lower
    
    # Previous candle context
    prev_upper_breach = prev_price > prev_upper
    prev_lower_breach = prev_price < prev_lower
    
    # Strong breakout - current and previous both outside bands
    if upper_breach and prev_upper_breach:
        return "breakout_up"
    elif lower_breach and prev_lower_breach:
        return "breakout_down"
    # Fresh breakout - just crossed the band
    elif upper_breach and not prev_upper_breach:
        return "breakout_up"
    elif lower_breach and not prev_lower_breach:
        return "breakout_down"
    # Close to bands but not breached - still within range
    else:
        return "within_range"