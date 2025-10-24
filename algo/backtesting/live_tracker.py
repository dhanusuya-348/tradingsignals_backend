def monitor_live_signal(symbol, signal_info, update_callback=None):
    from models import get_session_context, SignalPerformance
    import time
    from datetime import datetime
    from ..data.fetch_price import fetch_binance_1m_data
    from ..backtesting.backtester import calculate_trade_result

    symbol = symbol.upper()
    if symbol.endswith("USDT"):
        symbol = symbol[:-4]

    signal = signal_info.get("signal", "HOLD")
    entry_price = signal_info.get("price") or signal_info.get("price_snapshot", {}).get("close")
    risk_info = signal_info.get("risk", {})
    stop_loss = risk_info.get("suggested_stop_loss", 0.0)
    take_profit = risk_info.get("suggested_take_profit", 0.0)
    confidence = signal_info.get("confidence", 0)

    # --- Use valid_from and valid_to directly ---
    timing_info = signal_info.get("timing", {})
    valid_from_str = timing_info.get("start")  # example: "2025-10-24 08:30:00"
    valid_to_str = timing_info.get("end")
    if not valid_from_str or not valid_to_str:
        print(f"[WARN] Missing valid_from or valid_to, skipping {symbol}")
        return None

    valid_from = datetime.strptime(valid_from_str, "%Y-%m-%d %H:%M:%S")
    valid_to = datetime.strptime(valid_to_str, "%Y-%m-%d %H:%M:%S")

    # Skip if signal is HOLD or REJECTED
    if signal == "HOLD" or signal_info.get("decision") == "REJECTED":
        print(f"⏭️ Skipping {symbol} - Signal is {signal} or decision REJECTED")
        return None

    if not entry_price or not stop_loss or not take_profit:
        print(f"⚠️ Skipping {symbol} - Missing entry_price/SL/TP")
        return None

    print(f"📈 Tracking {symbol} from {valid_from} → {valid_to} for signal {signal}")

    # --- Create SignalPerformance record ---
    perf_id = None
    with get_session_context() as session:
        perf = SignalPerformance(
            signal_id=signal_info.get("id"),
            status="RUNNING",
            tracked_at=datetime.utcnow()
        )
        session.add(perf)
        session.commit()
        perf_id = perf.id
        print(f"🟢 Created SignalPerformance ID {perf_id} for {symbol}")

    exit_reason = "TIME"
    exit_price = entry_price
    exit_time = None

    # Loop over the actual valid_from → valid_to window
    while datetime.utcnow() < valid_to:
        try:
            df = fetch_binance_1m_data(symbol, valid_from, datetime.utcnow())
            if df.empty:
                print(f"[WARN] No 1m data for {symbol}, retrying in 60s")
                time.sleep(60)
                continue

            current_price = df.iloc[-1]["close"]

            if signal == "BUY":
                if current_price <= stop_loss:
                    exit_reason = "SL"
                    exit_price = stop_loss
                    exit_time = datetime.utcnow()
                    print(f"🛑 {symbol} hit SL at {exit_price}")
                    break
                elif current_price >= take_profit:
                    exit_reason = "TP"
                    exit_price = take_profit
                    exit_time = datetime.utcnow()
                    print(f"✨ {symbol} hit TP at {exit_price}")
                    break
            else:  # SELL
                if current_price >= stop_loss:
                    exit_reason = "SL"
                    exit_price = stop_loss
                    exit_time = datetime.utcnow()
                    print(f"🛑 {symbol} hit SL at {exit_price}")
                    break
                elif current_price <= take_profit:
                    exit_reason = "TP"
                    exit_price = take_profit
                    exit_time = datetime.utcnow()
                    print(f"✨ {symbol} hit TP at {exit_price}")
                    break

            time.sleep(60)
        except Exception as e:
            print(f"[ERROR] Live tracker failed for {symbol}: {e}")
            time.sleep(60)
            continue

    if exit_time is None:
        exit_time = datetime.utcnow()

    # --- Compute results ---
    net_return_percent, result, net_profit = calculate_trade_result(
        signal, entry_price, exit_price, exit_reason
    )
    duration = int((exit_time - valid_from).total_seconds() / 60)

    result_dict = {
        "symbol": symbol,
        "signal": signal,
        "confidence": confidence,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "entry_time": valid_from,
        "exit_time": exit_time,
        "return_percent": net_return_percent,
        "profit_usd": net_profit,
        "result": result,
        "duration_minutes": duration
    }

    # --- Update DB ---
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
