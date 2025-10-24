#algo/backtesting/live_tracker_runner.py
import sys
import json
from algo.backtesting.live_tracker import monitor_live_signal

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("No signal data passed.")
        sys.exit(1)

    signal_info = json.loads(sys.argv[1])
    symbol = signal_info["symbol"]
    print(f"[LIVE TRACKER RUNNER] Starting tracker for {symbol}")
    monitor_live_signal(symbol, signal_info)
