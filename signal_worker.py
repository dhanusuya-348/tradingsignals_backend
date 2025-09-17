# signal_worker.py
import time
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from models import get_session, Watchlist, Signal, UserSignal
from algo.runner import generate_live_signal_api   # <<— use runner
from aws_helpers import send_to_sqs_instant, send_to_sqs_pdf

POLL_INTERVAL = 30  # seconds between checks
DEFAULT_TIMEFRAME = "1h"  # adjust if you support multiple


def process_watchlist():
    session = get_session()
    try:
        # get all unique symbols users are watching
        rows = session.query(Watchlist.symbol).distinct().all()
        symbols = [r.symbol for r in rows]

        for symbol in symbols:
            try:
                # 1. Run algo ONCE per symbol
                signal_data = generate_live_signal_api(symbol, DEFAULT_TIMEFRAME)
                # runner returns key "signal" (BUY/SELL/HOLD)
                if not signal_data or signal_data.get("signal") == "HOLD":
                    continue

                created_at = datetime.utcnow().replace(second=0, microsecond=0)

                # 2. Store or reuse existing Signal
                signal = Signal(
                    symbol=symbol,
                    timeframe=DEFAULT_TIMEFRAME,
                    payload=signal_data,
                    created_at=created_at
                )
                session.add(signal)
                try:
                    session.commit()
                    print(f"✅ New Signal created for {symbol} at {created_at}")
                except IntegrityError:
                    # Already exists, fetch it
                    session.rollback()
                    signal = session.query(Signal).filter_by(
                        symbol=symbol,
                        timeframe=DEFAULT_TIMEFRAME,
                        created_at=created_at
                    ).first()
                    print(f"♻️ Reusing existing Signal for {symbol} at {created_at}")

                # 3. Link all users watching this symbol
                watchlist_users = session.query(Watchlist).filter_by(symbol=symbol).all()
                for w in watchlist_users:
                    exists = session.query(UserSignal).filter_by(
                        user_sub=w.user_sub,
                        signal_id=signal.id
                    ).first()
                    if not exists:
                        us = UserSignal(
                            user_sub=w.user_sub,
                            email=w.email,   # store email for SES
                            signal_id=signal.id,
                            delivery_status="pending"
                        )
                        # copy phone if model has it
                        if hasattr(us, "phone") and hasattr(w, "phone"):
                            setattr(us, "phone", getattr(w, "phone"))
                        session.add(us)
                        session.commit()

                        # enqueue INSTANT notification per user (includes email and phone)
                        send_to_sqs_instant({
                            "user_sub": w.user_sub,
                            "email": w.email,
                            "phone": getattr(w, "phone", None),
                            "symbol": symbol,
                            "signal_id": signal.id,
                            "signal": signal.payload
                        })
                        print(f"📩 Instant signal queued for {w.user_sub} ({w.email}) on {symbol}")

                # 4. Enqueue ONE PDF job (only if not already generated)
                if not signal.pdf_url:
                    send_to_sqs_pdf({
                        "signal_id": signal.id,
                        "symbol": symbol,
                        "timeframe": DEFAULT_TIMEFRAME
                    })
                    print(f"📝 PDF job queued for {symbol} at {created_at}")

            except Exception as e:
                print(f"⚠️ Error processing {symbol}: {e}")

    finally:
        session.close()


if __name__ == "__main__":
    while True:
        process_watchlist()
        time.sleep(POLL_INTERVAL)
