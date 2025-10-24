import sys, os, time, traceback
from datetime import datetime
from threading import Thread

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from load_env import load_env_file
    load_env_file()
except ImportError:
    pass

from models import get_session_context, Signal, SignalPerformance
from algo.backtesting.live_tracker import monitor_live_signal

def log(msg: str):
    print(f"[{datetime.utcnow()}] {msg}", flush=True)

def monitor_signal_thread(signal_id, symbol, signal_info):
    """Run monitor_live_signal in a separate thread."""
    try:
        monitor_live_signal(symbol, signal_info)
        log(f"✅ Monitoring completed for Signal {signal_id}")
    except Exception as e:
        log(f"❌ Monitoring failed for Signal {signal_id}: {e}")
        traceback.print_exc()

def monitor_pending_signals():
    log("Performance Monitor started. Listening for pending signals...")

    active_threads = {}

    while True:
        try:
            with get_session_context() as session:
                pending_signals = session.query(Signal).outerjoin(SignalPerformance).filter(SignalPerformance.id == None).all()

                for sig in pending_signals:
                    if sig.id in active_threads and active_threads[sig.id].is_alive():
                        # Already monitoring this signal
                        continue

                    signal_info = sig.payload.copy() if sig.payload else {}
                    signal_info["id"] = sig.id
                    signal_info["symbol"] = sig.symbol

                    # Start a new thread for this signal
                    thread = Thread(target=monitor_signal_thread, args=(sig.id, sig.symbol, signal_info))
                    thread.start()
                    active_threads[sig.id] = thread
                    log(f"📊 Started monitoring for Signal {sig.id} ({sig.symbol}) in a new thread")

            # Cleanup finished threads
            to_remove = [k for k, t in active_threads.items() if not t.is_alive()]
            for k in to_remove:
                del active_threads[k]

            time.sleep(30)  # Check every 30 seconds

        except Exception as e:
            log(f"⚠️ Error in monitoring loop: {e}")
            traceback.print_exc()
            time.sleep(60)

if __name__ == "__main__":
    monitor_pending_signals()
