# algo/backtesting/live_tracker.py
import time
from datetime import datetime
import json
from ..data.fetch_price import fetch_binance_1m_data
from ..backtesting.backtester import calculate_trade_result
from models import get_session_context, SignalPerformance

def monitor_live_signal(symbol, signal_info, perf_id, update_callback=None):
    """
    Monitors a signal by backtesting it against historical price data from signal start → end time.
    This is NOT real-time monitoring, but historical backtest evaluation.
    """

    # Handle payload as string or dict
    if isinstance(signal_info, str):
        try:
            signal_info = json.loads(signal_info)
        except Exception as e:
            print(f"[ERROR] Failed to parse signal_info: {e}")
            return None

    # Normalize symbol
    symbol = symbol.upper()
    if symbol.endswith("USDT"):
        symbol = symbol[:-4]

    # Extract signal, entry price, risk info
    signal = signal_info.get("signal", "HOLD")
    entry_price = (
        signal_info.get("price")
        or signal_info.get("price_snapshot", {}).get("close")
        or 0.0
    )

    risk_info = signal_info.get("risk", {})
    strategies_info = signal_info.get("strategies", {})

    stop_loss = (
        risk_info.get("suggested_stop_loss")
        or strategies_info.get("suggested_stop_loss")
        or 0.0
    )
    take_profit = (
        risk_info.get("suggested_take_profit")
        or strategies_info.get("suggested_take_profit")
        or 0.0
    )
    confidence = signal_info.get("confidence", 0)

    # Timing info
    timing_info = signal_info.get("timing", {})
    valid_from_str = timing_info.get("start")
    valid_to_str = timing_info.get("end")
    
    if not valid_from_str or not valid_to_str:
        print(f"[WARN] Missing timing info for {symbol}, skipping")
        return None

    try:
        valid_from = datetime.strptime(valid_from_str, "%Y-%m-%d %H:%M:%S")
        valid_to = datetime.strptime(valid_to_str, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"[ERROR] Failed to parse timing: {e}")
        return None

    # Skip HOLD or REJECTED signals
    if signal == "HOLD" or signal_info.get("decision") == "REJECTED":
        print(f"⏭️ Skipping {symbol} - Signal {signal} / REJECTED")
        return None

    # Only skip if entry price is missing
    if entry_price == 0.0:
        print(f"⚠️ Skipping {symbol} - Missing entry price")
        return None

    print(f"📈 Tracking {symbol} | Signal: {signal} | Entry: {entry_price} | SL: {stop_loss} | TP: {take_profit}")
    print(f"   Evaluating from {valid_from} → {valid_to}")

    exit_reason = "TIME"
    exit_price = entry_price
    exit_time = valid_to

    # ✅ FETCH HISTORICAL DATA FROM SIGNAL START TO END TIME (like backtester.py)
    try:
        minute_data = fetch_binance_1m_data(symbol, valid_from, valid_to)
        
        if minute_data.empty:
            print(f"[WARN] No price data for {symbol} between {valid_from} and {valid_to}, using entry price as exit")
            exit_price = entry_price
            exit_reason = "NO_DATA"
        else:
            print(f"[DEBUG] Fetched {len(minute_data)} candles for {symbol}")
            
            # Check each candle for SL/TP hits
            for t, row in minute_data.iterrows():
                high = row["high"]
                low = row["low"]

                if signal == "BUY":
                    # BUY: Check if SL hit first, then TP
                    if stop_loss and low <= stop_loss:
                        exit_reason = "SL"
                        exit_price = stop_loss
                        exit_time = t
                        print(f"   ❌ BUY hit SL @ {stop_loss}")
                        break
                    elif take_profit and high >= take_profit:
                        exit_reason = "TP"
                        exit_price = take_profit
                        exit_time = t
                        print(f"   ✅ BUY hit TP @ {take_profit}")
                        break
                
                else:  # SELL
                    # SELL: Check if SL hit first, then TP
                    if stop_loss and high >= stop_loss:
                        exit_reason = "SL"
                        exit_price = stop_loss
                        exit_time = t
                        print(f"   ❌ SELL hit SL @ {stop_loss}")
                        break
                    elif take_profit and low <= take_profit:
                        exit_reason = "TP"
                        exit_price = take_profit
                        exit_time = t
                        print(f"   ✅ SELL hit TP @ {take_profit}")
                        break
            
            # If loop completes without SL/TP, exit at last price (TIME exit)
            if exit_reason == "TIME":
                last_row = minute_data.iloc[-1]
                exit_price = last_row["close"]
                exit_time = minute_data.index[-1]
                print(f"   ⏱️ TIME exit @ {exit_price}")

    except Exception as e:
        print(f"[ERROR] Failed to fetch price data for {symbol}: {e}")
        import traceback
        traceback.print_exc()
        exit_price = entry_price
        exit_reason = "ERROR"

    # Calculate trade result with fees
    net_return_percent, result, net_profit = calculate_trade_result(
        signal, entry_price, exit_price, exit_reason
    )
    duration = int((exit_time - valid_from).total_seconds() / 60)

    # Round to 4 decimal places
    exit_price_rounded = round(float(exit_price), 4)
    return_percent_rounded = round(float(net_return_percent), 4)
    profit_usd_rounded = round(float(net_profit), 4)

    # Determine final status
    final_status = "DONE"

    # Update SignalPerformance safely
    try:
        with get_session_context() as session:
            perf = session.query(SignalPerformance).get(perf_id)
            if perf:
                perf.exit_price = str(exit_price_rounded)
                perf.exit_reason = exit_reason
                perf.result = result
                perf.return_percent = str(return_percent_rounded)
                perf.profit_usd = str(profit_usd_rounded)
                perf.duration_minutes = duration
                perf.tracked_at = datetime.utcnow()
                perf.status = final_status
                session.commit()
                print(f"💾 Updated SignalPerformance ID {perf_id} → {final_status} | Result: {result} | Profit: ${profit_usd_rounded}")
            else:
                print(f"[WARN] SignalPerformance ID {perf_id} not found")
    except Exception as e:
        print(f"[ERROR] Failed to update SignalPerformance for {symbol}: {e}")
        import traceback
        traceback.print_exc()

    # Optional callback for UI/logging
    if update_callback:
        try:
            update_callback({
                "symbol": symbol,
                "signal": signal,
                "entry_price": entry_price,
                "exit_price": exit_price_rounded,
                "exit_reason": exit_reason,
                "result": result,
                "profit_usd": profit_usd_rounded,
                "return_percent": return_percent_rounded,
                "duration_minutes": duration
            })
        except Exception as e:
            print(f"[ERROR] update_callback failed for {symbol}: {e}")

    return True