#main.py

import datetime

import pandas as pd
from data.fetch_price import get_price_data
from data.fetch_sentiment import get_sentiment_score
from indicators.macd import calculate_macd
from indicators.rsi import calculate_rsi
from indicators.bollinger import calculate_bollinger_bands
from indicators.volatility import calculate_volatility
from indicators.volume import calculate_volume_metrics
from logic.signal_engine import generate_live_signal
# from logic.signal_engine import generate_backtest_signal as generate_live_signal
from logic.risk_manager import calculate_risk_management
from logic.risk_manager import calculate_atr
from logic.signal_timer import estimate_signal_duration
from backtesting.backtester import run_backtest
from backtesting.evaluator import evaluate_backtest_results
from data.fetch_news_utils import fetch_rss_headlines
from reports.visualization import plot_backtest_results, plot_price_with_indicators
from reports.generate_pdf import create_pdf_report
import os

os.makedirs("reports/plots", exist_ok=True)
os.makedirs("reports/generated_pdfs", exist_ok=True)


def get_adjacent_timeframes(interval):
    tf_map = {
        "1m": (None, "5m"),
        "5m": ("1m", "15m"),
        "15m": ("5m", "1h"),
        "30m": ("15m", "2h"),
        "1h": ("15m", "4h"),
        "2h": ("30m", "6h"),
        "4h": ("1h", "1d"),
        "1d": ("4h", "3d"),
        "1w": ("1d", "1M")
    }
    return tf_map.get(interval, (None, None))


def run_trading_pipeline():
    print("-----Welcome to TradingSignals!-----")
    symbol = input("Enter the trading pair (e.g., BTCUSDT): ").upper()
    interval = input("Enter the timeframe (e.g., 1m, 5m, 1h, 4h, 1d): ").lower()

    print(f"\nProcessing {symbol} at interval {interval}...")

    lower_tf, higher_tf = get_adjacent_timeframes(interval)
    price_data = {interval: get_price_data(symbol, interval)}

    if lower_tf:
        print(f"Fetching lower timeframe ({lower_tf})...")
        lower_df = get_price_data(symbol, lower_tf)
        price_data[lower_tf] = lower_df
    else:
        lower_df = None

    if higher_tf:
        print(f"Fetching higher timeframe ({higher_tf})...")
        higher_df = get_price_data(symbol, higher_tf)
        price_data[higher_tf] = higher_df
    else:
        higher_df = None

    print("\n📊 Preview of Multi-Timeframe Price Data:")
    for tf, df in price_data.items():
        print(f"\n--- {tf.upper()} Data (last 5 rows) ---")
        print(df.tail(5))

    price_df = price_data[interval]

    # Step 2: Sentiment
    sentiment_score, scored_headlines = get_sentiment_score(symbol, print_news=True)
    print(f"\nSentiment Score: {sentiment_score}")

    # Convert string label to numeric score (needed for signal duration logic)
    sentiment_float = 1.0 if sentiment_score == "bullish" else -1.0 if sentiment_score == "bearish" else 0.0

    # Step 3: Indicators
    macd_signal = calculate_macd(price_df)
    rsi_val, rsi_signal = calculate_rsi(price_df)
    bb_signal = calculate_bollinger_bands(price_df)
    volatility = calculate_volatility(price_df)
    volume = calculate_volume_metrics(price_df)

    print(f"\nMACD Signal: {macd_signal}")
    print(f"RSI Signal: {rsi_signal}")
    print(f"Bollinger Bands Signal: {bb_signal}")
    print(f"Volatility Level: {volatility}")
    print(f"Volume Level: {volume}")

    # Step 4: Signal
    final_signal, confidence, contributing_strategies = generate_live_signal(price_data, sentiment_score, symbol)

    local_time = datetime.datetime.now()
    utc_time = datetime.datetime.utcnow()
    print(f"\nLocal Time: {local_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"UTC Time:   {utc_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Step 5: Risk Management & Final Decision
    indicators = {
        "rsi": rsi_val,
        "macd": macd_signal,
        "bb": bb_signal,
        "volatility": volatility,
        "sentiment": sentiment_float,
        "trend_strength": 0.6
    }
    
    # Calculate risk parameters for the signal
    risk_result = calculate_risk_management(price_df, final_signal, volatility, indicators, confidence)

    # ➡️➡️➡️ CRITICAL CHANGE: Make the final decision based on the risk_level
    final_decision = "REJECTED"
    if final_signal in ["BUY", "SELL"] and risk_result['risk_level'] not in ['too_weak', 'invalid']:
        final_decision = "APPROVED"

    print(f"\n✅ FINAL SIGNAL: {final_signal} ({confidence}% confidence)")
    print(f"Trading Decision: {final_decision}\n")

    if final_decision == "APPROVED":
        print(f"Risk Management:")
        print(f"Stop Loss: {risk_result['suggested_stop_loss']}")
        print(f"Take Profit: {risk_result['suggested_take_profit']}")
        print(f"Risk:Reward Ratio: {risk_result['risk_reward_label']}")
        print(f"Risk Level: {risk_result['risk_level'].upper()}")
        print(f"Expected Profit %: {risk_result['expected_profit_percent']}%")

        # Step 6: Signal Duration (Real-Time)
        duration_minutes = estimate_signal_duration(
            signal_type=final_signal,
            confidence=confidence,
            trend="uptrend" if macd_signal == "bullish" else "downtrend" if macd_signal == "bearish" else "sideways",
            sentiment="bullish" if sentiment_float > 0.3 else "bearish" if sentiment_float < -0.3 else "neutral",
            volatility=volatility,
            timeframe=interval
        )

        start = price_df.index[-1]
        end = start + datetime.timedelta(minutes=duration_minutes)
        signal_duration = f"~{duration_minutes} minutes"

        print(f"\n📌 Intelligent Signal Duration: {signal_duration}")
        print(f"🕒 Valid From: {start} → To: {end}")

    else:
        print("❌ Signal rejected due to poor risk-to-reward ratio or other invalid conditions.")
        risk_result = {'suggested_stop_loss': None, 'suggested_take_profit': None, 'risk_reward_label': "N/A", 'risk_level': "REJECTED", 'expected_profit_percent': 0.0}
        summary = {}
        backtest_df = pd.DataFrame()


    # Step 7: Backtest Evaluation
    price_data = {interval: price_df}
    if lower_tf and lower_df is not None:
        price_data[lower_tf] = lower_df
    if higher_tf and higher_df is not None:
        price_data[higher_tf] = higher_df

    try:
        backtest_df = run_backtest(price_df, symbol, interval, scored_headlines, price_data)

        if backtest_df.empty:
            print("\n⚠️ No trades were triggered during backtest. Please review signal logic or data coverage.")
            summary = {}
        else:
            print(f"\n✅ Backtest completed with {len(backtest_df)} trades.")
            summary = evaluate_backtest_results(backtest_df)

    except Exception as e:
        print(f"\n❌ Backtest Failed: {e}")
        backtest_df = pd.DataFrame()
        summary = {}
    
    # Step 8: Visualization
    backtest_chart = "reports/plots/backtest_chart.png"
    plot_backtest_results(backtest_df, backtest_chart)
    plot_price_with_indicators(price_df, backtest_df, symbol, "reports/plots/price_chart.png")
    
    # Step 9: Generate PDF Report
    signal_info = {
        "signal": final_signal,
        "confidence": confidence,
        "sentiment": sentiment_score,
        "price_snapshot": price_df.copy(),
        "indicators": {
            "macd": macd_signal,
            "rsi": rsi_signal,
            "bb": bb_signal,
            "volatility": volatility,
            "volume":volume
        }
    }

    risk_info = {
        "stop_loss": risk_result['suggested_stop_loss'],
        "take_profit": risk_result['suggested_take_profit'],
        "rr_ratio": risk_result['risk_reward_label'],
        "risk_level": risk_result['risk_level'].upper(),
        "expected_profit_percent": risk_result['expected_profit_percent']
    }

    # Fix timing_info to use actual calculated values
    if 'duration_minutes' in locals() and 'start' in locals() and 'end' in locals():
        # Use the actual calculated duration values
        timing_info = {
            "start": start,
            "end": end,
            "duration": signal_duration  # This will be "~X minutes" format
        }
    else:
        # Fallback for rejected signals or when duration wasn't calculated
        timing_info = {
            "start": local_time,
            "end": local_time + datetime.timedelta(minutes=30),
            "duration": "No Duration Calculated"
        }

    print(f"Debug - timing_info: {timing_info}")  # Add this debug line to verify

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = f"reports/generated_pdfs/{symbol}_{interval}_{final_signal}_{timestamp}_TradingSignals.pdf"
    create_pdf_report(symbol, interval, signal_info, risk_info, timing_info, summary, pdf_path, backtest_df, scored_headlines)

    print(f"\n✅ PDF Report saved to: {pdf_path}")


if __name__ == "__main__":
    run_trading_pipeline()