# performance_monitor.py
import sys
import time
from datetime import datetime
from threading import Thread
import json

# Force unbuffered output for systemd logs
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# Load .env variables for local testing
try:
    from load_env import load_env_file
    load_env_file()
    print(f"[{datetime.utcnow()}] ✅ Loaded .env variables")
except ImportError:
    print(f"[{datetime.utcnow()}] ⚠ load_env.py not found, using system environment variables")

from models import get_session_context, Signal, SignalPerformance
from algo.backtesting.live_tracker import monitor_live_signal

# ===== NEW: Import Twitter Service =====
try:
    from twitter_service import TwitterService
    twitter_service = TwitterService()
    print(f"[{datetime.utcnow()}] ✅ Twitter service initialized")
except Exception as e:
    twitter_service = None
    print(f"[{datetime.utcnow()}] ⚠️  Twitter service not available: {e}")

# --- CONFIG ---
START_DATE = datetime(2025, 10, 25)
CHECK_INTERVAL = 30  # Seconds between checks
STATE_FILE_SCANNER = "/tmp/perfmon_scanner_last_id.txt"
STATE_FILE_PROCESSOR = "/tmp/perfmon_processor_last_id.txt"

def load_last_checked_id(state_file):
    try:
        with open(state_file, "r") as f:
            return int(f.read().strip())
    except:
        return 0

def save_last_checked_id(state_file, last_id):
    with open(state_file, "w") as f:
        f.write(str(last_id))

# ===== NEW: Helper function to post to Twitter =====
def post_signal_to_twitter(symbol, entry_price, exit_price, return_percent, profit_usd, result, duration_minutes):
    """Post completed signal to Twitter"""
    if not twitter_service:
        print(f"[TWITTER] ⚠️  Twitter service not available, skipping post")
        return False
    
    try:
        print(f"[TWITTER] 📡 Posting {symbol} {result} to Twitter...")
        
        tweet_id = twitter_service.post_signal_performance(
            symbol=symbol,
            entry_price=float(entry_price),
            exit_price=float(exit_price),
            return_percent=float(return_percent),
            profit_usd=float(profit_usd),
            result=result.upper(),
            duration_minutes=int(duration_minutes)
        )
        
        if tweet_id:
            print(f"[TWITTER] ✅ Posted! Tweet ID: {tweet_id}")
            return True
        else:
            print(f"[TWITTER] ❌ Failed to post signal")
            return False
            
    except Exception as e:
        print(f"[TWITTER] ❌ Error posting to Twitter: {e}")
        import traceback
        traceback.print_exc()
        return False

def process_signal_thread(signal_id, perf_id):
    """Thread to monitor a single signal in real-time"""
    try:
        # Fetch signal in a new session (thread-safe)
        with get_session_context() as session:
            signal_obj = session.query(Signal).filter_by(id=signal_id).first()
            if not signal_obj:
                print(f"[ERROR] Signal ID {signal_id} not found")
                return False
            
            # Detach from session before passing to monitor_live_signal
            symbol = signal_obj.symbol
            payload = signal_obj.payload

        # Now monitor it (outside the session context)
        # monitor_live_signal returns: {
        #   'success': bool,
        #   'entry_price': float,
        #   'exit_price': float,
        #   'return_percent': float,
        #   'profit_usd': float,
        #   'result': 'SUCCESS' or 'FAILURE',
        #   'duration_minutes': int
        # }
        result = monitor_live_signal(symbol, payload, perf_id)
        
        if result:
            print(f"✅ Signal {signal_id} completed")
            
            # ===== NEW: Post to Twitter after signal completes =====
            entry_price = result.get('entry_price', payload.get('price', 0))
            exit_price = result.get('exit_price', 0)
            return_percent = result.get('return_percent', 0)
            profit_usd = result.get('profit_usd', 0)
            trade_result = result.get('result', 'FAILURE')
            duration_minutes = result.get('duration_minutes', 0)
            
            # Post to Twitter in background (non-blocking)
            post_signal_to_twitter(
                symbol=symbol,
                entry_price=entry_price,
                exit_price=exit_price,
                return_percent=return_percent,
                profit_usd=profit_usd,
                result=trade_result,
                duration_minutes=duration_minutes
            )
            # =====
            
            return True
        else:
            print(f"❌ Signal {signal_id} failed or timeout")
            return False
        
    except Exception as e:
        print(f"[ERROR] Exception while processing signal {signal_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def scan_and_add_expired_signals():
    """
    Phase 1: Scan signals table for EXPIRED signals and add them to signal_performance
    with status="PENDING"
    """
    print(f"[{datetime.utcnow()}] 📡 Scanner thread started")
    last_checked_id = load_last_checked_id(STATE_FILE_SCANNER)
    print(f"[SCANNER] Loaded last_checked_id: {last_checked_id}")

    while True:
        try:
            print(f"[SCANNER] [LOOP] Attempting DB query at {datetime.utcnow()}")
            with get_session_context() as session:
                print(f"[SCANNER] [CONNECTED] Session acquired")
                
                # DEBUG: Check total count first
                total_signals = session.query(Signal).filter(
                    Signal.id > last_checked_id,
                    Signal.created_at >= START_DATE
                ).count()
                print(f"[SCANNER] [DEBUG] Found {total_signals} signals with ID > {last_checked_id} and created_at >= {START_DATE}")
                
                # Fetch signals after last_checked_id, created after START_DATE
                signals = session.query(Signal)\
                    .filter(Signal.id > last_checked_id)\
                    .filter(Signal.created_at >= START_DATE)\
                    .order_by(Signal.id.asc())\
                    .all()

                if signals:
                    print(f"[SCANNER] Found {len(signals)} new signal(s) to check")
                    processed_count = 0

                    for sig in signals:
                        payload = sig.payload or {}

                        # Parse JSON if payload is string
                        if isinstance(payload, str):
                            try:
                                payload = json.loads(payload)
                            except Exception as e:
                                print(f"[ERROR] Failed to parse payload for Signal ID {sig.id}: {e}")
                                last_checked_id = max(last_checked_id, sig.id)
                                continue

                        # Extract timing info
                        timing = payload.get("timing", {})
                        valid_to_str = timing.get("end")

                        if not valid_to_str:
                            print(f"[WARN] Signal ID {sig.id} has no timing.end, skipping permanently")
                            last_checked_id = max(last_checked_id, sig.id)
                            continue

                        try:
                            valid_to = datetime.strptime(valid_to_str, "%Y-%m-%d %H:%M:%S")
                        except Exception as e:
                            print(f"[ERROR] Failed to parse valid_to for Signal ID {sig.id}: {e}")
                            last_checked_id = max(last_checked_id, sig.id)
                            continue

                        # Check if signal is EXPIRED (valid_to is in the past)
                        now = datetime.utcnow()
                        if now >= valid_to:
                            # Check if already in signal_performance
                            exists = session.query(SignalPerformance).filter_by(signal_id=sig.id).first()
                            
                            if not exists:
                                perf = SignalPerformance(
                                    signal_id=sig.id,
                                    status="PENDING",
                                    tracked_at=now
                                )
                                session.add(perf)
                                session.commit()
                                print(f"🟢 Signal {sig.id} added to SignalPerformance (ID {perf.id}) - EXPIRED at {valid_to}")
                                processed_count += 1
                            else:
                                print(f"[INFO] Signal {sig.id} already tracked, skipping")
                            
                            # ✅ Only update last_checked_id for EXPIRED signals (processed or already tracked)
                            last_checked_id = max(last_checked_id, sig.id)
                        else:
                            time_remaining = (valid_to - now).total_seconds() / 60
                            print(f"[INFO] Signal ID {sig.id} still active ({time_remaining:.1f} min left), NOT updating last_checked_id")
                            # ❌ DON'T update last_checked_id - we need to check this signal again when it expires!

                    # Save state only after processing batch
                    if processed_count > 0 or any(now >= datetime.strptime(json.loads(s.payload if isinstance(s.payload, str) else json.dumps(s.payload)).get("timing", {}).get("end", "2099-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S") for s in signals if s.payload):
                        save_last_checked_id(STATE_FILE_SCANNER, last_checked_id)
                        print(f"[SCANNER] Saved state: last_checked_id={last_checked_id}\n")
                else:
                    print(f"[SCANNER] [DEBUG] No new signals found (last_checked_id={last_checked_id})")

        except Exception as e:
            print(f"[ERROR] Scanner failed: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(CHECK_INTERVAL)

def process_pending_signals():
    """
    Phase 2: Process all PENDING signals in signal_performance table
    by fetching corresponding signal data and running backtest
    """
    print(f"[{datetime.utcnow()}] ⚙️  Processor thread started\n")
    last_processed_id = load_last_checked_id(STATE_FILE_PROCESSOR)
    print(f"[PROCESSOR] Loaded last_processed_id: {last_processed_id}")

    while True:
        try:
            print(f"[PROCESSOR] [LOOP] Attempting DB query at {datetime.utcnow()}")
            with get_session_context() as session:
                print(f"[PROCESSOR] [CONNECTED] Session acquired")
                
                # DEBUG: Check total pending count
                total_pending = session.query(SignalPerformance).filter(
                    SignalPerformance.status == "PENDING",
                    SignalPerformance.id > last_processed_id
                ).count()
                print(f"[PROCESSOR] [DEBUG] Found {total_pending} PENDING signals with ID > {last_processed_id}")
                
                # Fetch PENDING signals (limit to prevent memory issues)
                pending_perfs = session.query(SignalPerformance)\
                    .filter_by(status="PENDING")\
                    .filter(SignalPerformance.id > last_processed_id)\
                    .order_by(SignalPerformance.id.asc())\
                    .limit(5)\
                    .all()

                if pending_perfs:
                    print(f"[PROCESSOR] Found {len(pending_perfs)} PENDING signal(s) to process")

                    for perf in pending_perfs:
                        try:
                            signal_id = perf.signal_id
                            perf_id = perf.id
                            
                            # Update status to RUNNING
                            perf.status = "RUNNING"
                            session.commit()
                            print(f"📊 Processing Signal {signal_id} (PerfID {perf_id})...")

                            # Start backtesting in a NEW THREAD
                            thread = Thread(target=process_signal_thread, args=(signal_id, perf_id))
                            thread.daemon = True
                            thread.start()

                            last_processed_id = max(last_processed_id, perf.id)

                        except Exception as e:
                            print(f"[ERROR] Failed to process signal_performance ID {perf.id}: {e}")
                            import traceback
                            traceback.print_exc()
                            last_processed_id = max(last_processed_id, perf.id)

                    # Save state after batch
                    save_last_checked_id(STATE_FILE_PROCESSOR, last_processed_id)
                    print(f"[PROCESSOR] Saved state: last_processed_id={last_processed_id}\n")
                else:
                    print(f"[PROCESSOR] [DEBUG] No PENDING signals found (last_processed_id={last_processed_id})")

        except Exception as e:
            print(f"[ERROR] Processor failed: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    print(f"[{datetime.utcnow()}] 🚀 Starting Performance Monitor (2-phase)...\n")

    # Phase 1: Scanner (find expired signals, add to DB as PENDING)
    scanner_thread = Thread(target=scan_and_add_expired_signals, daemon=False)
    scanner_thread.start()

    # Phase 2: Processor (take PENDING signals, backtest, mark as DONE/FAILED)
    processor_thread = Thread(target=process_pending_signals, daemon=False)
    processor_thread.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Performance Monitor shutting down...")

# # performance_monitor.py
# import sys
# import time
# from datetime import datetime
# from threading import Thread
# import json
# from twitter_service import TwitterService

# # Force unbuffered output for systemd logs
# sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# # Load .env variables for local testing
# try:
#     from load_env import load_env_file
#     load_env_file()
#     print(f"[{datetime.utcnow()}] ✅ Loaded .env variables")
# except ImportError:
#     print(f"[{datetime.utcnow()}] ⚠ load_env.py not found, using system environment variables")

# from models import get_session_context, Signal, SignalPerformance
# from algo.backtesting.live_tracker import monitor_live_signal

# # --- CONFIG ---
# START_DATE = datetime(2025, 10, 25)
# CHECK_INTERVAL = 30  # Seconds between checks
# STATE_FILE_SCANNER = "/tmp/perfmon_scanner_last_id.txt"
# STATE_FILE_PROCESSOR = "/tmp/perfmon_processor_last_id.txt"

# def load_last_checked_id(state_file):
#     try:
#         with open(state_file, "r") as f:
#             return int(f.read().strip())
#     except:
#         return 0

# def save_last_checked_id(state_file, last_id):
#     with open(state_file, "w") as f:
#         f.write(str(last_id))

# def process_signal_thread(signal_id, perf_id):
#     """Thread to monitor a single signal in real-time"""
#     try:
#         # Fetch signal in a new session (thread-safe)
#         with get_session_context() as session:
#             signal_obj = session.query(Signal).filter_by(id=signal_id).first()
#             if not signal_obj:
#                 print(f"[ERROR] Signal ID {signal_id} not found")
#                 return False
            
#             # Detach from session before passing to monitor_live_signal
#             symbol = signal_obj.symbol
#             payload = signal_obj.payload
        
#         # Now monitor it (outside the session context)
#         result = monitor_live_signal(symbol, payload, perf_id)
#         if result:
#             print(f"✅ Signal {signal_id} completed")
#         return result
        
#     except Exception as e:
#         print(f"[ERROR] Exception while processing signal {signal_id}: {e}")
#         import traceback
#         traceback.print_exc()
#         return False

# def scan_and_add_expired_signals():
#     """
#     Phase 1: Scan signals table for EXPIRED signals and add them to signal_performance
#     with status="PENDING"
#     """
#     print(f"[{datetime.utcnow()}] 📡 Scanner thread started")
#     last_checked_id = load_last_checked_id(STATE_FILE_SCANNER)
#     print(f"[SCANNER] Loaded last_checked_id: {last_checked_id}")

#     while True:
#         try:
#             print(f"[SCANNER] [LOOP] Attempting DB query at {datetime.utcnow()}")
#             with get_session_context() as session:
#                 print(f"[SCANNER] [CONNECTED] Session acquired")
                
#                 # DEBUG: Check total count first
#                 total_signals = session.query(Signal).filter(
#                     Signal.id > last_checked_id,
#                     Signal.created_at >= START_DATE
#                 ).count()
#                 print(f"[SCANNER] [DEBUG] Found {total_signals} signals with ID > {last_checked_id} and created_at >= {START_DATE}")
                
#                 # Fetch signals after last_checked_id, created after START_DATE
#                 signals = session.query(Signal)\
#                     .filter(Signal.id > last_checked_id)\
#                     .filter(Signal.created_at >= START_DATE)\
#                     .order_by(Signal.id.asc())\
#                     .all()

#                 if signals:
#                     print(f"[SCANNER] Found {len(signals)} new signal(s) to check")
#                     processed_count = 0

#                     for sig in signals:
#                         payload = sig.payload or {}

#                         # Parse JSON if payload is string
#                         if isinstance(payload, str):
#                             try:
#                                 payload = json.loads(payload)
#                             except Exception as e:
#                                 print(f"[ERROR] Failed to parse payload for Signal ID {sig.id}: {e}")
#                                 last_checked_id = max(last_checked_id, sig.id)
#                                 continue

#                         # Extract timing info
#                         timing = payload.get("timing", {})
#                         valid_to_str = timing.get("end")

#                         if not valid_to_str:
#                             print(f"[WARN] Signal ID {sig.id} has no timing.end, skipping permanently")
#                             last_checked_id = max(last_checked_id, sig.id)
#                             continue

#                         try:
#                             valid_to = datetime.strptime(valid_to_str, "%Y-%m-%d %H:%M:%S")
#                         except Exception as e:
#                             print(f"[ERROR] Failed to parse valid_to for Signal ID {sig.id}: {e}")
#                             last_checked_id = max(last_checked_id, sig.id)
#                             continue

#                         # Check if signal is EXPIRED (valid_to is in the past)
#                         now = datetime.utcnow()
#                         if now >= valid_to:
#                             # Check if already in signal_performance
#                             exists = session.query(SignalPerformance).filter_by(signal_id=sig.id).first()
                            
#                             if not exists:
#                                 perf = SignalPerformance(
#                                     signal_id=sig.id,
#                                     status="PENDING",
#                                     tracked_at=now
#                                 )
#                                 session.add(perf)
#                                 session.commit()
#                                 print(f"🟢 Signal {sig.id} added to SignalPerformance (ID {perf.id}) - EXPIRED at {valid_to}")
#                                 processed_count += 1
#                             else:
#                                 print(f"[INFO] Signal {sig.id} already tracked, skipping")
                            
#                             # ✅ Only update last_checked_id for EXPIRED signals (processed or already tracked)
#                             last_checked_id = max(last_checked_id, sig.id)
#                         else:
#                             time_remaining = (valid_to - now).total_seconds() / 60
#                             print(f"[INFO] Signal ID {sig.id} still active ({time_remaining:.1f} min left), NOT updating last_checked_id")
#                             # ❌ DON'T update last_checked_id - we need to check this signal again when it expires!

#                     # Save state only after processing batch
#                     if processed_count > 0 or any(now >= datetime.strptime(json.loads(s.payload if isinstance(s.payload, str) else json.dumps(s.payload)).get("timing", {}).get("end", "2099-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S") for s in signals if s.payload):
#                         save_last_checked_id(STATE_FILE_SCANNER, last_checked_id)
#                         print(f"[SCANNER] Saved state: last_checked_id={last_checked_id}\n")
#                 else:
#                     print(f"[SCANNER] [DEBUG] No new signals found (last_checked_id={last_checked_id})")

#         except Exception as e:
#             print(f"[ERROR] Scanner failed: {e}")
#             import traceback
#             traceback.print_exc()

#         time.sleep(CHECK_INTERVAL)

# def process_pending_signals():
#     """
#     Phase 2: Process all PENDING signals in signal_performance table
#     by fetching corresponding signal data and running backtest
#     """
#     print(f"[{datetime.utcnow()}] ⚙️  Processor thread started\n")
#     last_processed_id = load_last_checked_id(STATE_FILE_PROCESSOR)
#     print(f"[PROCESSOR] Loaded last_processed_id: {last_processed_id}")

#     while True:
#         try:
#             print(f"[PROCESSOR] [LOOP] Attempting DB query at {datetime.utcnow()}")
#             with get_session_context() as session:
#                 print(f"[PROCESSOR] [CONNECTED] Session acquired")
                
#                 # DEBUG: Check total pending count
#                 total_pending = session.query(SignalPerformance).filter(
#                     SignalPerformance.status == "PENDING",
#                     SignalPerformance.id > last_processed_id
#                 ).count()
#                 print(f"[PROCESSOR] [DEBUG] Found {total_pending} PENDING signals with ID > {last_processed_id}")
                
#                 # Fetch PENDING signals (limit to prevent memory issues)
#                 pending_perfs = session.query(SignalPerformance)\
#                     .filter_by(status="PENDING")\
#                     .filter(SignalPerformance.id > last_processed_id)\
#                     .order_by(SignalPerformance.id.asc())\
#                     .limit(5)\
#                     .all()

#                 if pending_perfs:
#                     print(f"[PROCESSOR] Found {len(pending_perfs)} PENDING signal(s) to process")

#                     for perf in pending_perfs:
#                         try:
#                             signal_id = perf.signal_id
#                             perf_id = perf.id
                            
#                             # Update status to RUNNING
#                             perf.status = "RUNNING"
#                             session.commit()
#                             print(f"📊 Processing Signal {signal_id} (PerfID {perf_id})...")

#                             # Start backtesting in a NEW THREAD
#                             thread = Thread(target=process_signal_thread, args=(signal_id, perf_id))
#                             thread.daemon = True
#                             thread.start()

#                             last_processed_id = max(last_processed_id, perf.id)

#                         except Exception as e:
#                             print(f"[ERROR] Failed to process signal_performance ID {perf.id}: {e}")
#                             import traceback
#                             traceback.print_exc()
#                             last_processed_id = max(last_processed_id, perf.id)

#                     # Save state after batch
#                     save_last_checked_id(STATE_FILE_PROCESSOR, last_processed_id)
#                     print(f"[PROCESSOR] Saved state: last_processed_id={last_processed_id}\n")
#                 else:
#                     print(f"[PROCESSOR] [DEBUG] No PENDING signals found (last_processed_id={last_processed_id})")

#         except Exception as e:
#             print(f"[ERROR] Processor failed: {e}")
#             import traceback
#             traceback.print_exc()

#         time.sleep(CHECK_INTERVAL)

# if __name__ == "__main__":
#     print(f"[{datetime.utcnow()}] 🚀 Starting Performance Monitor (2-phase)...\n")

#     # Phase 1: Scanner (find expired signals, add to DB as PENDING)
#     scanner_thread = Thread(target=scan_and_add_expired_signals, daemon=False)
#     scanner_thread.start()

#     # Phase 2: Processor (take PENDING signals, backtest, mark as DONE/FAILED)
#     processor_thread = Thread(target=process_pending_signals, daemon=False)
#     processor_thread.start()

#     # Keep main thread alive
#     try:
#         while True:
#             time.sleep(1)
#     except KeyboardInterrupt:
#         print("\n[SHUTDOWN] Performance Monitor shutting down...")