# pdf_worker.py
import time
import json
import os
import boto3
from datetime import datetime
from models import get_session, Signal, UserSignal
from algo.runner import generate_pdf_report_full   # <-- use runner to generate full report
from aws_helpers import upload_pdf_to_s3, send_email_via_ses

region = os.environ.get("AWS_REGION", "us-east-1")
sqs = boto3.client("sqs", region_name=region)

PDF_QUEUE_URL = os.environ.get("PDF_QUEUE_URL")

POLL_INTERVAL = 15  # seconds


def process_pdf_jobs():
    if not PDF_QUEUE_URL:
        raise RuntimeError("❌ PDF_QUEUE_URL not set")

    while True:
        resp = sqs.receive_message(
            QueueUrl=PDF_QUEUE_URL,
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
                if not signal_id:
                    print("⚠️ Missing signal_id in message")
                    sqs.delete_message(QueueUrl=PDF_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
                    continue

                session = get_session()
                signal = session.query(Signal).get(signal_id)
                if not signal:
                    print(f"⚠️ No signal found for id={signal_id}")
                    session.close()
                    sqs.delete_message(QueueUrl=PDF_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
                    continue

                # 1. If PDF already exists → reuse it
                if signal.pdf_url:
                    pdf_url = signal.pdf_url
                    print(f"♻️ Reusing existing PDF for signal {signal_id}")
                else:
                    # Generate full report (uses your runner which creates pdf and returns path)
                    result = generate_pdf_report_full(signal.symbol, signal.timeframe)
                    pdf_path = result.get("pdf_path")
                    if not pdf_path:
                        print(f"❌ Runner didn't return a pdf_path for signal {signal_id}")
                        session.close()
                        sqs.delete_message(QueueUrl=PDF_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
                        continue

                    # upload to s3
                    s3_key = f"reports/signal_{signal_id}_{os.path.basename(pdf_path)}"
                    pdf_url = upload_pdf_to_s3(pdf_path, s3_key)

                    # Save URL in DB
                    signal.pdf_url = pdf_url
                    session.commit()
                    print(f"✅ PDF generated & uploaded for signal {signal_id}: {pdf_url}")

                # 2. Notify all users linked to this signal (pending only)
                users = session.query(UserSignal).filter_by(signal_id=signal.id, delivery_status="pending").all()
                for u in users:
                    try:
                        subject = f"Trading Signal Report - {signal.symbol}"
                        body_html = f"""
                        <h3>Trading Signal for {signal.symbol}</h3>
                        <p>Signal: {signal.payload.get('signal')}</p>
                        <p>Confidence: {signal.payload.get('confidence')}%</p>
                        <p>Download full report: <a href="{pdf_url}">{pdf_url}</a></p>
                        """
                        # use the email field
                        send_email_via_ses(subject, u.email, body_html)
                        u.delivery_status = "sent"
                        session.commit()
                        print(f"📩 PDF sent to {u.email} for signal {signal_id}")
                    except Exception as e:
                        print(f"⚠️ Email failed for {u.email}: {e}")
                        u.delivery_status = "failed"
                        session.commit()

                session.close()

            except Exception as e:
                print(f"❌ Error processing PDF job: {e}")

            # Delete message from queue after processing
            sqs.delete_message(QueueUrl=PDF_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])


if __name__ == "__main__":
    print("🚀 Starting PDF worker...")
    process_pdf_jobs()
