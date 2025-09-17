# indicators/volume.py

import pandas as pd

def calculate_volume_metrics(df: pd.DataFrame, period: int = 20) -> dict:
    """
    Calculates various volume metrics to assess market interest and signal strength.

    Args:
        df (pd.DataFrame): DataFrame with 'close', 'open', 'high', 'low', 'volume' columns.
        period (int): Lookback period for moving averages and standard deviation.

    Returns:
        dict: A dictionary containing volume metrics and signals.
    """
    if df is None or df.empty or "volume" not in df.columns or len(df) < period:
        return {
            "volume_value": 0.0,
            "volume_avg": 0.0,
            "volume_change_percent": 0.0,
            "volume_signal": "neutral",
            "obv": 0.0,
            "obv_signal": "neutral"
        }

    # --- Volume Analysis ---
    volume = df["volume"]
    current_volume = volume.iloc[-1]
    volume_avg = volume.iloc[-period:].mean() # Simple moving average of volume
    
    # Avoid division by zero
    volume_change_percent = ((current_volume - volume_avg) / volume_avg) * 100 if volume_avg != 0 else 0.0

    volume_signal = "neutral"
    if current_volume > volume_avg * 1.5: # Significantly higher volume
        volume_signal = "high_volume"
    elif current_volume < volume_avg * 0.5: # Significantly lower volume
        volume_signal = "low_volume"
    
    # --- On-Balance Volume (OBV) ---
    obv = pd.Series(0.0, index=df.index)
    obv.iloc[0] = 0 # Initialize OBV

    for i in range(1, len(df)):
        if df["close"].iloc[i] > df["close"].iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] + df["volume"].iloc[i]
        elif df["close"].iloc[i] < df["close"].iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] - df["volume"].iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]
            
    obv_ema = obv.ewm(span=10, adjust=False).mean() # 10-period EMA for OBV signal line
    
    obv_signal = "neutral"
    if obv.iloc[-1] > obv_ema.iloc[-1] and obv.iloc[-2] <= obv_ema.iloc[-2]: # OBV crosses above its EMA
        obv_signal = "bullish"
    elif obv.iloc[-1] < obv_ema.iloc[-1] and obv.iloc[-2] >= obv_ema.iloc[-2]: # OBV crosses below its EMA
        obv_signal = "bearish"

    return {
        "volume_value": current_volume,
        "volume_avg": volume_avg,
        "volume_change_percent": round(volume_change_percent, 2),
        "volume_signal": volume_signal,
        "obv": obv.iloc[-1],
        "obv_signal": obv_signal
    }

