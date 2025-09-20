# strategies/trend_sentiment_strategy.py
from indicators.trend import identify_trend

def trend_sentiment_signal(df, sentiment, symbol=""):
    trend = identify_trend(df)
    
    # Coin-specific sensitivity
    less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT', 'BNBUSDT']
    is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)
    is_icp = 'ICPUSDT' in symbol.upper()
    
    if is_icp:
        # ICP-specific combinations with moderate sensitivity
        if trend == "uptrend" and sentiment == "bullish":
            signal, confidence = "BUY", 78
        elif trend == "downtrend" and sentiment == "bearish":
            signal, confidence = "SELL", 78
        elif trend == "uptrend" and sentiment == "neutral":
            signal, confidence = "BUY", 66
        elif trend == "downtrend" and sentiment == "neutral":
            signal, confidence = "SELL", 66
        elif trend == "sideways" and sentiment == "bullish":
            signal, confidence = "BUY", 62
        elif trend == "sideways" and sentiment == "bearish":
            signal, confidence = "SELL", 62
        elif trend == "uptrend" and sentiment == "bearish":
            signal, confidence = "HOLD", 54
        elif trend == "downtrend" and sentiment == "bullish":
            signal, confidence = "HOLD", 54
        else:
            signal, confidence = "HOLD", 50
    elif is_less_volatile:
        # Enhanced granular combinations for other less volatile coins
        if trend == "uptrend" and sentiment == "bullish":
            signal, confidence = "BUY", 80  # Increased confidence
        elif trend == "downtrend" and sentiment == "bearish":
            signal, confidence = "SELL", 80  # Increased confidence
        elif trend == "uptrend" and sentiment == "neutral":
            signal, confidence = "BUY", 68  # Increased confidence
        elif trend == "downtrend" and sentiment == "neutral":
            signal, confidence = "SELL", 68  # Increased confidence
        elif trend == "sideways" and sentiment == "bullish":
            signal, confidence = "BUY", 65  # Increased confidence
        elif trend == "sideways" and sentiment == "bearish":
            signal, confidence = "SELL", 65  # Increased confidence
        elif trend == "uptrend" and sentiment == "bearish":
            signal, confidence = "HOLD", 55  # Slight positive bias in uptrend
        elif trend == "downtrend" and sentiment == "bullish":
            signal, confidence = "HOLD", 55  # Slight negative bias in downtrend
        # Additional nuanced signals
        elif trend == "sideways" and sentiment == "neutral":
            signal, confidence = "HOLD", 52
        else:
            signal, confidence = "HOLD", 50
    else:
        # Conservative logic for volatile coins
        if trend == "uptrend" and sentiment == "bullish":
            signal, confidence = "BUY", 75
        elif trend == "downtrend" and sentiment == "bearish":
            signal, confidence = "SELL", 75
        else:
            signal, confidence = "HOLD", 50

    return {"strategy": "Trend+Sentiment", "signal": signal, "confidence": confidence}


# # strategies/trend_sentiment_strategy.py
# from indicators.trend import identify_trend

# def trend_sentiment_signal(df, sentiment, symbol=""):
#     trend = identify_trend(df)
    
#     # Coin-specific sensitivity
#     less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT']
#     is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)
    
#     if is_less_volatile:
#         # More granular combinations for less volatile coins
#         if trend == "uptrend" and sentiment == "bullish":
#             signal, confidence = "BUY", 75
#         elif trend == "downtrend" and sentiment == "bearish":
#             signal, confidence = "SELL", 75
#         elif trend == "uptrend" and sentiment == "neutral":
#             signal, confidence = "BUY", 62
#         elif trend == "downtrend" and sentiment == "neutral":
#             signal, confidence = "SELL", 62
#         elif trend == "sideways" and sentiment == "bullish":
#             signal, confidence = "BUY", 58
#         elif trend == "sideways" and sentiment == "bearish":
#             signal, confidence = "SELL", 58
#         elif trend == "uptrend" and sentiment == "bearish":
#             signal, confidence = "HOLD", 52
#         elif trend == "downtrend" and sentiment == "bullish":
#             signal, confidence = "HOLD", 52
#         else:
#             signal, confidence = "HOLD", 50
#     else:
#         # Conservative logic for volatile coins
#         if trend == "uptrend" and sentiment == "bullish":
#             signal, confidence = "BUY", 75
#         elif trend == "downtrend" and sentiment == "bearish":
#             signal, confidence = "SELL", 75
#         else:
#             signal, confidence = "HOLD", 50

#     return {"strategy": "Trend+Sentiment", "signal": signal, "confidence": confidence}