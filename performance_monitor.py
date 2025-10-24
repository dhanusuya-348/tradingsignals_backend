#performance_monitor.py
import sys, os, time, traceback
from datetime import datetime
from threading import Thread

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import get_session_context, Signal, SignalPerformance
from algo.backtesting.live_tracker import monitor_live_signal

def log(msg: str):
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def process_signal_thread(sig):
    """Runs performance check for a completed signal."""
    try:
        monitor_live_signal(sig.symbol, sig.payload)
        log(f"✅ Completed performance evaluation for Signal {sig.id}")
    except Exception as e:
        log(f"❌ Error evaluating Signal {sig.id}: {e}")
        traceback.print_exc()

def monitor_pending_signals():
    log("📊 Performance Monitor started (post-signal evaluation mode)...")
    active_threads = {}

    while True:
        try:
            now = datetime.utcnow()

            with get_session_context() as session:
                # Fetch signals that either:
                # 1. Have no performance record, OR
                # 2. Have performance with 'PENDING' status
                pending_signals = (
                    session.query(Signal)
                    .outerjoin(SignalPerformance)
                    .filter(
                        (SignalPerformance.id == None) |
                        (SignalPerformance.status == "PENDING")
                    )
                    .all()
                )

                for sig in pending_signals:
                    payload = sig.payload or {}
                    timing = payload.get("timing", {})
                    valid_to_str = timing.get("end")

                    if not valid_to_str:
                        continue

                    # Try parsing valid_to safely
                    try:
                        valid_to = datetime.strptime(valid_to_str, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        continue

                    # If signal has reached its valid_to time → queue for evaluation
                    if now >= valid_to:
                        if sig.id not in active_threads or not active_threads[sig.id].is_alive():
                            t = Thread(target=process_signal_thread, args=(sig,))
                            t.daemon = True  # ensures thread closes cleanly with process
                            t.start()
                            active_threads[sig.id] = t
                            log(f"🧩 Queued Signal {sig.id} ({sig.symbol}) for performance evaluation")

            # Cleanup finished threads
            finished = [sid for sid, t in active_threads.items() if not t.is_alive()]
            for sid in finished:
                del active_threads[sid]

            time.sleep(60)  # check every 1 minute

        except Exception as e:
            log(f"⚠️ Monitor error: {e}")
            traceback.print_exc()
            time.sleep(60)

if __name__ == "__main__":
    monitor_pending_signals()
