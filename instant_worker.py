# instant_worker.py
import time
import json
import os
import boto3
from models import get_session, Signal, UserSignal
from aws_helpers import send_email_via_ses, publish_sms

region = os.environ.get("AWS_REGION", "us-east-1")
sqs = boto3.client("sqs", region_name=region)

INSTANT_QUEUE_URL = os.environ.get("INSTANT_QUEUE_URL")
POLL_INTERVAL = 10  # seconds


def process_instant_jobs():
    if not INSTANT_QUEUE_URL:
        raise RuntimeError("❌ INSTANT_QUEUE_URL not set")

    while True:
        resp = sqs.receive_message(
            QueueUrl=INSTANT_QUEUE_URL,
            MaxNumberOfMessages=5,
            WaitTimeSeconds=10
        )

        messages = resp.get("Messages", [])
        if not messages:
            time.sleep(POLL_INTERVAL)
            continue

        for msg in messages:
            try:
                body = json.loads(msg["Body"])
                signal_id = body.get("signal_id")
                user_sub = body.get("user_sub")
                email = body.get("email")
                phone = body.get("phone")  # optional
                symbol = body.get("symbol")

                if not signal_id or not email:
                    print(f"⚠️ Missing fields in message: {body}")
                    sqs.delete_message(QueueUrl=INSTANT_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
                    continue

                session = get_session()
                signal = session.query(Signal).get(signal_id)
                if not signal:
                    print(f"⚠️ No signal found for id={signal_id}")
                    session.close()
                    sqs.delete_message(QueueUrl=INSTANT_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
                    continue

                # --- Compose notification ---
                subject = f"🚨 Live Trading Signal - {symbol}"
                body_html = f"""
                <h3>New Trading Signal Detected</h3>
                <p><b>Symbol:</b> {symbol}</p>
                <p><b>Signal:</b> {signal.payload.get('signal')}</p>
                <p><b>Confidence:</b> {signal.payload.get('confidence')}%</p>
                <p>Time: {signal.created_at}</p>
                """

                # --- Send email ---
                send_email_via_ses(subject, email, body_html)

                # --- Send SMS (optional, only if phone is present) ---
                if phone:
                    sms_message = f"[{symbol}] Signal: {signal.payload.get('signal')} | Confidence: {signal.payload.get('confidence')}%"
                    publish_sms(sms_message, phone)

                # Mark as delivered in DB (user_signals)
                us = session.query(UserSignal).filter_by(user_sub=user_sub, signal_id=signal.id).first()
                if us:
                    us.delivery_status = "sent"
                    session.commit()

                session.close()
                print(f"📩 Instant signal sent to {email} (signal_id={signal_id})")

            except Exception as e:
                print(f"❌ Error processing instant job: {e}")

            # Always delete the message to avoid re-processing
            sqs.delete_message(QueueUrl=INSTANT_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])


if __name__ == "__main__":
    print("🚀 Starting Instant worker...")
    process_instant_jobs()
