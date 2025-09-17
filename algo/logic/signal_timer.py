# signal_timer.py

def estimate_signal_duration(signal_type, confidence, trend, sentiment, volatility, timeframe):
    """
    Estimate signal duration intelligently based on real-time contextual inputs.
    Optimized to provide a balanced duration: long enough for TP/SL hits,
    but not so long as to accumulate excessive losses. This aims for higher
    accuracy and profitability with definitive trade outcomes.

    Returns duration in minutes.
    """
    # Re-adjusted base durations to be more moderate, finding a sweet spot
    # These are now significantly higher than the last attempt, but not as extreme as the initial long ones.
    base_duration = {
        '1m': 45,  # Increased from 30 (more room than last, less than previous aggressive)
        '5m': 90,  # Increased from 60
        '15m': 150, # Increased from 90
        '1h': 240, # Increased from 120 (4 hours, more realistic for an hourly signal)
        '4h': 480, # Increased from 240 (8 hours)
        '1d': 960  # Increased from 480 (16 hours)
    }.get(timeframe, 150) # Fallback adjusted to 150 mins

    multiplier = 1.0

    # Trend strength impact - slightly increased bonus to allow more room for strong trend trades
    if trend == "uptrend" or trend == "downtrend":
        multiplier += 0.2  # Increased from 0.1
    elif trend == "sideways":
        multiplier -= 0.1  # Consistent penalty for sideways markets

    # Sentiment impact - slightly increased influence for aligned sentiment
    if sentiment == "bullish" and signal_type == "BUY":
        multiplier += 0.1  # Increased from 0.05
    elif sentiment == "bearish" and signal_type == "SELL":
        multiplier += 0.1  # Increased from 0.05
    elif sentiment == "bullish" and signal_type == "SELL":
        multiplier -= 0.05
    elif sentiment == "bearish" and signal_type == "BUY":
        multiplier -= 0.05

    # Volatility impact - more balanced adjustment
    if volatility == "low":
        multiplier += 0.1  # Increased from 0.05, low vol trades need more time
    elif volatility == "high":
        multiplier -= 0.05 # Reverted to slight penalty for high vol, as too much time can lead to reversals

    # Confidence adjustment (rewarding stronger signals with more appropriate room)
    if confidence >= 80:
        multiplier += 0.25 # Increased from 0.15
    elif confidence <= 55:
        multiplier -= 0.1 # Consistent penalty for low confidence

    # Clamping multiplier: Loosened range slightly to allow more nuanced duration calculation
    multiplier = max(0.9, min(multiplier, 1.5)) # Adjusted range from (0.8, 1.2)

    final_duration = int(base_duration * multiplier)
    
    # Ensure a reasonable minimum duration to avoid premature stops
    min_final_duration = 60 # Adjusted from 30 (default)
    if timeframe == '1m':
        min_final_duration = 25 # For 1m, 25 min minimum (adjusted from 15)
    
    return max(final_duration, min_final_duration)
