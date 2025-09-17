# indicators/rsi.py with ICP-specific adjustments
import pandas as pd

def calculate_rsi(df: pd.DataFrame, symbol="", period: int = 14) -> tuple[float, str]:
    """
    Calculates RSI from closing prices with coin-specific thresholds.
    Returns: (RSI value, signal: 'overbought', 'oversold', or 'neutral')
    """
    if df is None or df.empty or "close" not in df.columns:
        return 50.0, "neutral"

    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    latest_rsi = rsi.iloc[-1]

    if pd.isna(latest_rsi):
        return 50.0, "neutral"

    # Coin-specific thresholds with ICP special handling
    less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT', 'BNBUSDT']
    is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)
    is_icp = 'ICPUSDT' in symbol.upper()
    
    if is_icp:
        # ICP-specific thresholds - moderate sensitivity
        if latest_rsi > 65:
            return latest_rsi, "overbought"
        elif latest_rsi < 35:
            return latest_rsi, "oversold"
        else:
            return latest_rsi, "neutral"
    elif is_less_volatile:
        # More sensitive thresholds for other less volatile coins - using 60/40 as suggested
        if latest_rsi > 60:
            return latest_rsi, "overbought"
        elif latest_rsi < 40:
            return latest_rsi, "oversold"
        else:
            return latest_rsi, "neutral"
    else:
        # Conservative thresholds for volatile coins (original values)
        if latest_rsi > 75:
            return latest_rsi, "overbought"
        elif latest_rsi < 25:
            return latest_rsi, "oversold"
        else:
            return latest_rsi, "neutral"


# # indicators/rsi.py with ICP-specific adjustments
# import pandas as pd

# def calculate_rsi(df: pd.DataFrame, symbol="", period: int = 14) -> tuple[float, str]:
#     """
#     Calculates RSI from closing prices with coin-specific thresholds.
#     Returns: (RSI value, signal: 'overbought', 'oversold', or 'neutral')
#     """
#     if df is None or df.empty or "close" not in df.columns:
#         return 50.0, "neutral"

#     delta = df["close"].diff()
#     gain = delta.where(delta > 0, 0.0)
#     loss = -delta.where(delta < 0, 0.0)

#     alpha = 1.0 / period
#     avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
#     avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

#     rs = avg_gain / avg_loss
#     rsi = 100 - (100 / (1 + rs))

#     latest_rsi = rsi.iloc[-1]

#     if pd.isna(latest_rsi):
#         return 50.0, "neutral"

#     # Coin-specific thresholds with ICP special handling
#     less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT']
#     is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)
#     is_icp = 'ICPUSDT' in symbol.upper()
    
#     if is_icp:
#         # ICP-specific thresholds - slightly more conservative
#         if latest_rsi > 72:
#             return latest_rsi, "overbought"
#         elif latest_rsi < 28:
#             return latest_rsi, "oversold"
#         else:
#             return latest_rsi, "neutral"
#     elif is_less_volatile:
#         # More sensitive thresholds for other less volatile coins
#         if latest_rsi > 70:
#             return latest_rsi, "overbought"
#         elif latest_rsi < 30:
#             return latest_rsi, "oversold"
#         else:
#             return latest_rsi, "neutral"
#     else:
#         # Conservative thresholds for volatile coins (original values)
#         if latest_rsi > 75:
#             return latest_rsi, "overbought"
#         elif latest_rsi < 25:
#             return latest_rsi, "oversold"
#         else:
#             return latest_rsi, "neutral"