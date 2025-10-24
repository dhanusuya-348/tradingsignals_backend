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
    import time
    from datetime import datetime, timedelta
    from ..data.fetch_price import fetch_binance_1m_data
    from ..backtesting.backtester import calculate_trade_result

    # Ensure symbol does not double append USDT
    symbol = symbol.upper()
    if symbol.endswith("USDT"):
        symbol = symbol[:-4]

    signal = signal_info["signal"]
    entry_price = signal_info.get("price") or signal_info.get("price_snapshot", {}).get("close")
    stop_loss = signal_info["risk"]["suggested_stop_loss"]
    take_profit = signal_info["risk"]["suggested_take_profit"]
    confidence = signal_info["confidence"]
    interval = signal_info.get("interval", "1h")
    estimated_duration = signal_info["risk"]["estimated_duration_minutes"]

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(minutes=estimated_duration)

    print(f"📈 [LIVE TRACKER] {symbol} {signal} started at {start_time}, watching until {end_time}")

    exit_reason = "TIME"
    exit_price = entry_price
    exit_time = None

    while datetime.utcnow() < end_time:
        try:
            # Fetch only the last 2 minutes of 1m data
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

            time.sleep(60)  # wait 1 minute before next check

        except Exception as e:
            print(f"[ERROR] Live tracker failed for {symbol}: {e}")
            time.sleep(60)
            continue

    if exit_time is None:
        exit_time = datetime.utcnow()

    # Compute PnL
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

    # --- Save to DB ---
    try:
        with get_session_context() as session:
            perf = SignalPerformance(
                signal_id=signal_info["id"],  # make sure signal_info has DB id
                exit_price=str(exit_price),
                exit_reason=exit_reason,
                result=result,
                return_percent=str(net_return_percent),
                profit_usd=str(net_profit),
                duration_minutes=duration,
                tracked_at=datetime.utcnow()
            )
            session.add(perf)
            session.commit()
            print(f"💾 Live performance saved for {symbol}")
    except Exception as e:
        print(f"[ERROR] Failed to save live performance for {symbol}: {e}")

    if update_callback:
        update_callback(result_dict)

    return result_dict
