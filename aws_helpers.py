# aws_helpers.py
import boto3
import os
import json

region = os.environ.get("AWS_REGION", "us-east-1")

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
def send_to_sqs_instant(message: dict):
    """Push a message to the instant notification SQS queue"""
    if not INSTANT_QUEUE_URL:
        print("⚠️ INSTANT_QUEUE_URL not set")
        return
    sqs.send_message(
        QueueUrl=INSTANT_QUEUE_URL,
        MessageBody=json.dumps(message)
    )
    print(f"📤 Sent instant message to SQS for {message.get('symbol')} (user: {message.get('email')})")

def send_to_sqs_pdf(message: dict):
    """Push a message to the PDF generation SQS queue"""
    if not PDF_QUEUE_URL:
        print("⚠️ PDF_QUEUE_URL not set")
        return
    sqs.send_message(
        QueueUrl=PDF_QUEUE_URL,
        MessageBody=json.dumps(message)
    )
    print(f"📤 Sent PDF job to SQS for {message.get('symbol')} (signal_id: {message.get('signal_id')})")

# -----------------------------
# S3 helper
# -----------------------------
def upload_pdf_to_s3(local_path: str, key: str) -> str:
    """Upload a PDF file to S3 and return the public URL"""
    if not S3_BUCKET:
        raise RuntimeError("PDF_S3_BUCKET not set")
    s3.upload_file(local_path, S3_BUCKET, key)
    url = f"https://{S3_BUCKET}.s3.amazonaws.com/{key}"
    print(f"✅ Uploaded PDF to S3: {url}")
    return url

# -----------------------------
# SNS / SES helpers
# -----------------------------
def publish_sms(message: str, phone_number: str):
    """Send SMS via SNS"""
    try:
        resp = sns.publish(PhoneNumber=phone_number, Message=message)
        print(f"✅ SMS sent to {phone_number}")
        return resp
    except Exception as e:
        print(f"⚠️ Failed to send SMS: {e}")

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
        print(f"✅ Email sent to {to_email}")
        return resp
    except Exception as e:
        print(f"⚠️ Failed to send email to {to_email}: {e}")
