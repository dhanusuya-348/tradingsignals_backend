# signal_worker.py
import sys
import os
import time
from datetime import datetime
import traceback
import json

sys.stdout.reconfigure(line_buffering=True)  # forces prints to flush immediately

# --- Fix Python path so EB can find algo + models ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables if available
try:
    from load_env import load_env_file
    load_env_file()
    print(f"[{datetime.utcnow()}] Loaded .env file")
except ImportError:
    print(f"[{datetime.utcnow()}] load_env.py not found, using system environment variables")

# Import models and algo
try:
    from models import get_session, Watchlist, Signal, UserSignal, get_session_context
    from algo.runner import generate_live_signal_api
    print(f"[{datetime.utcnow()}] All imports successful")
except Exception as e:
    print(f"[{datetime.utcnow()}] Import error: {e}")
    print(traceback.format_exc())
    raise  # fail fast

DEFAULT_TIMEFRAME = "10m"

# ---------------- Retry Helper ----------------
def with_retries(func, max_retries=3, delay=5, *args, **kwargs):
    """Retry wrapper for transient errors."""
    for attempt in range(1, max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"[{datetime.utcnow()}] Attempt {attempt}/{max_retries} failed in {func.__name__}: {e}")
            if attempt < max_retries:
                time.sleep(delay)
            else:
                print(f"[{datetime.utcnow()}] Max retries reached for {func.__name__}")
                raise

# ---------------- Core Logic ----------------
def process_watchlist():
    """Run the algo for all symbols in watchlist and insert signals into DB."""
    with get_session_context() as session:
        try:
            rows = session.query(Watchlist.symbol).distinct().all()
            symbols = [r.symbol for r in rows]

            print(f"[{datetime.utcnow()}] Found symbols in watchlist: {symbols}")

            for symbol in symbols:
                try:
                    print(f"[{datetime.utcnow()}] Running algorithm for {symbol}...")
                    signal_data = with_retries(generate_live_signal_api, 2, 5, symbol, DEFAULT_TIMEFRAME)

                    if not signal_data:
                        print(f"[{datetime.utcnow()}] ⚠ No signal data for {symbol}, skipping...")
                        continue

                    sig_type = signal_data.get("signal", "HOLD")
                    if sig_type not in ["BUY", "SELL"]:
                        print(f"[{datetime.utcnow()}] Signal is HOLD for {symbol}, skipping DB insert...")
                        continue  # skip HOLD signals

                    # Ensure payload is JSON-serializable
                    signal_payload = json.loads(json.dumps(signal_data, default=str))
                    created_at = datetime.utcnow().replace(second=0, microsecond=0)

                    # --- Insert BUY/SELL signal ---
                    signal = session.query(Signal).filter_by(
                        symbol=symbol,
                        timeframe=DEFAULT_TIMEFRAME,
                        created_at=created_at
                    ).first()

                    if not signal:
                        signal = Signal(
                            symbol=symbol,
                            timeframe=DEFAULT_TIMEFRAME,
                            payload=signal_payload,
                            created_at=created_at
                        )
                        session.add(signal)
                        session.commit()
                        print(f"[{datetime.utcnow()}] New {sig_type} Signal created for {symbol} at {created_at}")
                    else:
                        print(f"[{datetime.utcnow()}] Reusing existing Signal for {symbol} at {created_at}")

                    # Link users (no phone references)
                    watchlist_users = session.query(Watchlist).filter_by(symbol=symbol).all()
                    print(f"[{datetime.utcnow()}] Found {len(watchlist_users)} users watching {symbol}")

                    for w in watchlist_users:
                        exists = session.query(UserSignal).filter_by(
                            user_sub=w.user_sub,
                            signal_id=signal.id
                        ).first()
                        if not exists:
                            us = UserSignal(
                                user_sub=w.user_sub,
                                email=w.email,
                                signal_id=signal.id,
                                delivery_status="pending"
                            )
                            session.add(us)

                    session.commit()

                except Exception as e:
                    print(f"[{datetime.utcnow()}] Error processing {symbol}: {e}")
                    print(traceback.format_exc())
                    session.rollback()

        except Exception as e:
            print(f"[{datetime.utcnow()}] Error in process_watchlist: {e}")
            print(traceback.format_exc())

def run_signal_cycle():
    print(f"\n[{datetime.utcnow()}] === Starting signal cycle ===")
    process_watchlist()
    print(f"[{datetime.utcnow()}] === Signal cycle completed ===\n")

if __name__ == "__main__":
    run_signal_cycle()
