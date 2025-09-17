# indicators/macd.py with ICP-specific adjustments
import pandas as pd

def calculate_macd(df, symbol=""):
    if df is None or df.empty or "close" not in df.columns:
        return "neutral"

    close = df["close"]
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    macd_line = ema50 - ema200
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line

    current_hist = histogram.iloc[-1]
    prev_hist = histogram.iloc[-2] if len(histogram) > 1 else current_hist

    # Coin-specific noise filter with ICP special handling
    less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT', 'BNBUSDT']
    is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)
    is_icp = 'ICPUSDT' in symbol.upper()
    
    if is_icp:
        threshold = 0.15  # Slightly higher threshold for ICP - needs clearer signals
    elif is_less_volatile:
        threshold = 0.1  # More sensitive for other less volatile coins
    else:
        threshold = 0.3

    if current_hist > threshold and prev_hist <= threshold:
        return "bullish"
    elif current_hist < -threshold and prev_hist >= -threshold:
        return "bearish"
    elif current_hist > prev_hist and current_hist > threshold:
        return "bullish"
    elif current_hist < prev_hist and current_hist < -threshold:
        return "bearish"
    elif abs(current_hist) < threshold:
        return "neutral"
    else:
        return "bullish" if current_hist > 0 else "bearish"