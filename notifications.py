#notifications.py
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

def format_signal_email(signal_data):
    """
    Create a nicely formatted HTML email for trading signal notifications.
    """
    symbol = signal_data.get("symbol", "N/A")
    signal = signal_data.get("signal", "N/A")
    confidence = signal_data.get("confidence", "N/A")
    sentiment = signal_data.get("sentiment", "neutral")
    decision = signal_data.get("decision", "N/A")
    timing = signal_data.get("timing", {})
    risk = signal_data.get("risk", {})

    ltf = signal_data["ltf"]
    interval = signal_data["interval"]
    htf = signal_data["htf"]
    ind = signal_data["indicators"]

    def safe_get(tf, key):
        return ind.get(tf, {}).get(key, "-")

    # Pick colors
    color_map = {"BUY": "#2ecc71", "SELL": "#e74c3c", "HOLD": "#f1c40f"}
    signal_color = color_map.get(signal, "#3498db")

    body_html = f"""
    <html>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">

      <div style="max-width: 700px; margin:auto; background:white; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.1); padding:25px;">
        <h2 style="color:#333;">🚀 {symbol}/USDT — <span style='color:{signal_color};'>{signal}</span> Signal</h2>
        <p style="font-size:15px; color:#555;">Confidence: <b>{confidence}%</b> | Sentiment: <b>{sentiment}</b></p>
        <hr style="border:none; border-top:1px solid #eee; margin:15px 0;"/>

        <h3 style="color:#444;">📊 Indicator Summary</h3>
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
          <tr style="background:#222; color:white;">
            <th style="padding:8px;">Indicator</th>
            <th style="padding:8px;">{ltf}</th>
            <th style="padding:8px;">{interval}</th>
            <th style="padding:8px;">{htf}</th>
          </tr>
          <tr>
            <td style="padding:8px;">MACD</td>
            <td style="padding:8px;">{safe_get(ltf, 'macd')}</td>
            <td style="padding:8px;">{safe_get(interval, 'macd')}</td>
            <td style="padding:8px;">{safe_get(htf, 'macd')}</td>
          </tr>
          <tr style="background:#fafafa;">
            <td style="padding:8px;">RSI</td>
            <td style="padding:8px;">{safe_get(ltf, 'rsi_value'):.2f} ({safe_get(ltf, 'rsi_signal')})</td>
            <td style="padding:8px;">{safe_get(interval, 'rsi_value'):.2f} ({safe_get(interval, 'rsi_signal')})</td>
            <td style="padding:8px;">{safe_get(htf, 'rsi_value'):.2f} ({safe_get(htf, 'rsi_signal')})</td>
          </tr>
          <tr>
            <td style="padding:8px;">Bollinger Bands</td>
            <td style="padding:8px;">{safe_get(ltf, 'bb')}</td>
            <td style="padding:8px;">{safe_get(interval, 'bb')}</td>
            <td style="padding:8px;">{safe_get(htf, 'bb')}</td>
          </tr>
          <tr style="background:#fafafa;">
            <td style="padding:8px;">Volatility</td>
            <td style="padding:8px;">{safe_get(ltf, 'volatility')}</td>
            <td style="padding:8px;">{safe_get(interval, 'volatility')}</td>
            <td style="padding:8px;">{safe_get(htf, 'volatility')}</td>
          </tr>
        </table>

        <h3 style="color:#444; margin-top:20px;">💰 Risk & Reward</h3>
        <ul style="line-height:1.6; color:#555;">
          <li><b>Risk-Reward:</b> {risk.get('risk_reward_label', '-')}</li>
          <li><b>Stop Loss:</b> {risk.get('suggested_stop_loss', '-')}</li>
          <li><b>Take Profit:</b> {risk.get('suggested_take_profit', '-')}</li>
          <li><b>Expected Profit:</b> {risk.get('expected_profit_percent', '-')}%</li>
          <li><b>Risk Level:</b> {risk.get('risk_level', '-')}</li>
        </ul>

        <h3 style="color:#444; margin-top:20px;">🕒 Timing</h3>
        <p style="color:#555;">From <b>{timing.get('start', '-')}</b> to <b>{timing.get('end', '-')}</b>  
        <br>Duration: <b>{timing.get('duration', '-')}</b></p>

        <hr style="border:none; border-top:1px solid #eee; margin:20px 0;"/>
        <p style="font-size:13px; color:#777;">✅ Decision: <b>{decision}</b></p>
        <p style="font-size:12px; color:#aaa; text-align:center;">DumbledoreCapital © 2025 | AI-Powered Crypto Insights</p>
      </div>
    </body>
    </html>
    """
    return body_html


def send_email(to_email, subject, body_text=None, body_html=None):
    if body_html is None and body_text is None:
        raise ValueError("Either body_text or body_html must be provided")

    if body_html is None:
        body_html = f"<html><body>{body_text}</body></html>"

    try:
        response = ses_client.send_email(
            Source=SENDER,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {
                    "Html": {"Data": body_html},
                    "Text": {"Data": body_text or 'HTML Email'},
                },
            },
        )
        print(f"[SES] Email sent to {to_email}, MessageId: {response['MessageId']}")
        return True
    except ClientError as e:
        print(f"[SES] Failed to send email: {e.response['Error']['Message']}")
        return False


# Quick local test
if __name__ == "__main__":
    # Fake data for preview
    test_signal = {
        "symbol": "ETH",
        "interval": "1h",
        "ltf": "30m",
        "htf": "4h",
        "signal": "BUY",
        "confidence": 69,
        "sentiment": "neutral",
        "indicators": {
            "30m": {"macd": "bullish", "rsi_value": 73.6, "rsi_signal": "neutral", "bb": "within_range", "volatility": "medium"},
            "1h": {"macd": "bullish", "rsi_value": 70.3, "rsi_signal": "neutral", "bb": "within_range", "volatility": "medium"},
            "4h": {"macd": "bullish", "rsi_value": 74.2, "rsi_signal": "neutral", "bb": "breakout_up", "volatility": "low"},
        },
        "risk": {
            "risk_reward_label": "1:2.7",
            "suggested_stop_loss": 4536.94,
            "suggested_take_profit": 4792.57,
            "expected_profit_percent": 4.05,
            "risk_level": "low"
        },
        "decision": "APPROVED",
        "timing": {"start": "2025-10-05 08:00:00", "end": "2025-10-05 12:48:00", "duration": "~288 minutes"}
    }

    html = format_signal_email(test_signal)
    send_email("dhanurk25@gmail.com", "🚀 ETH Signal Alert - BUY", body_html=html)


# # notifications.py
# import os
# import boto3
# from botocore.exceptions import ClientError

# try:
#     from load_env import load_env_file
#     load_env_file()
#     print("[notifications] Loaded .env file")
# except ImportError:
#     print("[notifications] load_env.py not found, using system environment variables")

# AWS_REGION = os.environ.get("AWS_REGION")
# SENDER = os.environ.get("SES_FROM_EMAIL")

# ses_client = boto3.client("ses", region_name=AWS_REGION)

# def send_email(to_email, subject, body_text, body_html=None):
#     """
#     Send an email via AWS SES.
#     """
#     if body_html is None:
#         body_html = f"<html><body>{body_text}</body></html>"

#     try:
#         response = ses_client.send_email(
#             Source=SENDER,
#             Destination={"ToAddresses": [to_email]},
#             Message={
#                 "Subject": {"Data": subject},
#                 "Body": {
#                     "Text": {"Data": body_text},
#                     "Html": {"Data": body_html},
#                 },
#             },
#         )
#         print(f"[SES] Email sent to {to_email}, MessageId: {response['MessageId']}")
#         return True
#     except ClientError as e:
#         print(f"[SES] Failed to send email to {to_email}: {e.response['Error']['Message']}")
#         return False
    
# if __name__ == "__main__":
#     # Quick SES test
#     send_email(
#         to_email="dhanurk25@gmail.com",  # replace with your actual email
#         subject="SES Test Email",
#         body_text="This is a quick test to check if SES is working."
#     )

