#performance_monitor.py
import time
from datetime import datetime
from threading import Thread

# Load .env variables for local testing
try:
    from load_env import load_env_file
    load_env_file()
    print(f"[{datetime.utcnow()}] ✅ Loaded .env variables")
except ImportError:
    print(f"[{datetime.utcnow()}] ⚠ load_env.py not found, using system environment variables")

from models import get_session_context, Signal, SignalPerformance
from algo.backtesting.live_tracker import monitor_live_signal

# --- CONFIG ---
START_DATE = datetime(2025, 10, 25)  # Only consider signals after this date
CHECK_INTERVAL = 60  # Seconds between checking for new signals
STATE_FILE = "/tmp/perfmon_last_id.txt"

def load_last_checked_id():
    try:
        with open(STATE_FILE, "r") as f:
            return int(f.read().strip())
    except:
        return 0

def save_last_checked_id(last_id):
    with open(STATE_FILE, "w") as f:
        f.write(str(last_id))

def process_signal_thread(signal_obj):
    """
    Thread to monitor a single signal in real-time using live_tracker.py
    """
    try:
        monitor_live_signal(signal_obj.symbol, signal_obj.payload)
    except Exception as e:
        print(f"[ERROR] Exception while processing signal {signal_obj.id}: {e}")

def add_new_signals():
    """
    Continuously monitors signals table and adds new entries to signal_performance
    for signals whose payload['timing']['end'] has passed and are not already tracked.
    """
    last_checked_id = load_last_checked_id()

    while True:
        try:
            with get_session_context() as session:
                # Fetch new signals after last_checked_id and START_DATE
                new_signals = session.query(Signal)\
                    .filter(Signal.id > last_checked_id)\
                    .filter(Signal.created_at >= START_DATE)\
                    .order_by(Signal.id.asc())\
                    .all()

                if new_signals:
                    print(f"[INFO] Found {len(new_signals)} new signal(s) to track")

                for sig in new_signals:
                    payload = sig.payload or {}
                    timing = payload.get("timing", {})
                    valid_to_str = timing.get("end")

                    if not valid_to_str:
                        print(f"[WARN] Signal ID {sig.id} has no timing end, skipping")
                        continue

                    valid_to = datetime.strptime(valid_to_str, "%Y-%m-%d %H:%M:%S")

                    # Only process if valid_to has passed
                    if datetime.utcnow() < valid_to:
                        print(f"[INFO] Signal ID {sig.id} not finished yet, skipping")
                        continue

                    # Skip if already tracked
                    exists = session.query(SignalPerformance).filter_by(signal_id=sig.id).first()
                    if exists:
                        print(f"[INFO] Signal {sig.id} already in performance table, skipping")
                        continue

                    # Add to SignalPerformance with status RUNNING
                    perf = SignalPerformance(
                        signal_id=sig.id,
                        status="RUNNING",
                        tracked_at=datetime.utcnow()
                    )
                    session.add(perf)
                    session.commit()
                    print(f"🟢 Signal {sig.id} added to SignalPerformance (ID {perf.id})")

                    # Start monitoring thread
                    thread = Thread(target=process_signal_thread, args=(sig,))
                    thread.start()

                    last_checked_id = max(last_checked_id, sig.id)
                    save_last_checked_id(last_checked_id)

        except Exception as e:
            print(f"[ERROR] Failed to fetch/add new signals: {e}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    print(f"[{datetime.utcnow()}] 🚀 Starting Performance Monitor...")
    add_new_signals()
