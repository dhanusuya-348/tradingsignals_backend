import numpy as np
from ..indicators.support_resistance import get_support_resistance_levels

# --- Global Commission Constant ---
COMMISSION_PERCENT = 0.002 # 0.2% Binance commission

# --- Coin Volatility Classification ---
HIGHLY_VOLATILE_COINS = ['ETHUSDT', 'SOLUSDT', 'DOGEUSDT', 'SHIBUSDT', 'PEPEUSDT', 'FLOKIUSDT']
MODERATELY_VOLATILE_COINS = ['BTCUSDT', 'BNBUSDT', 'ADAUSDT', 'LINKUSDT', 'UNIUSDT', 'OPUSDT']
STABLE_COINS = ['NEARUSDT', 'ICPUSDT', 'DOTUSDT', 'AVAXUSDT', 'MATICUSDT', 'LTCUSDT', 'XRPUSDT']

# ---------------- ATR CALCULATION ---------------- #
def calculate_atr(df, period=14):
    """Calculate the Average True Range for volatility measurement."""
    df = df.copy()
    df["H-L"] = df["high"] - df["low"]
    df["H-PC"] = abs(df["high"] - df["close"].shift(1))
    df["L-PC"] = abs(df["low"] - df["close"].shift(1))
    df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
    atr = df["TR"].rolling(window=period).mean()
    return round(atr.iloc[-1], 4) if not atr.empty and not atr.isna().iloc[-1] else 0.0

# ---------------- COIN VOLATILITY CLASSIFIER ---------------- #
def classify_coin_volatility(symbol):
    """Classify coin into volatility bucket based on historical behavior."""
    symbol_upper = symbol.upper()
    
    if any(coin in symbol_upper for coin in HIGHLY_VOLATILE_COINS):
        return "high"
    elif any(coin in symbol_upper for coin in MODERATELY_VOLATILE_COINS):
        return "moderate"
    elif any(coin in symbol_upper for coin in STABLE_COINS):
        return "low"
    else:
        return "moderate"  # Default to moderate for unknown coins

# ---------------- DYNAMIC MIN R:R BY COIN TYPE & VOL ---------------- #
def min_rr_by_vol_and_coin(volatility: str, symbol: str = None) -> float:
    """
    Dynamic minimum risk:reward ratio tuned per coin type.
    Higher RR for tighter SLs to ensure profitability despite small distances.
    """
    v = (volatility or "medium").lower()
    
    # Coin-specific overrides
    if symbol:
        symbol_upper = symbol.upper()
        if 'ICPUSDT' in symbol_upper:
            return 3.2  # ICP needs strong RR
        elif 'ETHUSDT' in symbol_upper:
            return 3.5  # ETH is volatile, needs highest RR
        elif any(coin in symbol_upper for coin in HIGHLY_VOLATILE_COINS):
            return 3.4  # High vol coins
        elif any(coin in symbol_upper for coin in STABLE_COINS):
            return 3.0  # Stable coins can be slightly lower
    
    # Generic volatility-based
    if v == "low":
        return 3.2
    if v == "high":
        return 3.5
    return 3.3  # Medium default

# ---------------- IMPROVED MULTIPLIER LOGIC (TIGHT & REALISTIC) ---------------- #
def estimate_reward_multiplier(trend_strength, sentiment_score, volatility_level, confidence, atr, symbol=None):
    """
    Determines TP distance multiplier with TIGHT, ATTAINABLE targets.
    Prioritizes tighter SLs over aggressive rewards.
    """
    multiplier = 1.1  # START LOW - we build from here
    
    # Trend influence - conservative bonuses
    if trend_strength > 0.8:
        multiplier += 0.04
    elif trend_strength > 0.65:
        multiplier += 0.02
    elif trend_strength < 0.4:
        multiplier -= 0.03
    
    # Sentiment influence
    if sentiment_score > 0.6:
        multiplier += 0.03
    elif sentiment_score < -0.6:
        multiplier -= 0.02
    
    # Volatility influence
    vol = (volatility_level or "medium").lower()
    if vol == "high":
        multiplier -= 0.05  # Reduce for high vol - we'll use higher RR instead
    elif vol == "low":
        multiplier += 0.04  # Slight boost for stable coins
    
    # Confidence influence - very conservative
    if confidence >= 85:
        multiplier += 0.08
    elif confidence >= 75:
        multiplier += 0.04
    elif confidence <= 55:
        multiplier -= 0.08
    
    # ATR-based caps - STRICT
    if atr > 0:
        if atr > 0.025:  # Very volatile
            multiplier = min(multiplier, 1.6)
        elif atr > 0.015:  # Moderately volatile
            multiplier = min(multiplier, 1.75)
        elif atr > 0.01:  # Medium volatile
            multiplier = min(multiplier, 1.9)
    
    # Coin-specific caps for safety
    if symbol:
        symbol_upper = symbol.upper()
        if 'ETHUSDT' in symbol_upper:
            multiplier = min(multiplier, 1.7)  # ETH gets capped tighter
        elif any(coin in symbol_upper for coin in HIGHLY_VOLATILE_COINS):
            multiplier = min(multiplier, 1.75)
    
    # Final clip - very tight range for realistic profits
    return round(float(np.clip(multiplier, 1.0, 2.0)), 2)

# ---------------- RISK LEVEL CLASSIFICATION ---------------- #
def determine_risk_level(multiplier):
    """Classify risk level based on reward multiplier."""
    if multiplier < 1.5:
        return "low"
    elif multiplier < 1.8:
        return "moderate"
    return "high"

# ---------------- SUPPORT / RESISTANCE UTILS ---------------- #
def find_nearest_level(levels, price, direction):
    """Find the nearest support/resistance level in the given direction."""
    if direction == "below":
        levels_below = [lvl for lvl in levels if lvl < price]
        return max(levels_below) if levels_below else None
    elif direction == "above":
        levels_above = [lvl for lvl in levels if lvl > price]
        return min(levels_above) if levels_above else None
    return None

# ---------------- UPDATED SL CALCULATION (TIGHT & NOISE-RESISTANT) ---------------- #
def calculate_smart_stop_loss(df, entry_price, atr, signal, confidence, trend_strength, symbol=None):
    """
    Calculate TIGHT stop loss optimized to reduce premature exits.
    Uses smaller ATR multipliers and smarter noise buffering.
    """
    # ---- TIGHT BASE MULTIPLIERS ----
    if confidence >= 85 and trend_strength > 0.7:
        base_multiplier = 1.3  # Tight for high conviction
    elif confidence >= 75:
        base_multiplier = 1.2
    elif confidence >= 65:
        base_multiplier = 1.1
    else:
        base_multiplier = 1.0  # Very tight for low confidence

    # ---- MINIMAL NOISE BUFFER ----
    # Only account for actual candlestick body size, not aggressive ATR buffering
    avg_body_size = abs(df['close'] - df['open']).tail(10).mean()
    noise_buffer = max(atr * 0.5, avg_body_size * 0.8)

    # ---- FINAL SL DISTANCE ----
    sl_distance = max(
        atr * base_multiplier,
        noise_buffer,
        entry_price * 0.003  # Absolute minimum: 0.3%
    )

    # ---- STRICT DYNAMIC RISK CAP ----
    # For ALL confidence levels, cap is VERY tight
    if confidence >= 85 and trend_strength > 0.7:
        max_risk_distance = entry_price * 0.008  # 0.8% max for highest conviction
    elif confidence >= 75:
        max_risk_distance = entry_price * 0.006  # 0.6% for good signals
    elif confidence >= 65:
        max_risk_distance = entry_price * 0.005  # 0.5% for medium signals
    else:
        max_risk_distance = entry_price * 0.004  # 0.4% for weak signals

    # Coin-specific tighter caps
    if symbol:
        symbol_upper = symbol.upper()
        if 'ETHUSDT' in symbol_upper:
            max_risk_distance = min(max_risk_distance, entry_price * 0.007)  # Even tighter for ETH
        elif any(coin in symbol_upper for coin in HIGHLY_VOLATILE_COINS):
            max_risk_distance = min(max_risk_distance, entry_price * 0.0075)

    sl_distance = min(sl_distance, max_risk_distance)

    if signal == "BUY":
        stop_loss = entry_price - sl_distance
    else:  # SELL
        stop_loss = entry_price + sl_distance
    
    return round(stop_loss, 4), sl_distance

# ---------------- MAIN CALCULATION ---------------- #
def calculate_risk_management(df, signal, volatility_level, indicators, backtest_df=None, confidence=70, symbol=None):
    """
    Improved risk management with TIGHT SL placement and realistic TP targets.
    Designed to work across all 100 top crypto coins.
    """
    if df.empty or signal not in ["BUY", "SELL"]:
        return _empty_result("neutral")

    entry_price = df["close"].iloc[-1]
    atr = calculate_atr(df)
    if atr == 0.0 or np.isnan(atr):
        return _empty_result("invalid")

    sentiment = indicators.get("sentiment", 0.0) if indicators else 0.0
    trend_strength = indicators.get("trend_strength", 0.5) if indicators else 0.5
    volatility = indicators.get("volatility", volatility_level or "medium") if indicators else (volatility_level or "medium")

    # Classify coin volatility
    classified_vol = classify_coin_volatility(symbol) if symbol else volatility

    # Calculate smart stop loss (TIGHT)
    stop_loss, sl_distance = calculate_smart_stop_loss(
        df, entry_price, atr, signal, confidence, trend_strength, symbol
    )
    
    # Get reward multiplier (REALISTIC)
    reward_multiplier = estimate_reward_multiplier(
        trend_strength, sentiment, volatility, confidence, atr, symbol
    )
    
    # Get support/resistance levels
    sr_levels = get_support_resistance_levels(df, window=20, order=5)
    
    # ---- SMART S/R ADJUSTMENT: ALWAYS TIGHTEN, NEVER LOOSEN ----
    if signal == "BUY":
        sr_support = find_nearest_level(sr_levels['support'], entry_price, "below")
        if sr_support and sr_support > 0:
            # Place SL just below support with tight buffer
            potential_sl = sr_support - (atr * 0.2)  # Only 0.2x ATR buffer
            potential_risk = entry_price - potential_sl
            
            # Only use if it actually tightens the SL
            if potential_risk < sl_distance:
                stop_loss = round(potential_sl, 4)
                sl_distance = potential_risk
    else:  # SELL
        sr_resistance = find_nearest_level(sr_levels['resistance'], entry_price, "above")
        if sr_resistance and sr_resistance > 0:
            # Place SL just above resistance with tight buffer
            potential_sl = sr_resistance + (atr * 0.2)  # Only 0.2x ATR buffer
            potential_risk = potential_sl - entry_price
            
            # Only use if it actually tightens the SL
            if potential_risk < sl_distance:
                stop_loss = round(potential_sl, 4)
                sl_distance = potential_risk
    
    # ---- CALCULATE TAKE PROFIT (REALISTIC) ----
    min_rr = min_rr_by_vol_and_coin(volatility, symbol)
    
    # Target reward: SL distance * RR ratio + commission padding
    target_reward = (sl_distance * min_rr) + (entry_price * COMMISSION_PERCENT * 2)
    
    if signal == "BUY":
        take_profit = round(entry_price + target_reward, 4)
        
        # Check for resistance levels - adjust TP if it goes too far beyond resistance
        sr_resistance = find_nearest_level(sr_levels['resistance'], entry_price, "above")
        if sr_resistance and take_profit > sr_resistance - (atr * 0.1):
            # Pull back TP to just before resistance
            take_profit = round(sr_resistance - (atr * 0.1), 4)
            
            # Ensure TP still covers minimum profit after fees
            min_profit = entry_price + (entry_price * COMMISSION_PERCENT * 2) + (atr * 0.01)
            if take_profit < min_profit:
                take_profit = min_profit
    else:  # SELL
        take_profit = round(entry_price - target_reward, 4)
        
        # Check for support levels - adjust TP if it goes too far beyond support
        sr_support = find_nearest_level(sr_levels['support'], entry_price, "below")
        if sr_support and take_profit < sr_support + (atr * 0.1):
            # Push back TP to just after support
            take_profit = round(sr_support + (atr * 0.1), 4)
            
            # Ensure TP still covers minimum profit after fees
            min_profit = entry_price - (entry_price * COMMISSION_PERCENT * 2) - (atr * 0.01)
            if take_profit > min_profit:
                take_profit = min_profit
    
    # ---- VALIDATE AND FINALIZE ----
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    
    # Double-check: If reward doesn't meet minimum RR, adjust TP up
    if reward < (risk * min_rr) + (entry_price * COMMISSION_PERCENT * 2):
        if signal == "BUY":
            take_profit = round(entry_price + (risk * min_rr) + (entry_price * COMMISSION_PERCENT * 2), 4)
        else:
            take_profit = round(entry_price - (risk * min_rr) - (entry_price * COMMISSION_PERCENT * 2), 4)
        reward = abs(take_profit - entry_price)
    
    # Calculate metrics
    risk_reward_ratio = round(reward / risk, 2) if risk > 0 else 0.0
    risk_reward_label = f"1:{risk_reward_ratio}" if risk > 0 else "1:0"
    expected_profit_percent = round((reward / entry_price) * 100, 2)
    
    # Determine risk level
    risk_level = determine_risk_level(reward_multiplier)
    
    return {
        'risk_reward_ratio': risk_reward_ratio,
        'risk_reward_label': risk_reward_label,
        'suggested_stop_loss': round(float(stop_loss), 4),
        'suggested_take_profit': round(float(take_profit), 4),
        'risk_level': risk_level,
        'expected_profit_percent': expected_profit_percent
    }

# ---- HELPER FUNCTIONS ----
def _empty_result(status):
    """Return empty result when calculation fails."""
    return {
        'risk_reward_ratio': 0.0,
        'risk_reward_label': "1:0",
        'suggested_stop_loss': 0.0,
        'suggested_take_profit': 0.0,
        'risk_level': status,
        'expected_profit_percent': 0.0
    }

# import numpy as np
# from ..indicators.support_resistance import get_support_resistance_levels

# # --- Global Commission Constant ---
# COMMISSION_PERCENT = 0.002 # 0.2% Binance commission

# # ---------------- ATR CALCULATION ---------------- #
# def calculate_atr(df, period=14):
#     """Calculate the Average True Range for volatility measurement."""
#     df = df.copy()
#     df["H-L"] = df["high"] - df["low"]
#     df["H-PC"] = abs(df["high"] - df["close"].shift(1))
#     df["L-PC"] = abs(df["low"] - df["close"].shift(1))
#     df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
#     atr = df["TR"].rolling(window=period).mean()
#     return round(atr.iloc[-1], 4) if not atr.empty and not atr.isna().iloc[-1] else 0.0

# # ---------------- MIN R:R BY VOL (BALANCED FOR ATTAINABLE PROFIT) ---------------- #
# def min_rr_by_vol(volatility: str) -> float:
#     """
#     Dynamic minimum risk:reward based on market volatility, now more balanced for attainability.
#     Slightly re-tuned to ensure more TPs are hit within practical timeframes while covering commissions.
#     """
#     v = (volatility or "medium").lower()
#     if v == "low":
#         return 2.8 # Slightly reduced from 3.0, but still strong for calm markets for more TP hits
#     if v == "high":
#         return 2.2 # Reduced from 2.5, aiming for more achievable TP in high vol
#     return 2.5 # Reduced from 2.8 default for medium vol

# # ---------------- IMPROVED MULTIPLIER LOGIC (BALANCED FOR ATTAINABILITY) ---------------- #
# def estimate_reward_multiplier(trend_strength, sentiment_score, volatility_level, confidence, atr):
#     """
#     Determines TP distance multiplier with a more balanced stance on reward,
#     prioritizing attainable net profits over excessively extreme targets.
#     """
#     multiplier = 1.2 # **Significantly Adjusted**: Lowered baseline for even stricter TPs
    
#     # Trend influence - keeping rewards strong but not excessively so
#     if trend_strength > 0.8:
#         multiplier += 0.1 # **Adjusted**: Reduced from 0.3
#     elif trend_strength > 0.65:
#         multiplier += 0.05 # **Adjusted**: Reduced from 0.15
#     elif trend_strength < 0.4:
#         multiplier -= 0.05 # **Adjusted**: Reduced penalty
    
#     # Sentiment influence (reverted to previous bonus for realism)
#     if sentiment_score > 0.6:
#         multiplier += 0.05 # **Adjusted**: Reduced from 0.1
#     elif sentiment_score < -0.6:
#         multiplier -= 0.02 # **Adjusted**: Reduced penalty
    
#     # Volatility influence - adjust for market conditions (reverted low vol bonus for realism)
#     if (volatility_level or "medium") == "high":
#         multiplier -= 0.05 # **Adjusted**: Reduced penalty
#     elif (volatility_level or "medium") == "low":
#         multiplier += 0.05 # **Adjusted**: Reduced from 0.1
    
#     # Confidence influence - slight reduction for realism
#     if confidence >= 85:
#         multiplier += 0.1 # **Adjusted**: Reduced from 0.2
#     elif confidence >= 75:
#         multiplier += 0.01 # **Adjusted**: Reduced from 0.03
#     elif confidence <= 55:
#         multiplier -= 0.1 # **Adjusted**: Reduced penalty
    
#     # ATR-based adjustments - slightly lower caps for more attainable TPs
#     if atr > 0:
#         if atr > 0.02: # very volatile
#             multiplier = min(multiplier, 1.8) # **Adjusted**: Stricter cap
#         elif atr > 0.015: # moderately volatile
#             multiplier = min(multiplier, 2.0) # **Adjusted**: Stricter cap
#         elif atr > 0.01: # medium volatile
#             multiplier = min(multiplier, 2.2) # **Adjusted**: Stricter cap
    
#     # Tighter overall range for more consistent success and achievable targets
#     return round(float(np.clip(multiplier, 1.0, 2.5)), 2) # **Adjusted**: Strictest clip range

# # ---------------- RISK LEVEL CLASSIFICATION ---------------- #
# def determine_risk_level(multiplier):
#     if multiplier < 2.8: # Adjusted thresholds
#         return "low"
#     elif multiplier < 3.8: # Adjusted thresholds
#         return "moderate"
#     return "high"

# # ---------------- SUPPORT / RESISTANCE UTILS ---------------- #
# def find_nearest_level(levels, price, direction):
#     """Find the nearest support/resistance level in the given direction."""
#     if direction == "below":
#         levels_below = [lvl for lvl in levels if lvl < price]
#         return max(levels_below) if levels_below else None
#     elif direction == "above":
#         levels_above = [lvl for lvl in levels if lvl > price]
#         return min(levels_above) if levels_above else None
#     return None

# # ---------------- UPDATED SL CALCULATION (OPTIMIZED FOR NOISE REDUCTION & ACCURACY) ---------------- #
# def calculate_smart_stop_loss(df, entry_price, atr, signal, confidence, trend_strength):
#     """
#     Calculate a more robust stop loss with adaptive spacing, prioritizing
#     volatility and market conditions to avoid premature noise-based stops.
#     """
#     # ------------------- ATR-BASED MULTIPLIER (More Dynamic) --------------------
#     # Base multiplier is now even more generous for all confidence levels.
#     if confidence >= 85 and trend_strength > 0.7:
#         base_multiplier = 4.0 # Increased from 3.5
#     elif confidence >= 75:
#         base_multiplier = 3.5 # Increased from 3.0
#     elif confidence >= 65:
#         base_multiplier = 3.0 # Increased from 2.5
#     else:
#         base_multiplier = 2.5 # Increased from 2.0

#     # ------------------- NOISE & VOLATILITY BUFFER --------------------
#     # Calculate an adaptive noise buffer to counter market whipsaws with higher multipliers.
#     avg_body_size = abs(df['close'] - df['open']).tail(10).mean() # Shorter lookback for responsiveness
#     noise_buffer = max(atr * 2.0, avg_body_size * 3.0) # Increased multipliers for even greater noise resilience

#     # ------------------- FINAL SL DISTANCE CALCULATION --------------------
#     # The stop-loss is the larger of the ATR-based distance or the noise buffer.
#     sl_distance = max(
#         atr * base_multiplier,
#         noise_buffer,
#         entry_price * 0.005 # Maintain a minimum distance of 0.5%
#     )

#     # ------------------- DYNAMIC RISK CAP (Crucial Change for More Room) --------------------
#     # The dynamic cap is now even more lenient, allowing for more room on high-conviction trades.
#     if confidence >= 80 and trend_strength > 0.6:
#         max_risk_distance = entry_price * 0.02 # Up to 2.0% for high-conviction trades
#     else:
#         max_risk_distance = entry_price * 0.015 # Up to 1.5% for all others

#     sl_distance = min(sl_distance, max_risk_distance)

#     if signal == "BUY":
#         stop_loss = entry_price - sl_distance
#     else: # SELL
#         stop_loss = entry_price + sl_distance
    
#     return round(stop_loss, 4), sl_distance

# # ---------------- MAIN CALCULATION ---------------- #
# def calculate_risk_management(df, signal, volatility_level, indicators, backtest_df=None, confidence=70):
#     """
#     Improved risk management with optimized SL placement to drastically reduce premature stops
#     and more attainable, commission-aware TPs to increase TP hit rate, ensuring higher net profit and accuracy.
#     """
#     if df.empty or signal not in ["BUY", "SELL"]:
#         return _empty_result("neutral")

#     entry_price = df["close"].iloc[-1]
#     atr = calculate_atr(df)
#     if atr == 0.0 or np.isnan(atr):
#         return _empty_result("invalid")

#     sentiment = indicators.get("sentiment", 0.0) if indicators else 0.0
#     trend_strength = indicators.get("trend_strength", 0.5) if indicators else 0.5
#     volatility = indicators.get("volatility", volatility_level or "medium") if indicators else (volatility_level or "medium")

#     # Calculate smart stop loss
#     stop_loss, sl_distance = calculate_smart_stop_loss(
#         df, entry_price, atr, signal, confidence, trend_strength
#     )
    
#     # Get reward multiplier
#     reward_multiplier = estimate_reward_multiplier(
#         trend_strength, sentiment, volatility, confidence, atr
#     )
    
#     # Get support/resistance levels
#     sr_levels = get_support_resistance_levels(df, window=20, order=5)
    
#     # Adjust SL based on S/R levels - give it more room
#     if signal == "BUY":
#         sr_support = find_nearest_level(sr_levels['support'], entry_price, "below")
#         if sr_support and sr_support > stop_loss: # Only adjust if S/R is below current SL
#             potential_sl = sr_support - (atr * 0.7) # Increased buffer below support for more room
#             potential_risk = entry_price - potential_sl
            
#             # REMOVED THE STRICT RISK CAP, allowing S/R adjustment to be more effective
#             stop_loss = round(potential_sl, 4)
#             sl_distance = potential_risk
#     else: # SELL
#         sr_resistance = find_nearest_level(sr_levels['resistance'], entry_price, "above")
#         if sr_resistance and sr_resistance < stop_loss: # Only adjust if S/R is above current SL
#             potential_sl = sr_resistance + (atr * 0.7) # Increased buffer above resistance for more room
#             potential_risk = potential_sl - entry_price
            
#             # REMOVED THE STRICT RISK CAP, allowing S/R adjustment to be more effective
#             stop_loss = round(potential_sl, 4)
#             sl_distance = potential_risk
    
#     # Calculate take profit, factoring in commission
#     min_rr = min_rr_by_vol(volatility)
    
#     # Calculate target reward including commission to ensure net profit
#     # This ensures the raw profit is large enough to cover the commission plus the desired RR
#     target_reward = (sl_distance * max(min_rr, reward_multiplier)) + (entry_price * COMMISSION_PERCENT)
    
#     if signal == "BUY":
#         take_profit = round(entry_price + target_reward, 4)
#         # Check for resistance levels near TP - adjust with more buffer and dynamic approach
#         sr_resistance = find_nearest_level(sr_levels['resistance'], entry_price, "above")
#         # If TP goes past resistance, pull it back to just before resistance with a good buffer
#         if sr_resistance and take_profit > sr_resistance - (atr * 0.05): # Less extreme buffer than 0.0001 (reverted from 0.001)
#             take_profit = round(sr_resistance - (atr * 0.05), 4)
#             # Ensure TP is still above entry after S/R adjustment and covers commission adequately
#             if take_profit <= entry_price + (entry_price * COMMISSION_PERCENT * 1.5): # Ensure minimum net profit after fees
#                 take_profit = entry_price + (entry_price * COMMISSION_PERCENT * 1.5) + (atr * 0.02) # Add small buffer
#     else:
#         take_profit = round(entry_price - target_reward, 4)
#         # Check for support levels near TP - adjust with more buffer and dynamic approach
#         sr_support = find_nearest_level(sr_levels['support'], entry_price, "below")
#         # If TP goes past support, push it back to just after support with a good buffer
#         if sr_support and take_profit < sr_support + (atr * 0.05): # Less extreme buffer than 0.0001 (reverted from 0.001)
#             take_profit = round(sr_support + (atr * 0.05), 4)
#             # Ensure TP is still below entry after S/R adjustment and covers commission adequately
#             if take_profit >= entry_price - (entry_price * COMMISSION_PERCENT * 1.5): # Ensure minimum net profit after fees
#                 take_profit = entry_price - (entry_price * COMMISSION_PERCENT * 1.5) - (atr * 0.02) # Add small buffer
    
#     # Final calculations
#     risk = abs(entry_price - stop_loss)
#     reward = abs(take_profit - entry_price)
    
#     # Ensure minimum RR (after potential S/R adjustments) is maintained, *plus* commission
#     min_rr_check = min_rr_by_vol(volatility)
#     # If reward is less than target, adjust TP to ensure it meets the minimum RR and covers commission
#     if reward < (risk * min_rr_check) + (entry_price * COMMISSION_PERCENT * 1.5): # Ensure more robust profit after commission
#         if signal == "BUY":
#             take_profit = round(entry_price + (risk * min_rr_check) + (entry_price * COMMISSION_PERCENT * 1.5), 4)
#         else:
#             take_profit = round(entry_price - ((risk * min_rr_check) + (entry_price * COMMISSION_PERCENT * 1.5)), 4)
#         reward = abs(take_profit - entry_price) # Recalculate reward based on new TP
    
#     risk_reward_ratio = round(reward / risk, 2) if risk > 0 else 0.0
#     risk_reward_label = f"1:{risk_reward_ratio}" if risk > 0 else "1:0"
#     expected_profit_percent = round((reward / entry_price) * 100, 2)
    
#     # Determine risk level
#     risk_level = determine_risk_level(reward_multiplier)
    
#     return {
#         'risk_reward_ratio': risk_reward_ratio,
#         'risk_reward_label': risk_reward_label,
#         'suggested_stop_loss': round(float(stop_loss), 4),
#         'suggested_take_profit': round(float(take_profit), 4),
#         'risk_level': risk_level,
#         'expected_profit_percent': expected_profit_percent
#     }

# # ---------------- HELPER FUNCTIONS ---------------- #
# def _empty_result(status):
#     return {
#         'risk_reward_ratio': 0.0,
#         'risk_reward_label': "1:0",
#         'suggested_stop_loss': 0.0,
#         'suggested_take_profit': 0.0,
#         'risk_level': status,
#         'expected_profit_percent': 0.0
#     }