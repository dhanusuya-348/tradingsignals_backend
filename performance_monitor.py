# performance_monitor.py
import sys
import os
import time
from datetime import datetime
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from load_env import load_env_file
    load_env_file()
except ImportError:
    pass

from models import get_session_context, Signal
from algo.backtesting.live_tracker import monitor_live_signal

def log(msg: str):
    """Print log messages with UTC timestamp."""
    print(f"[{datetime.utcnow()}] {msg}", flush=True)

def monitor_pending_signals():
    """
    24/7 daemon that picks up signals with processed=False
    and monitors them one at a time.
    """
    log("Performance Monitor started. Listening for pending signals...")
    
    while True:
        try:
            with get_session_context() as session:
                # Find ONE signal that needs monitoring
                pending_signal = session.query(Signal).filter_by(
                    processed=False
                ).order_by(Signal.created_at.desc()).first()
                
                if not pending_signal:
                    # No pending signals, sleep and check again
                    time.sleep(30)  # Check every 30 seconds
                    continue
                
                log(f"📊 Starting monitoring for Signal {pending_signal.id} ({pending_signal.symbol})")
                
                # Extract signal info from payload
                signal_info = pending_signal.payload.copy() if pending_signal.payload else {}
                signal_info["id"] = pending_signal.id
                signal_info["symbol"] = pending_signal.symbol
                
                try:
                    # Run the monitoring (blocks until done - could be 3 hours!)
                    monitor_live_signal(
                        pending_signal.symbol, 
                        signal_info
                    )
                    
                    log(f"✅ Monitoring completed for Signal {pending_signal.id}")
                    
                except Exception as monitor_err:
                    log(f"❌ Monitoring failed for Signal {pending_signal.id}: {monitor_err}")
                    traceback.print_exc()
                
        except Exception as e:
            log(f"⚠️ Error in monitoring loop: {e}")
            traceback.print_exc()
            time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    monitor_pending_signals()