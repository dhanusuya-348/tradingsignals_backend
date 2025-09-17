# indicators/volatility.py

import pandas as pd

def calculate_volatility(df):
    if df is None or df.empty or "close" not in df.columns:
        return "unknown"

    close = df["close"]
    returns = close.pct_change()
    
    # Use multiple timeframes for better volatility assessment
    short_vol = returns.rolling(window=5).std()   
    med_vol = returns.rolling(window=14).std()    
    long_vol = returns.rolling(window=30).std()  

    latest_short = short_vol.iloc[-1]
    latest_med = med_vol.iloc[-1]
    latest_long = long_vol.iloc[-1]
    
    # Get percentile-based thresholds for more adaptive classification
    med_vol_clean = med_vol.dropna()
    if len(med_vol_clean) < 10:
        return "medium"
    
    # Use percentiles for dynamic thresholds
    high_threshold = med_vol_clean.quantile(0.75)
    low_threshold = med_vol_clean.quantile(0.25)
    
    # Weight recent volatility more heavily
    weighted_vol = (latest_short * 0.5 + latest_med * 0.3 + latest_long * 0.2)
    
    if pd.isna(weighted_vol):
        return "medium"
    
    if weighted_vol > high_threshold * 1.2:
        return "high"
    elif weighted_vol < low_threshold * 0.8:
        return "low"
    else:
        return "medium"