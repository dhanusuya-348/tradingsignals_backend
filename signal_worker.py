#signal_worker.py - backend
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

# Import models, algo, and notifications
try:
    from models import get_session, Watchlist, Signal, UserSignal, get_session_context
    from algo.runner import generate_live_signal_api
    from notifications import send_email, format_signal_email  # <== NEW IMPORT
    print(f"[{datetime.utcnow()}] All imports successful")
except Exception as e:
    print(f"[{datetime.utcnow()}] Import error: {e}")
    print(traceback.format_exc())
    raise  # fail fast

DEFAULT_TIMEFRAME = "30m"

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
def process_all_coins():
    """Run the algo for all supported coins, insert signals into DB, send notifications, mark processed."""
    all_coins = [
        "BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "TRX", "AVAX", "LINK",
        "DOT", "BCH", "LTC", "MATIC", "SHIB", "XLM", "UNI", "ETC", "XMR",
        "NEAR", "ICP"
    ]

    with get_session_context() as session:
        for symbol in all_coins:
            try:
                print(f"[{datetime.utcnow()}] Running algorithm for {symbol}...")
                signal_data = with_retries(generate_live_signal_api, 2, 5, symbol)

                if not signal_data:
                    print(f"[{datetime.utcnow()}] ⚠ No signal data for {symbol}, skipping...")
                    continue

                sig_type = signal_data.get("signal", "HOLD")

                # Only store BUY or SELL signals
                if sig_type not in ["BUY", "SELL"]:
                    print(f"[{datetime.utcnow()}] ⚠ Signal is HOLD for {symbol}, skipping storage")
                    continue

                # JSON-serializable payload
                signal_payload = json.loads(json.dumps(signal_data, default=str))

                # Round created_at to nearest 30-minute mark
                now = datetime.utcnow()
                minute = (now.minute // 30) * 30
                created_at = now.replace(minute=minute, second=0, microsecond=0)

                # Check if signal already exists
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
                        created_at=created_at,
                        processed=False
                    )
                    session.add(signal)
                    session.commit()
                    print(f"[{datetime.utcnow()}] New {sig_type} Signal created for {symbol} at {created_at}")
                else:
                    print(f"[{datetime.utcnow()}] Reusing existing Signal for {symbol} at {created_at}")

                # Link users who have this coin in watchlist
                watchlist_users = session.query(Watchlist).filter_by(symbol=symbol).all()
                print(f"[{datetime.utcnow()}] Found {len(watchlist_users)} users watching {symbol}")

                all_success = True
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

                        # Build HTML email
                        subject = f"New {sig_type} Signal for {symbol} ({signal_data.get('confidence', 0)}% Confidence)"
                        body_html = format_signal_email(signal_data)
                        body_text = f"Signal for {symbol}: {sig_type}\n\nConfidence: {signal_data.get('confidence', 0)}%\nSentiment: {signal_data.get('sentiment', 'N/A')}"

                        # Send email
                        success = send_email(
                            to_email=w.email,
                            subject=subject,
                            body_text=body_text,
                            body_html=body_html
                        )

                        # Update delivery status
                        us.delivery_status = "sent" if success else "failed"
                        session.commit()

                        if not success:
                            all_success = False

                # If all emails sent successfully, mark signal as processed
                if all_success:
                    signal.processed = True
                    session.commit()
                    print(f"[{datetime.utcnow()}] Signal {symbol} at {created_at} marked as processed")

                
            except Exception as e:
                print(f"[{datetime.utcnow()}] Error processing {symbol}: {e}")
                print(traceback.format_exc())
                session.rollback()


def run_signal_cycle():
    print(f"\n[{datetime.utcnow()}] === Starting signal cycle ===")
    process_all_coins()
    print(f"[{datetime.utcnow()}] === Signal cycle completed ===\n")


if __name__ == "__main__":
    run_signal_cycle()


