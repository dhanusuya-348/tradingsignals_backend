# backtesting/backtester.py

import pandas as pd
from datetime import timedelta
from ..indicators.rsi import calculate_rsi
from ..indicators.macd import calculate_macd
from ..indicators.bollinger import calculate_bollinger_bands
from ..indicators.volatility import calculate_volatility
from ..logic.risk_manager import calculate_risk_management
from ..logic.signal_timer import estimate_signal_duration
from ..logic.signal_engine import generate_live_signal as generate_backtest_signal
from ..data.fetch_price import fetch_binance_1m_data

# Load historical sentiment data
url = "https://intern-tradingsignals.onrender.com/sentiment/csv"
sentiment_df = pd.read_csv(url, names=["timestamp", "symbol", "sentiment"], header=None)
sentiment_df["timestamp"] = pd.to_datetime(sentiment_df["timestamp"])

# Binance commission rate (0.1% per side)
BINANCE_COMMISSION_RATE = 0.001

def sentiment_label_to_score(label):
    mapping = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}
    return mapping.get(label.lower().strip(), 0.0)

def get_historical_sentiment(symbol, ts):
    ts_rounded = ts.replace(minute=(ts.minute // 30) * 30, second=0, microsecond=0)
    filtered = sentiment_df[
        (sentiment_df["symbol"] == symbol) &
        (sentiment_df["timestamp"] <= ts_rounded)
    ]
    if not filtered.empty:
        label = filtered.sort_values("timestamp").iloc[-1]["sentiment"]
        return sentiment_label_to_score(label)
    return 0.0

def calculate_trade_result(signal, entry_price, exit_price, exit_reason):
    """
    Calculate trade result with Binance 0.1% commission on both entry and exit.
    """
    fee_rate = BINANCE_COMMISSION_RATE

    if signal == "BUY":
        entry_cost = entry_price * (1 + fee_rate)
        exit_revenue = exit_price * (1 - fee_rate)
        pnl = exit_revenue - entry_cost
        return_percent = (pnl / abs(entry_cost)) * 100
    else:  # SELL
        sell_revenue = entry_price * (1 - fee_rate)
        buy_cost = exit_price * (1 + fee_rate)
        pnl = sell_revenue - buy_cost
        return_percent = (pnl / abs(sell_revenue)) * 100

    # Determine success/failure based on exit reason and raw price move
    if exit_reason == "TP":
        result = "SUCCESS"
    elif exit_reason == "SL":
        result = "FAILURE"
    else:  # TIME exit
        if signal == "BUY":
            result = "SUCCESS" if exit_price > entry_price else "FAILURE"
        else:
            result = "SUCCESS" if exit_price < entry_price else "FAILURE"

    return return_percent, result, pnl

def run_backtest(price_df, symbol, interval, headlines, price_data_dict):
    backtest_results = []
    next_trade_possible_at = price_df.index[0]

    for i in range(20, len(price_df) - 6):  # leave room for next candle
        current_time = pd.to_datetime(price_df.index[i])
        if current_time < next_trade_possible_at:
            continue

        subset = price_df.iloc[:i + 1]
        current = price_df.iloc[i]
        sentiment_score = get_historical_sentiment(symbol, current_time)

        # TF-specific data for signal generation
        current_tf_data = {
            tf: df[df.index <= current_time].copy()
            for tf, df in price_data_dict.items()
        }

        signal, confidence, contributing_strategies = generate_backtest_signal(current_tf_data, sentiment_score, symbol)

        if signal == "HOLD":
            continue

        # Entry (next candle open)
        entry_candle_index = i + 1
        entry_time = pd.to_datetime(price_df.index[entry_candle_index])
        entry_price = price_df.iloc[entry_candle_index]["open"]

        # Indicators from candle N
        rsi_val, rsi_signal = calculate_rsi(subset)
        macd_signal = calculate_macd(subset)
        bb_signal = calculate_bollinger_bands(subset)
        volatility = calculate_volatility(subset)

        indicators = {
            "rsi": float(rsi_val),
            "macd": macd_signal,
            "bb": bb_signal,
            "volatility": volatility,
            "sentiment": sentiment_score,
            "trend_strength": 0.6
        }

        risk_info = calculate_risk_management(
            subset, signal, volatility, indicators,
            pd.DataFrame(backtest_results), confidence
        )
        
        # ➡️➡️➡️ CRITICAL CHANGE: Filter trades with a poor R:R ratio.
        if risk_info['risk_level'] in ['too_weak', 'invalid']:
            continue # Skips this trade and moves to the next candle.

        stop_loss = risk_info["suggested_stop_loss"]
        take_profit = risk_info["suggested_take_profit"]

        # Adjust invalid SL/TP
        if signal == "BUY":
            if take_profit <= entry_price or stop_loss >= entry_price:
                atr = abs(entry_price * 0.02)
                take_profit = entry_price + atr * 2.5
                stop_loss = entry_price - atr * 1.5
        elif signal == "SELL":
            if take_profit >= entry_price or stop_loss <= entry_price:
                atr = abs(entry_price * 0.02)
                take_profit = entry_price - atr * 2.5
                stop_loss = entry_price + atr * 1.5

        estimated_duration_minutes = estimate_signal_duration(
            signal_type=signal,
            confidence=confidence,
            trend="uptrend" if macd_signal == "bullish" else "downtrend" if macd_signal == "bearish" else "sideways",
            sentiment="bullish" if sentiment_score > 0.3 else "bearish" if sentiment_score < -0.3 else "neutral",
            volatility=volatility,
            timeframe=interval
        )

        # Get 1-min candles for trade duration
        end_time = entry_time + timedelta(minutes=estimated_duration_minutes)
        minute_data = fetch_binance_1m_data(symbol, entry_time, end_time)

        exit_price = None
        exit_time = None
        exit_reason = "TIME"
        actual_duration_minutes = estimated_duration_minutes

        for t, row in minute_data.iterrows():
            high = row["high"]
            low = row["low"]
            actual_duration_minutes = int((t - entry_time).total_seconds() / 60)

            if signal == "BUY":
                if low <= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "SL"
                    exit_time = t
                    break
                elif high >= take_profit:
                    exit_price = take_profit
                    exit_reason = "TP"
                    exit_time = t
                    break
            elif signal == "SELL":
                if high >= stop_loss:
                    exit_price = stop_loss
                    exit_reason = "SL"
                    exit_time = t
                    break
                elif low <= take_profit:
                    exit_price = take_profit
                    exit_reason = "TP"
                    exit_time = t
                    break

        if exit_price is None:
            last_row = minute_data.iloc[-1]
            exit_price = last_row["close"]
            exit_time = minute_data.index[-1]
            actual_duration_minutes = int((exit_time - entry_time).total_seconds() / 60)
            exit_reason = "TIME"

        # Calculate trade result using fee-adjusted logic
        net_return_percent, result, net_profit = calculate_trade_result(
            signal, entry_price, exit_price, exit_reason
        )

        backtest_results.append({
            "timestamp": entry_time,
            "coin": symbol,
            "interval": interval,
            "open": entry_price,
            "exit_price": exit_price,
            "exit_time": exit_time,
            "actual_duration_minutes": actual_duration_minutes,
            "rsi": round(rsi_val, 2),
            "rsi_signal": rsi_signal,
            "macd": macd_signal,
            "bollinger": bb_signal,
            "sentiment": sentiment_score,
            "volatility": volatility,
            "signal": signal,
            "confidence": confidence,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "estimated_duration_minutes": estimated_duration_minutes,
            "risk_reward_ratio": risk_info["risk_reward_label"],
            "expected_profit_percent": risk_info["expected_profit_percent"],
            "risk_level": risk_info["risk_level"],
            "exit_reason": exit_reason,
            "net_return_percent": round(net_return_percent, 2),
            "net_profit": round(net_profit, 6),
            "result": result
        })

        next_trade_possible_at = exit_time + timedelta(minutes=1)

    df = pd.DataFrame(backtest_results)
    if not df.empty and "timestamp" in df.columns:
        df["Time"] = pd.to_datetime(df["timestamp"])
    else:
        print("Warning: No valid backtest results generated.")
    return df