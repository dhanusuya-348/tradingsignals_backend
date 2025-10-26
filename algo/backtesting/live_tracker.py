# algo/backtesting/live_tracker.py
import time
from datetime import datetime
from ..data.fetch_price import fetch_binance_1m_data
from ..backtesting.backtester import calculate_trade_result
from models import get_session_context, SignalPerformance

def monitor_live_signal(symbol, signal_info, perf_id, update_callback=None):
    """
    Monitors a single signal in real-time and updates the corresponding SignalPerformance row.
    """
    symbol = symbol.upper()
    if symbol.endswith("USDT"):
        symbol = symbol[:-4]

    signal = signal_info.get("signal", "HOLD")
    entry_price = signal_info.get("price") or signal_info.get("price_snapshot", {}).get("close")
    risk_info = signal_info.get("risk", {})
    stop_loss = risk_info.get("suggested_stop_loss", 0.0)
    take_profit = risk_info.get("suggested_take_profit", 0.0)
    confidence = signal_info.get("confidence", 0)

    timing_info = signal_info.get("timing", {})
    valid_from_str = timing_info.get("start")
    valid_to_str = timing_info.get("end")
    if not valid_from_str or not valid_to_str:
        print(f"[WARN] Missing timing info for {symbol}, skipping")
        return None

    valid_from = datetime.strptime(valid_from_str, "%Y-%m-%d %H:%M:%S")
    valid_to = datetime.strptime(valid_to_str, "%Y-%m-%d %H:%M:%S")

    # Skip signals that are HOLD or explicitly REJECTED
    if signal == "HOLD" or signal_info.get("decision") == "REJECTED":
        print(f"⏭️ Skipping {symbol} - Signal {signal} / REJECTED")
        return None

    # Skip if entry/SL/TP are missing
    if entry_price is None or stop_loss is None or take_profit is None:
        print(f"⚠️ Skipping {symbol} - Missing price/SL/TP")
        return None

    print(f"📈 Tracking {symbol} from {valid_from} → {valid_to} for signal {signal}")

    exit_reason = "TIME"
    exit_price = entry_price
    exit_time = None

    # Monitor live until valid_to or exit condition triggered
    while datetime.utcnow() < valid_to:
        try:
            df = fetch_binance_1m_data(symbol, valid_from, datetime.utcnow())
            if df.empty:
                time.sleep(60)
                continue

            current_price = df.iloc[-1]["close"]

            if signal == "BUY":
                if current_price <= stop_loss:
                    exit_reason = "SL"
                    exit_price = stop_loss
                    exit_time = datetime.utcnow()
                    break
                elif current_price >= take_profit:
                    exit_reason = "TP"
                    exit_price = take_profit
                    exit_time = datetime.utcnow()
                    break
            else:  # SELL
                if current_price >= stop_loss:
                    exit_reason = "SL"
                    exit_price = stop_loss
                    exit_time = datetime.utcnow()
                    break
                elif current_price <= take_profit:
                    exit_reason = "TP"
                    exit_price = take_profit
                    exit_time = datetime.utcnow()
                    break

            time.sleep(60)
        except Exception as e:
            print(f"[ERROR] Live tracker failed for {symbol}: {e}")
            time.sleep(60)
            continue

    if exit_time is None:
        exit_time = datetime.utcnow()

    net_return_percent, result, net_profit = calculate_trade_result(
        signal, entry_price, exit_price, exit_reason
    )
    duration = int((exit_time - valid_from).total_seconds() / 60)

    # Update SignalPerformance safely
    try:
        with get_session_context() as session:
            perf = session.query(SignalPerformance).get(perf_id)
            if perf:
                perf.exit_price = str(exit_price)
                perf.exit_reason = exit_reason
                perf.result = result
                perf.return_percent = str(net_return_percent)
                perf.profit_usd = str(net_profit)
                perf.duration_minutes = duration
                perf.tracked_at = datetime.utcnow()
                perf.status = "SUCCESS" if result != "FAILED" else "FAILED"
                session.commit()
                print(f"💾 Updated SignalPerformance ID {perf_id} → {perf.status}")
            else:
                print(f"[WARN] SignalPerformance ID {perf_id} not found")
    except Exception as e:
        print(f"[ERROR] Failed to update SignalPerformance for {symbol}: {e}")

    # Optional callback for live updates to UI or logging
    if update_callback:
        try:
            update_callback({
                "symbol": symbol,
                "signal": signal,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "result": result,
                "profit_usd": net_profit,
                "return_percent": net_return_percent,
                "duration_minutes": duration
            })
        except Exception as e:
            print(f"[ERROR] update_callback failed for {symbol}: {e}")

    return True
