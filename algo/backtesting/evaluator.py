# backtesting/evaluator.py
# Enhanced backtest evaluation report

from prettytable import PrettyTable
import pandas as pd
from ..config import HISTORICAL_LIMIT
from datetime import datetime, timedelta
import numpy as np


def evaluate_backtest_results(df):
    if "result" not in df.columns:
        print("\nNo 'result' column in backtest data. Skipping evaluation.")
        return {}

    # Calculate actual backtest period based on HISTORICAL_LIMIT and interval
    if not df.empty and "interval" in df.columns:
        interval = df.iloc[0]["interval"]

        # Convert interval to minutes
        interval_minutes = {
            "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480, "12h": 720,
            "1d": 1440, "3d": 4320, "1w": 10080
        }.get(interval, 60)  # Default to 1h if not found

        # Calculate actual days analyzed
        total_minutes = HISTORICAL_LIMIT * interval_minutes
        total_days_analyzed = round(total_minutes / (24 * 60), 1)

        end_date = datetime.now()
        start_date = end_date - timedelta(minutes=total_minutes)
        backtest_period = f"{start_date.strftime('%d-%b-%Y %H:%M')} to {end_date.strftime('%d-%b-%Y %H:%M')} UTC"
    else:
        backtest_period = "N/A"
        total_days_analyzed = 0
        end_date = datetime.now()

    # Basic calculations
    total_signals = len(df)
    success_signals = df[df['result'] == 'SUCCESS']
    failed_signals = df[df['result'] == 'FAILURE']
    neutral_signals = df[df['result'] == 'NEUTRAL']

    buy_signals = df[df['signal'] == 'BUY']
    sell_signals = df[df['signal'] == 'SELL']
    hold_signals = df[df['signal'] == 'HOLD']

    success_rate = round((len(success_signals) / total_signals) * 100, 2) if total_signals else 0

    avg_profit = round(success_signals['net_return_percent'].mean(), 2) if not success_signals.empty else 0.0

    # Cumulative return (geometric)
    if "net_return_percent" in df.columns and not df.empty:
        df_sorted = df.sort_values(by="timestamp").copy()
        df_sorted["return_multiplier"] = 1 + (df_sorted["net_return_percent"] / 100)
        cumulative_return = round((df_sorted["return_multiplier"].prod() - 1) * 100, 2)
    else:
        cumulative_return = 0.0

    total_gains = round(success_signals["net_return_percent"].sum(), 2) if not success_signals.empty else 0.0
    total_losses = round(failed_signals["net_return_percent"].sum(), 2) if not failed_signals.empty else 0.0

    # Streaks
    max_winning_streak, max_losing_streak = calculate_streaks(df)

    # Period returns (last 30/60/90 calendar days from today)
    period_returns = calculate_recent_period_returns(df)

    # Advanced metrics
    max_drawdown = calculate_max_drawdown(df)
    sharpe_ratio = calculate_sharpe_ratio(df)
    monthly_performance = calculate_recent_monthly_performance(df)
    benchmark_comparison = calculate_benchmark_comparison(df)

    # Win/loss ratio
    win_loss_ratio = round(len(success_signals) / len(failed_signals), 2) if len(failed_signals) > 0 else "∞"

    # Average holding period
    avg_duration = round(df["estimated_duration_minutes"].mean(), 1) if "estimated_duration_minutes" in df.columns and not df.empty else 0

    summary = {
        "Backtest Period": backtest_period,
        "Total Days Analyzed": f"{total_days_analyzed} days",
        "Total Signals | Success Rate": f"{total_signals} | {success_rate}%",
        "BUY | SELL Signals": f"{len(buy_signals)} | {len(sell_signals)}",
        "Success | Failed | Neutral": f"{len(success_signals)} | {len(failed_signals)} | {len(neutral_signals)}",
        "Avg Profit % | Win/Loss Ratio": f"{avg_profit}% | {win_loss_ratio}:1",
        "Total Gains | Total Losses": f"+{total_gains}% | {total_losses}%",
        "Cumulative Net Return %": f"{cumulative_return}%",
        "30d | 60d | 90d Returns": period_returns,
        "Max Winning Streak": max_winning_streak,
        "Max Losing Streak": max_losing_streak,
        "Sharpe Ratio": sharpe_ratio,
        "Avg Duration (min)": f"{avg_duration} min",
        "Risk-Adjusted Metrics": f"Volatility: {calculate_volatility(df)}%",
    }

    print("\nEnhanced Backtest Evaluation Report:\n" + "-" * 60)
    for k, v in summary.items():
        print(f"{k}: {v}")
    print("-" * 60)

    print_detailed_backtest_table(df)

    return summary


def calculate_recent_period_returns(df):
    """Calculate returns for the most recent 30, 60, and 90 calendar days from TODAY"""
    if df.empty or "timestamp" not in df.columns or "net_return_percent" not in df.columns:
        return "N/A | N/A | N/A"

    df_sorted = df.sort_values(by="timestamp").copy()
    today = datetime.now()

    cutoffs = {
        "30d": today - timedelta(days=30),
        "60d": today - timedelta(days=60),
        "90d": today - timedelta(days=90),
    }

    results = []
    for label, cutoff in cutoffs.items():
        period_df = df_sorted[df_sorted["timestamp"] >= cutoff].copy()
        if period_df.empty:
            results.append("N/A")
            continue
        period_df["return_multiplier"] = 1 + (period_df["net_return_percent"] / 100)
        geometric_return = (period_df["return_multiplier"].prod() - 1) * 100
        results.append(f"{geometric_return:.2f}%")

    return " | ".join(results)


def calculate_max_drawdown(df):
    """Calculate maximum drawdown"""
    if df.empty or "net_return_percent" not in df.columns:
        return 0.0

    df_sorted = df.sort_values(by="timestamp").copy()
    df_sorted["return_multiplier"] = 1 + (df_sorted["net_return_percent"] / 100)
    df_sorted["cumulative_return"] = df_sorted["return_multiplier"].cumprod()
    df_sorted["running_max"] = df_sorted["cumulative_return"].expanding().max()
    df_sorted["drawdown"] = (df_sorted["cumulative_return"] / df_sorted["running_max"] - 1) * 100

    max_drawdown = abs(df_sorted["drawdown"].min())
    return round(max_drawdown, 2)


def calculate_sharpe_ratio(df):
    """Calculate Sharpe ratio (risk-free rate = 0)"""
    if df.empty or "net_return_percent" not in df.columns:
        return 0.0

    returns = df["net_return_percent"]
    if len(returns) < 2:
        return 0.0

    mean_return = returns.mean()
    std_return = returns.std()

    if std_return == 0:
        return 0.0

    sharpe = round(mean_return / std_return, 3)
    return sharpe


def calculate_volatility(df):
    """Calculate return volatility"""
    if df.empty or "net_return_percent" not in df.columns:
        return 0.0

    return round(df["net_return_percent"].std(), 2)


def calculate_recent_monthly_performance(df):
    """Performance for the most recent 30 days from TODAY"""
    if df.empty or "timestamp" not in df.columns or "net_return_percent" not in df.columns:
        return "N/A"

    df_sorted = df.sort_values(by="timestamp")
    today = datetime.now()
    month_start = today - timedelta(days=30)

    df_month = df_sorted[df_sorted["timestamp"] >= month_start].copy()
    if df_month.empty:
        return "N/A"

    df_month["return_multiplier"] = 1 + (df_month["net_return_percent"] / 100)
    monthly_return = round((df_month["return_multiplier"].prod() - 1) * 100, 2)
    monthly_trades = len(df_month)
    monthly_success_rate = round((len(df_month[df_month["result"] == "SUCCESS"]) / len(df_month)) * 100, 1)

    return f"{monthly_return}% ({monthly_trades} trades, {monthly_success_rate}% SR)"


def calculate_benchmark_comparison(df):
    """Simple buy & hold comparison"""
    if df.empty or "net_return_percent" not in df.columns:
        return "N/A"

    df_sorted = df.sort_values(by="timestamp").copy()
    df_sorted["return_multiplier"] = 1 + (df_sorted["net_return_percent"] / 100)
    strategy_return = round((df_sorted["return_multiplier"].prod() - 1) * 100, 2)
    return f"Strategy: {strategy_return}% vs Buy&Hold: 0%"


def calculate_streaks(df):
    """Max winning and losing streaks"""
    if df.empty or "result" not in df.columns:
        return 0, 0

    df_sorted = df.sort_values(by="timestamp")

    max_winning = max_losing = 0
    current_winning = current_losing = 0

    for _, row in df_sorted.iterrows():
        result = row.get("result", "")
        if result == "SUCCESS":
            current_winning += 1
            current_losing = 0
            max_winning = max(max_winning, current_winning)
        elif result == "FAILURE":
            current_losing += 1
            current_winning = 0
            max_losing = max(max_losing, current_losing)
        else:
            current_winning = current_losing = 0

    return max_winning, max_losing


def print_detailed_backtest_table(df):
    df = df.sort_values(by="timestamp")
    table = PrettyTable()
    table.field_names = [
        "Time", "Coin", "Open", "Close", "Profit/Loss %", "RSI",
        "Volatility", "MACD", "Sentiment", "BB", "Signal", "Confidence", "Result",
        "Exit", "TP", "SL", "R:R", "Exit Reason", "Duration (min)"
    ]

    for _, row in df.iterrows():
        def safe_val(val):
            try:
                return round(float(val), 2)
            except:
                return "-"

        table.add_row([
            row["timestamp"].strftime('%Y-%m-%d %H:%M:%S'),
            row.get("coin", "-"),
            safe_val(row.get("open", 0.0)),
            safe_val(row.get("close", 0.0)),
            f"{safe_val(row.get('net_return_percent', 0.0))}%",
            f"{safe_val(row.get('rsi', '-'))} ({row.get('rsi_signal', '-')})",
            row.get("volatility", "-"),
            row.get("macd", "-"),
            row.get("sentiment", "-"),
            row.get("bollinger", "-"),
            row.get("signal", "-"),
            safe_val(row.get("confidence", "-")),
            row.get("result", "-"),
            safe_val(row.get("exit_price", 0.0)),
            safe_val(row.get("take_profit", 0.0)),
            safe_val(row.get("stop_loss", 0.0)),
            safe_val(row.get("risk_reward_ratio", "-")),
            row.get("exit_reason", "-"),
            row.get("estimated_duration_minutes", "-")
        ])

    print("\nDetailed Backtest Table:")
    print(table)
