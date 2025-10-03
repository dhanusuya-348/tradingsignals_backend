#scheduler.py
import time
import subprocess
from datetime import datetime, timedelta
import traceback
import sys
import signal

def log(msg: str):
    print(f"[{datetime.utcnow()}] {msg}", flush=True)

def run_worker():
    """Spawn signal_worker.py once as a child process."""
    log("Launching signal_worker.py...")
    try:
        result = subprocess.run(
            [sys.executable, "signal_worker.py"],  # safer, uses same Python
            capture_output=True,
            text=True
        )
        log(f"Return code: {result.returncode}")
        if result.stdout:
            log(f"--- STDOUT ---\n{result.stdout}")
        if result.stderr:
            log(f"--- STDERR ---\n{result.stderr}")
    except Exception as e:
        log(f"Failed to run signal_worker.py: {e}")
        log(traceback.format_exc())

def wait_until_next_cycle(interval_minutes=10):
    """Sleep for interval_minutes."""
    log(f"Sleeping {interval_minutes} minutes until next cycle...")
    time.sleep(interval_minutes * 60)

def shutdown_handler(signum, frame):
    log(f"Scheduler received signal {signum}, exiting gracefully...")
    exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    log("Scheduler started. Will trigger signal_worker.py every 10 minutes.")
    try:
        while True:
            run_worker()
            wait_until_next_cycle(10)  # 10-minute interval
    except Exception as e:
        log(f"Unexpected error in scheduler loop: {e}")
        log(traceback.format_exc())
