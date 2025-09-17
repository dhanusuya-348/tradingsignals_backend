# strategies/macd_ema_strategy.py
from indicators.macd import calculate_macd
from indicators.trend import calculate_ema

def macd_ema_signal(df, symbol=""):
    df = df.copy()

    if len(df) < 50:
        return {"strategy": "MACD+EMA", "signal": "HOLD", "confidence": 50}

    df = calculate_ema(df, periods=[50])

    if "ema_50" not in df.columns or df["ema_50"].isna().all():
        return {"strategy": "MACD+EMA", "signal": "HOLD", "confidence": 50}

    try:
        ema_50 = df["ema_50"].iloc[-1]
        price = df["close"].iloc[-1]
        macd_signal = calculate_macd(df, symbol)  # Pass symbol for coin-specific thresholds
    except Exception:
        return {"strategy": "MACD+EMA", "signal": "HOLD", "confidence": 50}

    # Coin-specific sensitivity
    less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT', 'BNBUSDT']
    is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)
    is_icp = 'ICPUSDT' in symbol.upper()

    if is_icp:
        # ICP-specific logic - moderate sensitivity
        if macd_signal == "bullish" and price > ema_50:
            signal, confidence = "BUY", 72
        elif macd_signal == "bearish" and price < ema_50:
            signal, confidence = "SELL", 72
        elif macd_signal == "bullish" and price > ema_50 * 0.997:  # Within 0.3% of EMA
            signal, confidence = "BUY", 62
        elif macd_signal == "bearish" and price < ema_50 * 1.003:  # Within 0.3% of EMA
            signal, confidence = "SELL", 62
        elif macd_signal == "neutral" and price > ema_50 * 1.008:  # Price 0.8% above EMA
            signal, confidence = "BUY", 58
        elif macd_signal == "neutral" and price < ema_50 * 0.992:  # Price 0.8% below EMA
            signal, confidence = "SELL", 58
        else:
            signal, confidence = "HOLD", 50
    elif is_less_volatile:
        # Enhanced sensitivity for other less volatile coins
        if macd_signal == "bullish" and price > ema_50:
            signal, confidence = "BUY", 75
        elif macd_signal == "bearish" and price < ema_50:
            signal, confidence = "SELL", 75
        elif macd_signal == "bullish" and price > ema_50 * 0.998:  # Within 0.2% of EMA
            signal, confidence = "BUY", 65
        elif macd_signal == "bearish" and price < ema_50 * 1.002:  # Within 0.2% of EMA
            signal, confidence = "SELL", 65
        elif macd_signal == "neutral" and price > ema_50 * 1.003:  # Price 0.3% above EMA
            signal, confidence = "BUY", 58
        elif macd_signal == "neutral" and price < ema_50 * 0.997:  # Price 0.3% below EMA
            signal, confidence = "SELL", 58
        # Additional signals for very subtle movements
        elif price > ema_50 * 1.001:  # Just 0.1% above EMA
            signal, confidence = "BUY", 55
        elif price < ema_50 * 0.999:  # Just 0.1% below EMA
            signal, confidence = "SELL", 55
        else:
            signal, confidence = "HOLD", 50
    else:
        # Conservative logic for volatile coins (BTC, ETH, etc.)
        if macd_signal == "bullish" and price > ema_50:
            signal, confidence = "BUY", 70
        elif macd_signal == "bearish" and price < ema_50:
            signal, confidence = "SELL", 70
        else:
            signal, confidence = "HOLD", 50

    return {"strategy": "MACD+EMA", "signal": signal, "confidence": confidence}


# # strategies/macd_ema_strategy.py
# from indicators.macd import calculate_macd
# from indicators.trend import calculate_ema

# def macd_ema_signal(df, symbol=""):
#     df = df.copy()

#     if len(df) < 50:
#         return {"strategy": "MACD+EMA", "signal": "HOLD", "confidence": 50}

#     df = calculate_ema(df, periods=[50])

#     if "ema_50" not in df.columns or df["ema_50"].isna().all():
#         return {"strategy": "MACD+EMA", "signal": "HOLD", "confidence": 50}

#     try:
#         ema_50 = df["ema_50"].iloc[-1]
#         price = df["close"].iloc[-1]
#         macd_signal = calculate_macd(df, symbol)  # Pass symbol for coin-specific thresholds
#     except Exception:
#         return {"strategy": "MACD+EMA", "signal": "HOLD", "confidence": 50}

#     # Coin-specific sensitivity
#     less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT']
#     is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)

#     if is_less_volatile:
#         # More sensitive logic for less volatile coins
#         if macd_signal == "bullish" and price > ema_50:
#             signal, confidence = "BUY", 70
#         elif macd_signal == "bearish" and price < ema_50:
#             signal, confidence = "SELL", 70
#         elif macd_signal == "bullish" and price > ema_50 * 0.998:  # Within 0.2% of EMA
#             signal, confidence = "BUY", 58
#         elif macd_signal == "bearish" and price < ema_50 * 1.002:  # Within 0.2% of EMA
#             signal, confidence = "SELL", 58
#         elif macd_signal == "neutral" and price > ema_50 * 1.005:  # Price 0.5% above EMA
#             signal, confidence = "BUY", 55
#         elif macd_signal == "neutral" and price < ema_50 * 0.995:  # Price 0.5% below EMA
#             signal, confidence = "SELL", 55
#         else:
#             signal, confidence = "HOLD", 50
#     else:
#         # Conservative logic for volatile coins (BTC, ETH, etc.)
#         if macd_signal == "bullish" and price > ema_50:
#             signal, confidence = "BUY", 70
#         elif macd_signal == "bearish" and price < ema_50:
#             signal, confidence = "SELL", 70
#         else:
#             signal, confidence = "HOLD", 50

#     return {"strategy": "MACD+EMA", "signal": signal, "confidence": confidence}