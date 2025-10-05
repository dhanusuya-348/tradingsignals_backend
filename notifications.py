# notifications.py
import os
import boto3
from botocore.exceptions import ClientError

try:
    from load_env import load_env_file
    load_env_file()
    print("[notifications] Loaded .env file")
except ImportError:
    print("[notifications] load_env.py not found, using system environment variables")

AWS_REGION = os.environ.get("AWS_REGION")
SENDER = os.environ.get("SES_FROM_EMAIL")

ses_client = boto3.client("ses", region_name=AWS_REGION)

def send_email(to_email, subject, body_text, body_html=None):
    """
    Send an email via AWS SES.
    """
    if body_html is None:
        body_html = f"<html><body>{body_text}</body></html>"

    try:
        response = ses_client.send_email(
            Source=SENDER,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {
                    "Text": {"Data": body_text},
                    "Html": {"Data": body_html},
                },
            },
        )
        print(f"[SES] Email sent to {to_email}, MessageId: {response['MessageId']}")
        return True
    except ClientError as e:
        print(f"[SES] Failed to send email to {to_email}: {e.response['Error']['Message']}")
        return False
    
if __name__ == "__main__":
    # Quick SES test
    send_email(
        to_email="dhanurk25@gmail.com",  # replace with your actual email
        subject="SES Test Email",
        body_text="This is a quick test to check if SES is working."
    )

