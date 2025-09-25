# pdf_worker.py
import time
import json
import os
import boto3
from datetime import datetime
from models import get_session_context, Signal, UserSignal
from algo.runner import generate_pdf_report_full
from aws_helpers import upload_pdf_to_s3, send_email_via_ses
import traceback

region = os.environ.get("AWS_REGION", "us-east-1")
sqs = boto3.client("sqs", region_name=region)

PDF_QUEUE_URL = os.environ.get("PDF_QUEUE_URL")
POLL_INTERVAL = 15  # seconds


def process_pdf_jobs_once():
    """Process messages in PDF SQS queue once"""
    if not PDF_QUEUE_URL:
        raise RuntimeError("PDF_QUEUE_URL not set")

    resp = sqs.receive_message(
        QueueUrl=PDF_QUEUE_URL,
        MaxNumberOfMessages=5,
        WaitTimeSeconds=10
    )

    messages = resp.get("Messages", [])
    if not messages:
        print(f"{datetime.utcnow()} - No PDF jobs found")
        return

    for msg in messages:
        try:
            body = json.loads(msg["Body"])
            signal_id = body.get("signal_id")
            if not signal_id:
                print(f"{datetime.utcnow()} - Missing signal_id in message")
                sqs.delete_message(QueueUrl=PDF_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
                continue

            with get_session_context() as session:
                signal = session.query(Signal).get(signal_id)
                if not signal:
                    print(f"{datetime.utcnow()} - No signal found for id={signal_id}")
                    sqs.delete_message(QueueUrl=PDF_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
                    continue

                # 1. Generate PDF if not exists
                if signal.pdf_url:
                    pdf_url = signal.pdf_url
                    print(f"{datetime.utcnow()} - Reusing existing PDF for signal {signal_id}")
                else:
                    result = generate_pdf_report_full(signal.symbol, signal.timeframe)
                    pdf_path = result.get("pdf_path")
                    if not pdf_path:
                        print(f"{datetime.utcnow()} - Runner didn't return a pdf_path for signal {signal_id}")
                        continue

                    s3_key = f"reports/signal_{signal_id}_{os.path.basename(pdf_path)}"
                    pdf_url = upload_pdf_to_s3(pdf_path, s3_key)

                    signal.pdf_url = pdf_url
                    session.commit()
                    print(f"{datetime.utcnow()} - PDF generated & uploaded for signal {signal_id}: {pdf_url}")

                # 2. Notify pending users
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
                        send_email_via_ses(subject, u.email, body_html)
                        u.delivery_status = "sent"
                        session.commit()
                        print(f"{datetime.utcnow()} - PDF sent to {u.email} for signal {signal_id}")
                    except Exception as e:
                        print(f"{datetime.utcnow()} - Email failed for {u.email}: {e}")
                        u.delivery_status = "failed"
                        session.commit()

        except Exception as e:
            print(f"{datetime.utcnow()} - Error processing PDF job: {e}")
            print(traceback.format_exc())

        finally:
            # Always delete message to avoid re-processing
            try:
                sqs.delete_message(QueueUrl=PDF_QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
            except Exception as e:
                print(f"{datetime.utcnow()} - Failed to delete SQS message: {e}")


def run_worker_loop():
    """Standalone loop mode (optional)"""
    print(f"{datetime.utcnow()} - Starting PDF worker loop...")
    while True:
        try:
            process_pdf_jobs_once()
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print(f"{datetime.utcnow()} - PDF worker stopped by user")
            break
        except Exception as e:
            print(f"{datetime.utcnow()} - Worker loop error: {e}")
            print(traceback.format_exc())
            time.sleep(30)


if __name__ == "__main__":
    # Use loop mode for local testing
    run_worker_loop()
