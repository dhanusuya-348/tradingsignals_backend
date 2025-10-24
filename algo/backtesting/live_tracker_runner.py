#algo/backtesting/live_tracker_runner.py
import sys
import json
import os

# Add parent dirs to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from algo.backtesting.live_tracker import monitor_live_signal

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("No signal data passed.")
        sys.exit(1)

    try:
        signal_info = json.loads(sys.argv[1])
        symbol = signal_info["symbol"]
        print(f"[LIVE TRACKER RUNNER] Starting tracker for {symbol}", flush=True)
        monitor_live_signal(symbol, signal_info)
        print(f"[LIVE TRACKER RUNNER] Completed for {symbol}", flush=True)
    except Exception as e:
        print(f"[LIVE TRACKER RUNNER ERROR] {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)