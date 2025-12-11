import sys
import time
from datetime import datetime
from threading import Thread
import json

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

try:
    from load_env import load_env_file
    load_env_file()
    print(f"[{datetime.utcnow()}] ✅ Loaded .env variables")
except ImportError:
    print(f"[{datetime.utcnow()}] ⚠ load_env.py not found, using system environment variables")

from models import get_session_context, Signal, SignalPerformance
from algo.backtesting.live_tracker import monitor_live_signal

# ===== TWITTER SERVICE =====
try:
    from twitter_service import TwitterService
    twitter_service = TwitterService()
    test_result = twitter_service.test_connection()
    if test_result:
        print(f"[{datetime.utcnow()}] ✅ Twitter service initialized and connected")
    else:
        twitter_service = None
        print(f"[{datetime.utcnow()}] ❌ Twitter service failed connection test")
except Exception as e:
    twitter_service = None
    print(f"[{datetime.utcnow()}] ⚠️  Twitter service initialization error: {e}")

# --- CONFIG ---
START_DATE = datetime(2025, 10, 25)
CHECK_INTERVAL = 30
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

def post_signal_to_twitter_safe(signal_data, performance_data):
    """
    Safely post signal performance to Twitter with proper error handling.
    Returns True if successful, False otherwise.
    """
    if not twitter_service:
        print(f"[TWITTER] ⚠️  Twitter service not initialized, cannot post")
        return False
    
    try:
        symbol = signal_data.get('symbol', 'UNKNOWN')
        entry_price = float(signal_data.get('entry_price', performance_data.get('entry_price', 0)))
        exit_price = float(performance_data.get('exit_price', 0))
        return_percent = float(performance_data.get('return_percent', 0))
        profit_usd = float(performance_data.get('profit_usd', 0))
        result = performance_data.get('result', 'FAILURE').upper()
        duration_minutes = int(performance_data.get('duration_minutes', 0))
        
        print(f"\n[TWITTER] 📡 Preparing to post {symbol} {result} signal to X.com...")
        print(f"[TWITTER]   Entry: ${entry_price:.4f} → Exit: ${exit_price:.4f}")
        print(f"[TWITTER]   Return: {return_percent:.2f}% | P&L: ${profit_usd:.2f} | Duration: {duration_minutes}min")
        
        tweet_id = twitter_service.post_signal_performance(
            symbol=symbol,
            entry_price=entry_price,
            exit_price=exit_price,
            return_percent=return_percent,
            profit_usd=profit_usd,
            result=result,
            duration_minutes=duration_minutes
        )
        
        if tweet_id:
            print(f"[TWITTER] ✅ SUCCESS! Posted to X.com")
            print(f"[TWITTER]   Tweet ID: {tweet_id}")
            print(f"[TWITTER]   URL: https://x.com/dollaraptor/status/{tweet_id}\n")
            return True
        else:
            print(f"[TWITTER] ❌ Failed to post (API returned None)\n")
            return False
            
    except Exception as e:
        print(f"[TWITTER] ❌ Exception while posting: {e}\n")
        import traceback
        traceback.print_exc()
        return False

def process_signal_thread(signal_id, perf_id):
    """
    Thread to monitor a single signal in real-time and post results to Twitter.
    """
    print(f"\n[PROCESSOR] 🔄 Starting signal processing (Signal ID: {signal_id}, Perf ID: {perf_id})")
    
    try:
        # Fetch signal in a new session (thread-safe)
        signal_data = {}
        with get_session_context() as session:
            signal_obj = session.query(Signal).filter_by(id=signal_id).first()
            if not signal_obj:
                print(f"[ERROR] Signal ID {signal_id} not found in database")
                return False
            
            # Extract signal data
            symbol = signal_obj.symbol
            payload = signal_obj.payload or {}
            signal_data = {
                'id': signal_obj.id,
                'symbol': symbol,
                'entry_price': payload.get('price', 0),
                'payload': payload
            }
            
            print(f"[PROCESSOR] Found signal: {symbol}")

        # Monitor the signal (outside session context)
        result = monitor_live_signal(symbol, signal_data['payload'], perf_id)
        
        if result and result.get('success', False):
            print(f"[PROCESSOR] ✅ Signal {signal_id} completed successfully")
            print(f"[PROCESSOR]   Result: {result}")
            
            # Prepare performance data
            performance_data = {
                'entry_price': result.get('entry_price', signal_data['entry_price']),
                'exit_price': result.get('exit_price', 0),
                'return_percent': result.get('return_percent', 0),
                'profit_usd': result.get('profit_usd', 0),
                'result': result.get('result', 'FAILURE'),
                'duration_minutes': result.get('duration_minutes', 0)
            }
            
            # Update database with completed status
            try:
                with get_session_context() as session:
                    perf = session.query(SignalPerformance).filter_by(id=perf_id).first()
                    if perf:
                        perf.status = "COMPLETED"
                        perf.exit_price = performance_data['exit_price']
                        perf.return_percent = performance_data['return_percent']
                        perf.profit_usd = performance_data['profit_usd']
                        perf.result = performance_data['result']
                        perf.duration_minutes = performance_data['duration_minutes']
                        session.commit()
                        print(f"[PROCESSOR] Database updated for Perf ID {perf_id}")
            except Exception as db_error:
                print(f"[PROCESSOR] ⚠️  Database update error: {db_error}")
            
            # POST TO TWITTER (in background thread to not block)
            print(f"[PROCESSOR] Starting Twitter posting thread...")
            twitter_thread = Thread(
                target=post_signal_to_twitter_safe,
                args=(signal_data, performance_data),
                daemon=True
            )
            twitter_thread.start()
            
            return True
        else:
            print(f"[PROCESSOR] ❌ Signal {signal_id} failed or returned no result")
            
            # Update database with failed status
            try:
                with get_session_context() as session:
                    perf = session.query(SignalPerformance).filter_by(id=perf_id).first()
                    if perf:
                        perf.status = "FAILED"
                        session.commit()
            except Exception as db_error:
                print(f"[PROCESSOR] ⚠️  Database update error: {db_error}")
            
            return False
        
    except Exception as e:
        print(f"[PROCESSOR] ❌ Exception processing signal {signal_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def scan_and_add_expired_signals():
    """
    Phase 1: Scan signals table for EXPIRED signals
    """
    print(f"[{datetime.utcnow()}] 📡 Scanner thread started")
    last_checked_id = load_last_checked_id(STATE_FILE_SCANNER)
    print(f"[SCANNER] Loaded last_checked_id: {last_checked_id}")

    while True:
        try:
            print(f"[SCANNER] [LOOP] Checking at {datetime.utcnow()}")
            with get_session_context() as session:
                total_signals = session.query(Signal).filter(
                    Signal.id > last_checked_id,
                    Signal.created_at >= START_DATE
                ).count()
                print(f"[SCANNER] Found {total_signals} new signals")
                
                signals = session.query(Signal)\
                    .filter(Signal.id > last_checked_id)\
                    .filter(Signal.created_at >= START_DATE)\
                    .order_by(Signal.id.asc())\
                    .all()

                if signals:
                    print(f"[SCANNER] Processing {len(signals)} signal(s)...")
                    processed_count = 0

                    for sig in signals:
                        payload = sig.payload or {}

                        if isinstance(payload, str):
                            try:
                                payload = json.loads(payload)
                            except Exception as e:
                                print(f"[SCANNER] ❌ Failed to parse Signal {sig.id}: {e}")
                                last_checked_id = max(last_checked_id, sig.id)
                                continue

                        timing = payload.get("timing", {})
                        valid_to_str = timing.get("end")

                        if not valid_to_str:
                            print(f"[SCANNER] ⚠️  Signal {sig.id} has no end time")
                            last_checked_id = max(last_checked_id, sig.id)
                            continue

                        try:
                            valid_to = datetime.strptime(valid_to_str, "%Y-%m-%d %H:%M:%S")
                        except Exception as e:
                            print(f"[SCANNER] ❌ Failed to parse time for Signal {sig.id}: {e}")
                            last_checked_id = max(last_checked_id, sig.id)
                            continue

                        now = datetime.utcnow()
                        if now >= valid_to:
                            exists = session.query(SignalPerformance).filter_by(signal_id=sig.id).first()
                            
                            if not exists:
                                perf = SignalPerformance(
                                    signal_id=sig.id,
                                    status="PENDING",
                                    tracked_at=now
                                )
                                session.add(perf)
                                session.commit()
                                print(f"[SCANNER] 🟢 Signal {sig.id} ({sig.symbol}) marked as PENDING")
                                processed_count += 1
                            else:
                                print(f"[SCANNER] ℹ️  Signal {sig.id} already tracked")
                            
                            last_checked_id = max(last_checked_id, sig.id)
                        else:
                            time_remaining = (valid_to - now).total_seconds() / 60
                            print(f"[SCANNER] ⏳ Signal {sig.id} expires in {time_remaining:.1f} mins")

                    if processed_count > 0:
                        save_last_checked_id(STATE_FILE_SCANNER, last_checked_id)
                        print(f"[SCANNER] Saved state: {last_checked_id}\n")
                else:
                    print(f"[SCANNER] No new signals to check\n")

        except Exception as e:
            print(f"[SCANNER] ❌ Error: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(CHECK_INTERVAL)

def process_pending_signals():
    """
    Phase 2: Process PENDING signals and post to Twitter
    """
    print(f"[{datetime.utcnow()}] ⚙️  Processor thread started\n")
    last_processed_id = load_last_checked_id(STATE_FILE_PROCESSOR)
    print(f"[PROCESSOR] Loaded last_processed_id: {last_processed_id}\n")

    while True:
        try:
            print(f"[PROCESSOR] [LOOP] Checking at {datetime.utcnow()}")
            with get_session_context() as session:
                total_pending = session.query(SignalPerformance).filter(
                    SignalPerformance.status == "PENDING",
                    SignalPerformance.id > last_processed_id
                ).count()
                print(f"[PROCESSOR] Found {total_pending} PENDING signals")
                
                pending_perfs = session.query(SignalPerformance)\
                    .filter_by(status="PENDING")\
                    .filter(SignalPerformance.id > last_processed_id)\
                    .order_by(SignalPerformance.id.asc())\
                    .limit(5)\
                    .all()

                if pending_perfs:
                    print(f"[PROCESSOR] Processing {len(pending_perfs)} signal(s)...\n")

                    for perf in pending_perfs:
                        try:
                            signal_id = perf.signal_id
                            perf_id = perf.id
                            
                            perf.status = "RUNNING"
                            session.commit()
                            print(f"[PROCESSOR] 📊 Processing Signal {signal_id} (Perf ID {perf_id})...")

                            thread = Thread(
                                target=process_signal_thread,
                                args=(signal_id, perf_id),
                                daemon=True
                            )
                            thread.start()

                            last_processed_id = max(last_processed_id, perf.id)

                        except Exception as e:
                            print(f"[PROCESSOR] ❌ Error with Perf ID {perf.id}: {e}")
                            last_processed_id = max(last_processed_id, perf.id)

                    save_last_checked_id(STATE_FILE_PROCESSOR, last_processed_id)
                    print(f"[PROCESSOR] Saved state: {last_processed_id}\n")
                else:
                    print(f"[PROCESSOR] No PENDING signals\n")

        except Exception as e:
            print(f"[PROCESSOR] ❌ Error: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    print(f"[{datetime.utcnow()}] 🚀 Starting Performance Monitor with Twitter Integration...\n")
    print("=" * 80)
    print("TWITTER SERVICE STATUS:", "✅ READY" if twitter_service else "❌ DISABLED")
    print("=" * 80 + "\n")

    scanner_thread = Thread(target=scan_and_add_expired_signals, daemon=False)
    scanner_thread.start()

    processor_thread = Thread(target=process_pending_signals, daemon=False)
    processor_thread.start()

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