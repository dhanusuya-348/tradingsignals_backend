# signal_worker.py
import sys
import os
from datetime import datetime
from sqlalchemy.exc import IntegrityError
import traceback

# --- Fix Python path so EB can find algo + models ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables if available
try:
    from load_env import load_env_file
    load_env_file()
    print("✅ Loaded .env file")
except ImportError:
    print("ℹ️ load_env.py not found, using system environment variables")

# Import models and helpers (fail fast if broken)
try:
    from models import get_session, Watchlist, Signal, UserSignal
    from algo.runner import generate_live_signal_api
    from aws_helpers import send_to_sqs_instant, send_to_sqs_pdf
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import error: {e}")
    print(traceback.format_exc())
    raise  # fail fast

DEFAULT_TIMEFRAME = "1h"  # adjust if you support multiple

def process_watchlist():
    """Run the algo for all symbols in watchlist and queue signals."""
    session = get_session()
    try:
        # get all unique symbols users are watching
        rows = session.query(Watchlist.symbol).distinct().all()
        symbols = [r.symbol for r in rows]

        print(f"📊 Found symbols in watchlist: {symbols}")

        for symbol in symbols:
            try:
                print(f"⚡ Running algorithm for {symbol}...")

                # Run algo once per symbol
                signal_data = generate_live_signal_api(symbol, DEFAULT_TIMEFRAME)
                if not signal_data or signal_data.get("signal") == "HOLD":
                    print(f"⏸ {symbol}: HOLD signal, skipping...")
                    continue

                created_at = datetime.utcnow().replace(second=0, microsecond=0)

                # Upsert Signal
                signal = session.query(Signal).filter_by(
                    symbol=symbol,
                    timeframe=DEFAULT_TIMEFRAME,
                    created_at=created_at
                ).first()

                if not signal:
                    signal = Signal(
                        symbol=symbol,
                        timeframe=DEFAULT_TIMEFRAME,
                        payload=signal_data,
                        created_at=created_at
                    )
                    session.add(signal)
                    session.commit()
                    print(f"🆕 New Signal created for {symbol} at {created_at}")
                else:
                    print(f"♻️ Reusing existing Signal for {symbol} at {created_at}")

                # Link all users watching this symbol
                watchlist_users = session.query(Watchlist).filter_by(symbol=symbol).all()
                print(f"👥 Found {len(watchlist_users)} users watching {symbol}")

                new_user_signals = []
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
                            delivery_status="pending",
                            phone=getattr(w, "phone", None)
                        )
                        session.add(us)
                        new_user_signals.append({
                            "user_sub": w.user_sub,
                            "email": w.email,
                            "phone": getattr(w, "phone", None)
                        })

                # Commit all new user signals at once
                if new_user_signals:
                    session.commit()
                    for u in new_user_signals:
                        send_to_sqs_instant({
                            "user_sub": u["user_sub"],
                            "email": u["email"],
                            "phone": u["phone"],
                            "symbol": symbol,
                            "signal_id": signal.id,
                            "signal": signal.payload
                        })
                        print(f"📩 Instant signal queued for {u['user_sub']} ({u['email']}) on {symbol}")

                # Enqueue ONE PDF job (only if not already generated)
                if not signal.pdf_url:
                    send_to_sqs_pdf({
                        "signal_id": signal.id,
                        "symbol": symbol,
                        "timeframe": DEFAULT_TIMEFRAME
                    })
                    print(f"📑 PDF job queued for {symbol} at {created_at}")

            except Exception as e:
                print(f"❌ Error processing {symbol}: {e}")
                print(traceback.format_exc())
                session.rollback()

    except Exception as e:
        print(f"❌ Error in process_watchlist: {e}")
        print(traceback.format_exc())
    finally:
        session.close()
        print("✅ Database session closed")

def run_signal_cycle():
    """One full run triggered by cron or endpoint"""
    print(f"\n=== 🚀 Starting signal cycle at {datetime.utcnow()} ===")
    process_watchlist()
    print(f"=== ✅ Signal cycle completed at {datetime.utcnow()} ===")

if __name__ == "__main__":
    run_signal_cycle()
