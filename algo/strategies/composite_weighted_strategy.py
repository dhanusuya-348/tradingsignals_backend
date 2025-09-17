# strategies/composite_weighted_strategy.py
from indicators.macd import calculate_macd
from indicators.rsi import calculate_rsi
from indicators.bollinger import calculate_bollinger_bands
from indicators.volatility import calculate_volatility
from indicators.volume import calculate_volume_metrics
from indicators.trend import identify_trend

def composite_weighted_signal(df, sentiment, symbol=""):
    score = 0

    # Coin-specific sensitivity detection with ICP special handling
    less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT', 'BNBUSDT']
    is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)
    
    # Special handling for ICP - it's less volatile but has unique characteristics
    is_icp = 'ICPUSDT' in symbol.upper()

    # Get trend context for better RSI interpretation
    try:
        trend = identify_trend(df)
    except:
        trend = "sideways"

    macd = calculate_macd(df, symbol)  # Pass symbol for coin-specific thresholds
    if macd == "bullish":
        score += 3
    elif macd == "bearish":
        score -= 3

    rsi_val, rsi_state = calculate_rsi(df, symbol)  # Pass symbol for coin-specific thresholds

    # Enhanced RSI scoring with trend context
    if rsi_state == "oversold":
        # In uptrend, oversold is more reliable for buying
        if trend == "uptrend":
            score += 3
            if rsi_val < (25 if not is_less_volatile else 35 if not is_icp else 30):
                score += 1
        elif trend == "downtrend":
            # In downtrend, be more cautious with oversold signals
            score += 1
        else:  # sideways
            score += 2
            if rsi_val < (25 if not is_less_volatile else 35 if not is_icp else 30):
                score += 1
    elif rsi_state == "overbought":
        # In downtrend, overbought is more reliable for selling
        if trend == "downtrend":
            score -= 3
            if rsi_val > (75 if not is_less_volatile else 65 if not is_icp else 70):
                score -= 1
        elif trend == "uptrend":
            # In uptrend, be more cautious with overbought signals
            score -= 1
        else:  # sideways
            score -= 2
            if rsi_val > (75 if not is_less_volatile else 65 if not is_icp else 70):
                score -= 1
    elif rsi_state == "neutral":
        # Enhanced neutral zone logic for less volatile coins
        if is_less_volatile:
            if 40 <= rsi_val <= 45 and trend == "uptrend":
                score += 1
            elif 55 <= rsi_val <= 60 and trend == "downtrend":
                score -= 1
            elif 45 <= rsi_val <= 55:
                score += 1 if macd == "bullish" else -1 if macd == "bearish" else 0
        else:
            if 45 <= rsi_val <= 55:
                score += 1 if macd == "bullish" else -1

    if sentiment == "bullish":
        score += 2
    elif sentiment == "bearish":
        score -= 2

    bb = calculate_bollinger_bands(df)
    if bb == "breakout_up":
        score += 3
        if macd == "bullish":
            score += 1
    elif bb == "breakout_down":
        score -= 3
        if macd == "bearish":
            score -= 1
    elif bb == "within_range":
        score += 1 if rsi_state == "oversold" else -1 if rsi_state == "overbought" else 0

    volatility = calculate_volatility(df)
    if volatility == "low" and abs(score) >= 3:
        score += 1
    elif volatility == "high" and abs(score) < 3:
        score = int(score * 0.8)  # Less aggressive reduction

    # Integrate volume analysis with reduced impact for less volatile coins
    volume_metrics = calculate_volume_metrics(df)
    volume_signal = volume_metrics["volume_signal"]
    obv_signal = volume_metrics["obv_signal"]
    
    # Volume confirmation logic - adjusted multipliers
    if is_icp:
        volume_multiplier = 1.1  # Slightly reduced for ICP
    elif is_less_volatile:
        volume_multiplier = 0.9  # Increased for other less volatile coins
    else:
        volume_multiplier = 0.7  # Keep for volatile coins
    
    if volume_signal == "high_volume":
        # High volume confirms signals
        if abs(score) >= 3:
            score += int(2 * volume_multiplier) if score > 0 else -int(2 * volume_multiplier)
        elif abs(score) >= 1:
            score += int(1 * volume_multiplier) if score > 0 else -int(1 * volume_multiplier)
    elif volume_signal == "low_volume":
        # Low volume weakens signals - less aggressive reduction
        if is_icp:
            reduction_factor = 0.75
            strong_reduction_factor = 0.9
        elif is_less_volatile:
            reduction_factor = 0.7
            strong_reduction_factor = 0.85
        else:
            reduction_factor = 0.5
            strong_reduction_factor = 0.6
        
        if abs(score) < 3:
            score = int(score * reduction_factor)
        else:
            score = int(score * strong_reduction_factor)
    
    # OBV signal integration - adjusted multipliers
    if is_icp:
        obv_multiplier = 1.2
    elif is_less_volatile:
        obv_multiplier = 1.0  # Increased from 0.7
    else:
        obv_multiplier = 0.7
        
    if obv_signal == "bullish":
        score += int(2 * obv_multiplier)
    elif obv_signal == "bearish":
        score -= int(2 * obv_multiplier)
    
    # Volume-price divergence boost
    if volume_signal == "high_volume" and obv_signal == "bullish" and score > 0:
        score += int(1 * volume_multiplier)
    elif volume_signal == "high_volume" and obv_signal == "bearish" and score < 0:
        score -= int(1 * volume_multiplier)

    # Coin-specific confidence mapping with adjusted thresholds
    if is_icp:
        # ICP-specific mapping - slightly reduced thresholds
        if score >= 8:
            return "BUY", min(95, 85 + score * 2)
        elif score <= -8:
            return "SELL", min(95, 85 + abs(score) * 2)
        elif score >= 6:
            return "BUY", min(90, 80 + score * 2)
        elif score <= -6:
            return "SELL", min(90, 80 + abs(score) * 2)
        elif score >= 4:
            return "BUY", min(85, 75 + score * 2)
        elif score <= -4:
            return "SELL", min(85, 75 + abs(score) * 2)
        elif score >= 3:
            return "BUY", min(75, 70 + score * 2)
        elif score <= -3:
            return "SELL", min(75, 70 + abs(score) * 2)
        else:
            return "HOLD", 50
    elif is_less_volatile:
        # Reduced thresholds for other less volatile coins to catch more opportunities
        if score >= 7:
            return "BUY", min(95, 80 + score * 2)
        elif score <= -7:
            return "SELL", min(95, 80 + abs(score) * 2)
        elif score >= 5:
            return "BUY", min(90, 75 + score * 2)
        elif score <= -5:
            return "SELL", min(90, 75 + abs(score) * 2)
        elif score >= 3:
            return "BUY", min(85, 68 + score * 2)
        elif score <= -3:
            return "SELL", min(85, 68 + abs(score) * 2)
        elif score >= 2:
            return "BUY", min(75, 65 + score * 2)
        elif score <= -2:
            return "SELL", min(75, 65 + abs(score) * 2)
        elif score >= 1:
            return "BUY", min(70, 62 + score * 2)
        elif score <= -1:
            return "SELL", min(70, 62 + abs(score) * 2)
        else:
            return "HOLD", 50 + score * 2
    else:
        # Conservative mapping for volatile coins (higher thresholds)
        if score >= 10:
            return "BUY", min(95, 85 + score * 2)
        elif score <= -10:
            return "SELL", min(95, 85 + abs(score) * 2)
        elif score >= 8:
            return "BUY", min(90, 80 + score * 2)
        elif score <= -8:
            return "SELL", min(90, 80 + abs(score) * 2)
        elif score >= 6:
            return "BUY", min(85, 75 + score * 2)
        elif score <= -6:
            return "SELL", min(85, 75 + abs(score) * 2)
        elif score >= 4:
            return "BUY", min(75, 70 + score * 2)
        elif score <= -4:
            return "SELL", min(75, 70 + abs(score) * 2)
        else:
            return "HOLD", 50


# # strategies/composite_weighted_strategy.py
# from indicators.macd import calculate_macd
# from indicators.rsi import calculate_rsi
# from indicators.bollinger import calculate_bollinger_bands
# from indicators.volatility import calculate_volatility
# from indicators.volume import calculate_volume_metrics

# def composite_weighted_signal(df, sentiment, symbol=""):
#     score = 0

#     # Coin-specific sensitivity detection with ICP special handling
#     less_volatile_coins = ['NEARUSDT', 'ADAUSDT', 'LINKUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT']
#     is_less_volatile = any(coin in symbol.upper() for coin in less_volatile_coins)
    
#     # Special handling for ICP - it's less volatile but has unique characteristics
#     is_icp = 'ICPUSDT' in symbol.upper()

#     macd = calculate_macd(df, symbol)  # Pass symbol for coin-specific thresholds
#     if macd == "bullish":
#         score += 3
#     elif macd == "bearish":
#         score -= 3

#     rsi_val, rsi_state = calculate_rsi(df, symbol)  # Pass symbol for coin-specific thresholds

#     if rsi_state == "oversold":
#         score += 2
#         if rsi_val < 25:
#             score += 1
#     elif rsi_state == "overbought":
#         score -= 2
#         if rsi_val > 75:
#             score -= 1
#     elif rsi_state == "neutral":
#         if 45 <= rsi_val <= 55:
#             score += 1 if macd == "bullish" else -1

#     if sentiment == "bullish":
#         score += 2
#     elif sentiment == "bearish":
#         score -= 2

#     bb = calculate_bollinger_bands(df)
#     if bb == "breakout_up":
#         score += 3
#         if macd == "bullish":
#             score += 1
#     elif bb == "breakout_down":
#         score -= 3
#         if macd == "bearish":
#             score -= 1
#     elif bb == "within_range":
#         score += 1 if rsi_state == "oversold" else -1 if rsi_state == "overbought" else 0

#     volatility = calculate_volatility(df)
#     if volatility == "low" and abs(score) >= 3:
#         score += 1
#     elif volatility == "high" and abs(score) < 3:
#         score = int(score * 0.7)

#     # Integrate volume analysis
#     volume_metrics = calculate_volume_metrics(df)
#     volume_signal = volume_metrics["volume_signal"]
#     obv_signal = volume_metrics["obv_signal"]
    
#     # Volume confirmation logic - ICP-specific adjustments
#     if is_icp:
#         volume_multiplier = 1.2  # ICP responds better to volume signals
#     else:
#         volume_multiplier = 0.7 if not is_less_volatile else 1.0  # Reduce volume impact for other volatile coins
    
#     if volume_signal == "high_volume":
#         # High volume confirms signals
#         if abs(score) >= 3:
#             score += int(2 * volume_multiplier) if score > 0 else -int(2 * volume_multiplier)
#         elif abs(score) >= 1:
#             score += int(1 * volume_multiplier) if score > 0 else -int(1 * volume_multiplier)
#     elif volume_signal == "low_volume":
#         # Low volume weakens signals - ICP-specific adjustment
#         if is_icp:
#             reduction_factor = 0.7  # Less aggressive reduction for ICP
#             strong_reduction_factor = 0.85  # Less aggressive for strong signals
#         else:
#             reduction_factor = 0.5 if not is_less_volatile else 0.6
#             strong_reduction_factor = 0.6 if not is_less_volatile else 0.8
        
#         if abs(score) < 3:
#             score = int(score * reduction_factor)
#         else:
#             score = int(score * strong_reduction_factor)
    
#     # OBV signal integration - ICP-specific multiplier
#     if is_icp:
#         obv_multiplier = 1.3  # ICP responds well to OBV signals
#     else:
#         obv_multiplier = 0.7 if not is_less_volatile else 1.0
        
#     if obv_signal == "bullish":
#         score += int(2 * obv_multiplier)
#     elif obv_signal == "bearish":
#         score -= int(2 * obv_multiplier)
    
#     # Volume-price divergence boost
#     if volume_signal == "high_volume" and obv_signal == "bullish" and score > 0:
#         score += int(1 * volume_multiplier)
#     elif volume_signal == "high_volume" and obv_signal == "bearish" and score < 0:
#         score -= int(1 * volume_multiplier)

#     # Coin-specific confidence mapping with ICP special handling
#     if is_icp:
#         # ICP-specific mapping - requires stronger signals
#         if score >= 9:
#             return "BUY", min(95, 85 + score * 2)
#         elif score <= -9:
#             return "SELL", min(95, 85 + abs(score) * 2)
#         elif score >= 7:
#             return "BUY", min(90, 80 + score * 2)
#         elif score <= -7:
#             return "SELL", min(90, 80 + abs(score) * 2)
#         elif score >= 5:
#             return "BUY", min(85, 75 + score * 2)
#         elif score <= -5:
#             return "SELL", min(85, 75 + abs(score) * 2)
#         elif score >= 3:
#             return "BUY", min(75, 70 + score * 2)
#         elif score <= -3:
#             return "SELL", min(75, 70 + abs(score) * 2)
#         else:
#             return "HOLD", 50
#     elif is_less_volatile:
#         # More granular mapping for other less volatile coins (current logic)
#         if score >= 8:
#             return "BUY", min(95, 80 + score * 2)
#         elif score <= -8:
#             return "SELL", min(95, 80 + abs(score) * 2)
#         elif score >= 6:
#             return "BUY", min(90, 75 + score * 2)
#         elif score <= -6:
#             return "SELL", min(90, 75 + abs(score) * 2)
#         elif score >= 4:
#             return "BUY", min(85, 68 + score * 2)
#         elif score <= -4:
#             return "SELL", min(85, 68 + abs(score) * 2)
#         elif score >= 2:
#             return "BUY", min(75, 65 + score * 2)
#         elif score <= -2:
#             return "SELL", min(75, 65 + abs(score) * 2)
#         elif score >= 1:
#             return "BUY", min(70, 62 + score * 2)
#         elif score <= -1:
#             return "SELL", min(70, 62 + abs(score) * 2)
#         else:
#             return "HOLD", 50 + score * 2
#     else:
#         # Conservative mapping for volatile coins (higher thresholds)
#         if score >= 10:
#             return "BUY", min(95, 85 + score * 2)
#         elif score <= -10:
#             return "SELL", min(95, 85 + abs(score) * 2)
#         elif score >= 8:
#             return "BUY", min(90, 80 + score * 2)
#         elif score <= -8:
#             return "SELL", min(90, 80 + abs(score) * 2)
#         elif score >= 6:
#             return "BUY", min(85, 75 + score * 2)
#         elif score <= -6:
#             return "SELL", min(85, 75 + abs(score) * 2)
#         elif score >= 4:
#             return "BUY", min(75, 70 + score * 2)
#         elif score <= -4:
#             return "SELL", min(75, 70 + abs(score) * 2)
#         else:
#             return "HOLD", 50