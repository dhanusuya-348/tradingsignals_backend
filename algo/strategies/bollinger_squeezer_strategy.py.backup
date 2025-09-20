# strategies/bollinger_squeezer_strategy.py
from indicators.bollinger import calculate_bollinger_bands
import pandas as pd

def bollinger_squeeze_signal(df, symbol=""):
    if len(df) < 20:
        return {"strategy": "Bollinger Squeeze", "signal": "HOLD", "confidence": 50}

    try:
        bb_signal = calculate_bollinger_bands(df)
        
        # Coin-specific sensitivity
        less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT', 'BNBUSDT']
        is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)
        is_icp = 'ICPUSDT' in symbol.upper()
        
        # Calculate band metrics for enhanced analysis
        close = df["close"]
        sma = close.rolling(window=20).mean()
        std = close.rolling(window=20).std()
        upper_band = sma + 2 * std
        lower_band = sma - 2 * std
        
        latest_price = close.iloc[-1]
        latest_sma = sma.iloc[-1]
        latest_upper = upper_band.iloc[-1]
        latest_lower = lower_band.iloc[-1]
        
        # Calculate position within bands (0 = lower band, 1 = upper band)
        band_position = (latest_price - latest_lower) / (latest_upper - latest_lower) if latest_upper != latest_lower else 0.5
        
    except Exception:
        return {"strategy": "Bollinger Squeeze", "signal": "HOLD", "confidence": 50}

    if bb_signal == "breakout_up":
        if is_less_volatile:
            signal, confidence = "BUY", 75  # Increased confidence for less volatile coins
        else:
            signal, confidence = "BUY", 70
    elif bb_signal == "breakout_down":
        if is_less_volatile:
            signal, confidence = "SELL", 75  # Increased confidence for less volatile coins
        else:
            signal, confidence = "SELL", 70
    elif is_icp:
        # ICP-specific logic with moderate thresholds
        if band_position > 0.75:
            signal, confidence = "SELL", 62
        elif band_position < 0.25:
            signal, confidence = "BUY", 62
        elif latest_price > latest_sma * 1.005:  # 0.5% above SMA
            signal, confidence = "BUY", 58
        elif latest_price < latest_sma * 0.995:  # 0.5% below SMA
            signal, confidence = "SELL", 58
        else:
            signal, confidence = "HOLD", 50
    elif is_less_volatile:
        # Enhanced sensitivity for other less volatile coins
        if band_position > 0.7:  # Reduced from 0.8
            signal, confidence = "SELL", 65  # Increased confidence
        elif band_position < 0.3:  # Increased from 0.2
            signal, confidence = "BUY", 65  # Increased confidence
        elif latest_price > latest_sma * 1.002:  # More sensitive - 0.2% above SMA
            signal, confidence = "BUY", 60
        elif latest_price < latest_sma * 0.998:  # More sensitive - 0.2% below SMA
            signal, confidence = "SELL", 60
        # Additional micro-signals for very subtle movements
        elif band_position > 0.6:
            signal, confidence = "SELL", 55
        elif band_position < 0.4:
            signal, confidence = "BUY", 55
        else:
            signal, confidence = "HOLD", 50
    else:
        # Conservative logic for volatile coins - keep original thresholds
        if band_position > 0.8:
            signal, confidence = "SELL", 58
        elif band_position < 0.2:
            signal, confidence = "BUY", 58
        elif latest_price > latest_sma * 1.003:
            signal, confidence = "BUY", 55
        elif latest_price < latest_sma * 0.997:
            signal, confidence = "SELL", 55
        else:
            signal, confidence = "HOLD", 50

    return {"strategy": "Bollinger Squeeze", "signal": signal, "confidence": confidence}


# # strategies/bollinger_squeezer_strategy.py
# from indicators.bollinger import calculate_bollinger_bands
# import pandas as pd

# def bollinger_squeeze_signal(df, symbol=""):
#     if len(df) < 20:
#         return {"strategy": "Bollinger Squeeze", "signal": "HOLD", "confidence": 50}

#     try:
#         bb_signal = calculate_bollinger_bands(df)
        
#         # Coin-specific sensitivity
#         less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT']
#         is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)
        
#         if is_less_volatile:
#             # Add position within bands analysis for less volatile coins
#             close = df["close"]
#             sma = close.rolling(window=20).mean()
#             std = close.rolling(window=20).std()
#             upper_band = sma + 2 * std
#             lower_band = sma - 2 * std
            
#             latest_price = close.iloc[-1]
#             latest_sma = sma.iloc[-1]
#             latest_upper = upper_band.iloc[-1]
#             latest_lower = lower_band.iloc[-1]
            
#             # Calculate position within bands (0 = lower band, 1 = upper band)
#             band_position = (latest_price - latest_lower) / (latest_upper - latest_lower)
            
#         else:
#             band_position = 0.5  # Default for volatile coins
        
#     except Exception:
#         return {"strategy": "Bollinger Squeeze", "signal": "HOLD", "confidence": 50}

#     if bb_signal == "breakout_up":
#         signal, confidence = "BUY", 70
#     elif bb_signal == "breakout_down":
#         signal, confidence = "SELL", 70
#     elif is_less_volatile and band_position > 0.8:  # Only for less volatile coins
#         signal, confidence = "SELL", 58
#     elif is_less_volatile and band_position < 0.2:  # Only for less volatile coins
#         signal, confidence = "BUY", 58
#     elif is_less_volatile and latest_price > latest_sma * 1.003:  # Only for less volatile coins
#         signal, confidence = "BUY", 55
#     elif is_less_volatile and latest_price < latest_sma * 0.997:  # Only for less volatile coins
#         signal, confidence = "SELL", 55
#     else:
#         signal, confidence = "HOLD", 50

#     return {"strategy": "Bollinger Squeeze", "signal": signal, "confidence": confidence}