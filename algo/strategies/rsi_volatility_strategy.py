# strategies/rsi_volatility_strategy.py
from indicators.rsi import calculate_rsi
from indicators.volatility import calculate_volatility
from indicators.trend import identify_trend

def rsi_volatility_signal(df, symbol=""):
    if len(df) < 14:
        return {"strategy": "RSI+Volatility", "signal": "HOLD", "confidence": 50}

    try:
        rsi_val, rsi_signal = calculate_rsi(df, symbol)  # Pass symbol for coin-specific thresholds
        volatility = calculate_volatility(df)
        trend = identify_trend(df)  # Add trend context for better RSI interpretation
    except Exception:
        return {"strategy": "RSI+Volatility", "signal": "HOLD", "confidence": 50}

    # Coin-specific sensitivity
    less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT', 'BNBUSDT']
    is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)
    is_icp = 'ICPUSDT' in symbol.upper()

    # Enhanced RSI logic with trend consideration
    if is_less_volatile:
        # More granular RSI thresholds for less volatile coins with trend context
        if rsi_signal == "oversold":
            # In uptrend, oversold is more reliable for buying
            if trend == "uptrend":
                confidence = 72 if volatility == "low" else 68
                signal = "BUY"
            # In downtrend, oversold might be a dead cat bounce - be cautious
            elif trend == "downtrend":
                confidence = 58 if volatility == "low" else 55
                signal = "BUY"
            else:  # sideways
                confidence = 65 if volatility == "low" else 62
                signal = "BUY"
        elif rsi_signal == "overbought":
            # In downtrend, overbought is more reliable for selling
            if trend == "downtrend":
                confidence = 72 if volatility == "high" else 68
                signal = "SELL"
            # In uptrend, overbought might continue - be cautious
            elif trend == "uptrend":
                confidence = 58 if volatility == "high" else 55
                signal = "SELL"
            else:  # sideways
                confidence = 65 if volatility == "high" else 62
                signal = "SELL"
        # Additional signals for less volatile coins using 60/40 thresholds
        elif 35 < rsi_val < 40 and trend == "uptrend":
            signal, confidence = "BUY", 60
        elif 60 < rsi_val < 65 and trend == "downtrend":
            signal, confidence = "SELL", 60
        elif rsi_val < 35 and volatility == "low":
            signal, confidence = "BUY", 58
        elif rsi_val > 65 and volatility == "high":
            signal, confidence = "SELL", 58
        elif rsi_val < 45:
            signal, confidence = "BUY", 55
        elif rsi_val > 55:
            signal, confidence = "SELL", 55
        else:
            signal, confidence = "HOLD", 50
    elif is_icp:
        # ICP-specific logic with moderate sensitivity
        if rsi_signal == "oversold":
            if trend == "uptrend":
                confidence = 70 if volatility == "low" else 65
                signal = "BUY"
            elif trend == "downtrend":
                confidence = 60 if volatility == "low" else 58
                signal = "BUY"
            else:
                confidence = 65 if volatility == "low" else 62
                signal = "BUY"
        elif rsi_signal == "overbought":
            if trend == "downtrend":
                confidence = 70 if volatility == "high" else 65
                signal = "SELL"
            elif trend == "uptrend":
                confidence = 60 if volatility == "high" else 58
                signal = "SELL"
            else:
                confidence = 65 if volatility == "high" else 62
                signal = "SELL"
        elif rsi_val < 40 and trend == "uptrend":
            signal, confidence = "BUY", 58
        elif rsi_val > 60 and trend == "downtrend":
            signal, confidence = "SELL", 58
        else:
            signal, confidence = "HOLD", 50
    else:
        # Conservative logic for volatile coins with trend context
        if rsi_signal == "oversold":
            if trend == "uptrend" and volatility == "low":
                signal, confidence = "BUY", 70
            elif trend != "downtrend":
                signal, confidence = "BUY", 65
            else:
                signal, confidence = "HOLD", 52  # Avoid buying in strong downtrend
        elif rsi_signal == "overbought":
            if trend == "downtrend" and volatility == "high":
                signal, confidence = "SELL", 70
            elif trend != "uptrend":
                signal, confidence = "SELL", 65
            else:
                signal, confidence = "HOLD", 52  # Avoid selling in strong uptrend
        else:
            signal, confidence = "HOLD", 50

    return {"strategy": "RSI+Volatility", "signal": signal, "confidence": confidence}


# # strategies/rsi_volatility_strategy.py
# from indicators.rsi import calculate_rsi
# from indicators.volatility import calculate_volatility

# def rsi_volatility_signal(df, symbol=""):
#     if len(df) < 14:
#         return {"strategy": "RSI+Volatility", "signal": "HOLD", "confidence": 50}

#     try:
#         rsi_val, rsi_signal = calculate_rsi(df, symbol)  # Pass symbol for coin-specific thresholds
#         volatility = calculate_volatility(df)
#     except Exception:
#         return {"strategy": "RSI+Volatility", "signal": "HOLD", "confidence": 50}

#     # Coin-specific sensitivity
#     less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT']
#     is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)

#     if is_less_volatile:
#         # More granular RSI thresholds for less volatile coins
#         if rsi_signal == "oversold":
#             if volatility == "low":
#                 signal, confidence = "BUY", 68
#             else:
#                 signal, confidence = "BUY", 62
#         elif rsi_signal == "overbought":
#             if volatility == "high":
#                 signal, confidence = "SELL", 68
#             else:
#                 signal, confidence = "SELL", 62
#         elif rsi_val < 35 and volatility == "low":
#             signal, confidence = "BUY", 58
#         elif rsi_val > 65 and volatility == "high":
#             signal, confidence = "SELL", 58
#         elif rsi_val < 40:
#             signal, confidence = "BUY", 55
#         elif rsi_val > 60:
#             signal, confidence = "SELL", 55
#         else:
#             signal, confidence = "HOLD", 50
#     else:
#         # Conservative logic for volatile coins
#         if rsi_signal == "oversold" and volatility == "low":
#             signal, confidence = "BUY", 65
#         elif rsi_signal == "overbought" and volatility == "high":
#             signal, confidence = "SELL", 65
#         else:
#             signal, confidence = "HOLD", 50

#     return {"strategy": "RSI+Volatility", "signal": signal, "confidence": confidence}