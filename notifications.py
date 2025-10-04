# notifications.py
import os
import boto3
from botocore.exceptions import ClientError

AWS_REGION = os.environ.get("AWS_REGION")
SENDER = os.environ.get("SES_SENDER_EMAIL")

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
