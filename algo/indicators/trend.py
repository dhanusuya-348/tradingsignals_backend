#indicators\trend.py
import pandas as pd

def calculate_ema(df, periods=[20, 50]):
    df = df.copy()
    for period in periods:
        df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
    return df

def identify_trend(df):
    df = calculate_ema(df, periods=[20, 50])

    # Ensure safe access
    if len(df.dropna()) < 50 or "ema_20" not in df.columns or "ema_50" not in df.columns:
        return "sideways"
    try:
        ema_20 = df["ema_20"].iloc[-1]
        ema_50 = df["ema_50"].iloc[-1]
    except Exception:
        return "sideways"

    if ema_20 > ema_50:
        return "uptrend"
    elif ema_20 < ema_50:
        return "downtrend"
    else:
        return "sideways"
