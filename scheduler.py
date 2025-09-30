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

def wait_until_next_hour():
    """Sleep until the start of the next UTC hour."""
    now = datetime.utcnow()
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    delta = (next_hour - now).total_seconds()
    log(f"Sleeping {int(delta)} seconds until next UTC hour ({next_hour})...")
    time.sleep(delta)

def shutdown_handler(signum, frame):
    log(f"Scheduler received signal {signum}, exiting gracefully...")
    exit(0)

if __name__ == "__main__":
    # Handle termination signals (EB worker stop/restart)
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    log("Scheduler started. Will trigger signal_worker.py at the start of each UTC hour.")
    try:
        while True:
            run_worker()
            wait_until_next_hour()
    except Exception as e:
        log(f"Unexpected error in scheduler loop: {e}")
        log(traceback.format_exc())