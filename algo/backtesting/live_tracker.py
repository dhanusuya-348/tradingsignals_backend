import time
import os
from datetime import datetime, timedelta

# Load .env variables for local testing
try:
    from load_env import load_env_file
    load_env_file()
    print(f"[{datetime.utcnow()}] ✅ Loaded .env variables")
except ImportError:
    print(f"[{datetime.utcnow()}] ⚠ load_env.py not found, using system environment variables")

from ..data.fetch_price import fetch_binance_1m_data
from ..backtesting.backtester import calculate_trade_result


def monitor_live_signal(symbol, signal_info, update_callback=None):
    from models import get_session_context, SignalPerformance

    symbol = symbol.upper()
    if symbol.endswith("USDT"):
        symbol = symbol[:-4]

    signal = signal_info.get("signal", "HOLD")
    entry_price = signal_info.get("price") or signal_info.get("price_snapshot", {}).get("close")
    
    risk_info = signal_info.get("risk", {})
    stop_loss = risk_info.get("suggested_stop_loss", 0.0)
    take_profit = risk_info.get("suggested_take_profit", 0.0)
    confidence = signal_info.get("confidence", 0)
    interval = signal_info.get("interval", "1h")

    # --- Get duration safely ---
    timing_info = signal_info.get("timing", {})
    estimated_duration = 60  # default duration

    if "duration" in timing_info and isinstance(timing_info["duration"], str):
        duration_str = timing_info["duration"].replace("~", "").replace("minutes", "").strip()
        try:
            estimated_duration = int(float(duration_str))
        except Exception:
            pass
    elif "estimated_duration_minutes" in risk_info:
        try:
            estimated_duration = int(risk_info["estimated_duration_minutes"])
        except Exception:
            pass

    # Skip if invalid
    if signal == "HOLD" or signal_info.get("decision") == "REJECTED":
        print(f"⏭️ [LIVE TRACKER] Skipping {symbol} - Signal is {signal} or decision is REJECTED")
        return None

    if not entry_price or not stop_loss or not take_profit:
        print(f"⚠️ [LIVE TRACKER] Skipping {symbol} - Missing entry_price, stop_loss, or take_profit")
        print(f"   Entry: {entry_price}, SL: {stop_loss}, TP: {take_profit}")
        return None

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(minutes=estimated_duration)

    print(f"📈 [LIVE TRACKER] {symbol} {signal} started at {start_time}, watching for {estimated_duration}m until {end_time}")

    # --- Create a SignalPerformance record with status='RUNNING' ---
    perf_id = None
    with get_session_context() as session:
        perf = SignalPerformance(
            signal_id=signal_info.get("id"),
            status="RUNNING",
            tracked_at=start_time
        )
        session.add(perf)
        session.commit()
        perf_id = perf.id
        print(f"🟢 Created SignalPerformance record with ID {perf_id} for {symbol}")

    exit_reason = "TIME"
    exit_price = entry_price
    exit_time = None

    while datetime.utcnow() < end_time:
        try:
            df = fetch_binance_1m_data(symbol, datetime.utcnow() - timedelta(minutes=2), datetime.utcnow())
            
            if df.empty:
                print(f"[WARN] No recent 1m data for {symbol}, retrying in 60s...")
                time.sleep(60)
                continue

            current_price = df.iloc[-1]["close"]

            if signal == "BUY":
                if current_price <= stop_loss:
                    exit_reason = "SL"
                    exit_price = stop_loss
                    exit_time = datetime.utcnow()
                    print(f"🛑 [LIVE TRACKER] {symbol} hit SL at {exit_price}")
                    break
                elif current_price >= take_profit:
                    exit_reason = "TP"
                    exit_price = take_profit
                    exit_time = datetime.utcnow()
                    print(f"✨ [LIVE TRACKER] {symbol} hit TP at {exit_price}")
                    break
            else:  # SELL
                if current_price >= stop_loss:
                    exit_reason = "SL"
                    exit_price = stop_loss
                    exit_time = datetime.utcnow()
                    print(f"🛑 [LIVE TRACKER] {symbol} hit SL at {exit_price}")
                    break
                elif current_price <= take_profit:
                    exit_reason = "TP"
                    exit_price = take_profit
                    exit_time = datetime.utcnow()
                    print(f"✨ [LIVE TRACKER] {symbol} hit TP at {exit_price}")
                    break

            time.sleep(60)

        except Exception as e:
            print(f"[ERROR] Live tracker failed for {symbol}: {e}")
            time.sleep(60)
            continue

    if exit_time is None:
        exit_time = datetime.utcnow()

    # --- Compute performance ---
    net_return_percent, result, net_profit = calculate_trade_result(
        signal, entry_price, exit_price, exit_reason
    )
    duration = int((exit_time - start_time).total_seconds() / 60)

    result_dict = {
        "symbol": symbol,
        "signal": signal,
        "confidence": confidence,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "entry_time": start_time,
        "exit_time": exit_time,
        "return_percent": net_return_percent,
        "profit_usd": net_profit,
        "result": result,
        "duration_minutes": duration
    }

    print(f"✅ [LIVE RESULT] {symbol}: {result_dict}")

    # --- Update record as SUCCESS or FAILED ---
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
    except Exception as e:
        print(f"[ERROR] Failed to update SignalPerformance for {symbol}: {e}")

    if update_callback:
        update_callback(result_dict)

    return result_dict
