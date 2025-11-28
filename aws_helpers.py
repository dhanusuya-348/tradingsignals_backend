# aws_helpers.py
import boto3
import os
import json
import time
from typing import Optional, Dict

region = os.environ.get("AWS_REGION", "ap-southeast-2")

# AWS clients
sqs = boto3.client("sqs", region_name=region)
s3 = boto3.client("s3", region_name=region)
sns = boto3.client("sns", region_name=region)
ses = boto3.client("ses", region_name=region)

# Environment variables for queue URLs and S3 bucket
INSTANT_QUEUE_URL = os.environ.get("INSTANT_QUEUE_URL")
PDF_QUEUE_URL = os.environ.get("PDF_QUEUE_URL")
S3_BUCKET = os.environ.get("PDF_S3_BUCKET")
SNS_TOPIC = os.environ.get("SNS_TOPIC_ARN")
SES_FROM = os.environ.get("SES_FROM")  # verified sender email

# -----------------------------
# SQS helpers
# -----------------------------
def send_to_sqs_instant(message: Dict) -> Optional[str]:
    """Push a message to the instant notification SQS queue and return MessageId."""
    if not INSTANT_QUEUE_URL:
        print("[WARN] INSTANT_QUEUE_URL not set")
        return None
    try:
        resp = sqs.send_message(
            QueueUrl=INSTANT_QUEUE_URL,
            MessageBody=json.dumps(message)
        )
        msg_id = resp.get("MessageId")
        print(f"[INFO] Sent instant message to SQS for {message.get('symbol')} (user: {message.get('email')}), MessageId: {msg_id}")
        return msg_id
    except Exception as e:
        print(f"[ERROR] Failed to send instant message to SQS: {e}")
        return None

def send_to_sqs_pdf(message: Dict) -> Optional[str]:
    """Push a message to the PDF generation SQS queue and return MessageId."""
    if not PDF_QUEUE_URL:
        print("[WARN] PDF_QUEUE_URL not set")
        return None
    try:
        resp = sqs.send_message(
            QueueUrl=PDF_QUEUE_URL,
            MessageBody=json.dumps(message)
        )
        msg_id = resp.get("MessageId")
        print(f"[INFO] Sent PDF job to SQS for {message.get('symbol')} (signal_id: {message.get('signal_id')}), MessageId: {msg_id}")
        return msg_id
    except Exception as e:
        print(f"[ERROR] Failed to send PDF job to SQS: {e}")
        return None

# -----------------------------
# S3 helper improvements
# -----------------------------
def upload_pdf_to_s3(local_path: str, key: Optional[str] = None, expire_seconds: int = 3600) -> str:
    """Upload a PDF to S3 and return a presigned URL (default 1 hour expiry)."""
    if not S3_BUCKET:
        raise RuntimeError("PDF_S3_BUCKET not set")
    
    if key is None:
        # auto-generate key if not provided
        base_name = os.path.basename(local_path)
        timestamp = int(time.time())
        key = f"pdfs/{timestamp}_{base_name}"
    
    try:
        s3.upload_file(local_path, S3_BUCKET, key)
        print(f"[INFO] Uploaded PDF to S3: {key}")
        
        # Generate presigned URL
        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': S3_BUCKET, 'Key': key},
            ExpiresIn=expire_seconds
        )
        print(f"[INFO] Presigned URL: {url}")
        return url
    except Exception as e:
        print(f"[ERROR] Failed to upload PDF to S3: {e}")
        raise

# -----------------------------
# SNS / SES helpers
# -----------------------------
def publish_sms(message: str, phone_number: str):
    """Send SMS via SNS"""
    try:
        resp = sns.publish(PhoneNumber=phone_number, Message=message)
        print(f"[INFO] SMS sent to {phone_number}")
        return resp
    except Exception as e:
        print(f"[ERROR] Failed to send SMS: {e}")
        return None

def send_email_via_ses(subject: str, to_email: str, body_html: str):
    """Send HTML email via SES"""
    if not SES_FROM:
        raise RuntimeError("SES_FROM not set")
    try:
        resp = ses.send_email(
            Source=SES_FROM,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Html": {"Data": body_html}}
            }
        )
        print(f"[INFO] Email sent to {to_email}")
        return resp
    except Exception as e:
        print(f"[ERROR] Failed to send email to {to_email}: {e}")
        return None
