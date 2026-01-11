#notifications.py
import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime

try:
    from load_env import load_env_file
    load_env_file()
    print("[notifications] Loaded .env file")
except ImportError:
    print("[notifications] load_env.py not found, using system environment variables")

AWS_REGION = os.environ.get("AWS_REGION")
SENDER = os.environ.get("SES_FROM_EMAIL")

ses_client = boto3.client("ses", region_name=AWS_REGION)

def check_ses_configuration():
    """
    Comprehensive check of AWS SES configuration and account status
    """
    print("\n" + "="*70)
    print("AWS SES CONFIGURATION CHECK")
    print("="*70)
    
    try:
        # 1. Check basic config
        print(f"\n✓ AWS Region: {AWS_REGION}")
        print(f"✓ Sender Email: {SENDER}")
        
        if not AWS_REGION:
            print("❌ ERROR: AWS_REGION not set in .env")
            return False
        
        if not SENDER:
            print("❌ ERROR: SES_FROM_EMAIL not set in .env")
            return False
        
        # 2. Get verified identities
        print("\n📋 Checking Verified Identities...")
        identities_response = ses_client.list_identities()
        identities = identities_response.get('Identities', [])
        
        if not identities:
            print("❌ ERROR: No verified identities found!")
            print("   → You need to verify at least one domain/email in AWS SES")
            return False
        
        print(f"✓ Verified Identities: {identities}")
        
        # 3. Check if sender domain/email is verified
        sender_domain = SENDER.split('@')[1] if '@' in SENDER else SENDER
        verified = False
        
        for identity in identities:
            if identity == SENDER or identity == sender_domain:
                verified = True
                print(f"✓ Sender '{SENDER}' is verified!")
                break
        
        if not verified:
            print(f"❌ ERROR: Sender '{SENDER}' is NOT verified!")
            print(f"   → Verified identities: {identities}")
            print(f"   → You need to verify '{sender_domain}' in AWS SES")
            return False
        
        # 4. Check if account sending is enabled (Sandbox status)
        print("\n🔐 Checking Account Status...")
        sending_response = ses_client.get_account_sending_enabled()
        sending_enabled = sending_response.get('Enabled', False)
        
        if sending_enabled:
            print("✓ Account sending is ENABLED (Production Access)")
        else:
            print("⚠️  WARNING: Account is in SANDBOX MODE")
            print("   → You can only send to verified email addresses")
            print("   → To send to any email, request Production Access from AWS")
        
        # 5. Check account quotas
        print("\n📊 Checking Send Quota...")
        quota_response = ses_client.get_send_quota()
        max_send_rate = quota_response.get('Max24HourSend', 'N/A')
        max_send_per_second = quota_response.get('MaxSendRate', 'N/A')
        sent_24h = quota_response.get('Sent24HourSend', 0)
        
        print(f"✓ Max 24-hour send: {max_send_rate} emails")
        print(f"✓ Max send rate: {max_send_per_second} emails/second")
        print(f"✓ Already sent (24h): {sent_24h} emails")
        
        # 6. Check email sending statistics
        print("\n📈 Checking Bounce/Complaint Rates...")
        try:
            stats_response = ses_client.get_account_summary()
            stats = stats_response.get('SendingQuotaMetrics', {})
            
            bounces = stats.get('Bounces', 0)
            complaints = stats.get('Complaints', 0)
            rejects = stats.get('Rejects', 0)
            
            print(f"✓ Bounces: {bounces}")
            print(f"✓ Complaints: {complaints}")
            print(f"✓ Rejects: {rejects}")
            
            if bounces > 0 or complaints > 0:
                print("⚠️  WARNING: You have bounces/complaints. Check your recipient list!")
        except:
            print("✓ Statistics check skipped (older AWS account)")
        
        print("\n" + "="*70)
        print("✅ SES CONFIGURATION LOOKS GOOD!")
        print("="*70 + "\n")
        return True
        
    except ClientError as e:
        print(f"\n❌ ERROR: {e.response['Error']['Code']}")
        print(f"   → {e.response['Error']['Message']}")
        print("\n   POSSIBLE FIXES:")
        print("   1. Check AWS_REGION in .env (should be where you verified domain)")
        print("   2. Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env")
        print("   3. Make sure your IAM user has SES permissions")
        print("   4. Verify your domain in AWS SES console")
        print("="*70 + "\n")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        print("="*70 + "\n")
        return False


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
    price = signal_data.get("price", "N/A")

    ltf = signal_data.get("ltf", "N/A")
    interval = signal_data.get("interval", "N/A")
    htf = signal_data.get("htf", "N/A")
    ind = signal_data.get("indicators", {})

    def safe_get(tf, key):
        return ind.get(tf, {}).get(key, "-")

    def safe_format(value):
        """Format numeric values safely"""
        if value == "N/A" or value == "-" or value is None:
            return "N/A"
        try:
            return f"${float(value):,.2f}"
        except (ValueError, TypeError):
            return str(value)

    def format_rsi(value):
        """Format RSI values to 2 decimal places"""
        if value == "-" or value is None:
            return "-"
        try:
            return f"{float(value):.2f}"
        except (ValueError, TypeError):
            return str(value)

    def format_datetime(date_str):
        """Format datetime string to 'DD MMM, YYYY HH:MM:SS UTC' format"""
        if date_str == "-" or date_str is None or date_str == "":
            return "-"
        
        try:
            # Try multiple datetime formats that might come from API/database
            formats_to_try = [
                "%Y-%m-%d %H:%M:%S.%f",        # 2025-09-29 09:35:04.094713 (with microseconds)
                "%Y-%m-%d %H:%M:%S",           # 2025-10-16 09:00:00
                "%Y-%m-%dT%H:%M:%S",           # 2025-10-16T09:00:00
                "%Y-%m-%dT%H:%M:%SZ",          # 2025-10-16T09:00:00Z (ISO format)
                "%Y-%m-%dT%H:%M:%S.%f",        # 2025-10-16T09:00:00.000000
                "%Y-%m-%dT%H:%M:%S.%fZ",       # 2025-10-16T09:00:00.000000Z
            ]
            
            dt = None
            for fmt in formats_to_try:
                try:
                    dt = datetime.strptime(date_str.strip().replace('Z', ''), fmt.replace('Z', ''))
                    break
                except ValueError:
                    continue
            
            if dt is None:
                print(f"[DEBUG] Could not parse datetime with any format: {date_str}")
                return str(date_str)
            
            # Format to desired output: 16 OCT, 2025 09:00:00 UTC
            formatted = dt.strftime("%d %b, %Y %H:%M:%S UTC").upper()
            print(f"[DEBUG] Successfully formatted: {date_str} -> {formatted}")
            return formatted
            
        except (ValueError, TypeError, AttributeError) as e:
            print(f"[DEBUG] Error parsing datetime '{date_str}': {e}")
            return str(date_str)

    # Format datetime BEFORE creating HTML string
    valid_from = format_datetime(timing.get('start', '-'))
    valid_to = format_datetime(timing.get('end', '-'))

    # Pick colors
    color_map = {"BUY": "#2ecc71", "SELL": "#e74c3c", "HOLD": "#f1c40f"}
    signal_color = color_map.get(signal, "#3498db")

    body_html = f"""
    <html>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">

      <div style="max-width: 700px; margin:auto; background:white; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.1); padding:25px;">
        <h2 style="color:#333;">🚀 {symbol}/USDT — <span style='color:{signal_color};'>{signal}</span> Signal</h2>
        <p style="font-size:15px; color:#555;">
          <b>Entry Price:</b> {safe_format(price)} | 
          <b>Confidence:</b> {confidence}% | 
          <b>Sentiment:</b> {sentiment}
        </p>
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
            <td style="padding:8px;">{format_rsi(safe_get(ltf, 'rsi_value'))} ({safe_get(ltf, 'rsi_signal')})</td>
            <td style="padding:8px;">{format_rsi(safe_get(interval, 'rsi_value'))} ({safe_get(interval, 'rsi_signal')})</td>
            <td style="padding:8px;">{format_rsi(safe_get(htf, 'rsi_value'))} ({safe_get(htf, 'rsi_signal')})</td>
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
          <li><b>Entry Price:</b> {safe_format(price)}</li>
          <li><b>Stop Loss:</b> {safe_format(risk.get('suggested_stop_loss'))}</li>
          <li><b>Take Profit:</b> {safe_format(risk.get('suggested_take_profit'))}</li>
          <li><b>Risk-Reward Ratio:</b> {risk.get('risk_reward_label', '-')}</li>
          <li><b>Expected Profit:</b> {risk.get('expected_profit_percent', '-')}%</li>
          <li><b>Risk Level:</b> {risk.get('risk_level', '-')}</li>
        </ul>

        <h3 style="color:#444; margin-top:20px;">🕒 Timing</h3>
        <p style="color:#555;">
          <b>Valid From:</b> {valid_from}<br>
          <b>Valid To:</b> {valid_to}<br>
          <b>Duration:</b> {timing.get('duration', '-')}
        </p>

        <div style="background:#fffbea; border-left:4px solid #f39c12; padding:12px; margin:15px 0; border-radius:4px;">
          <p style="color:#555; font-size:14px; margin:0;"><b>📌 Exit Note:</b> Please exit the trade once the Take Profit level, Stop Loss level, or the validity time window has been reached.</p>
        </div>

        <hr style="border:none; border-top:1px solid #eee; margin:20px 0;"/>
        <p style="font-size:13px; color:#777;">✅ Decision: <b>{decision}</b></p>
        <p style="font-size:12px; color:#aaa; text-align:center; margin-bottom:10px;">Dollaraptor © 2025 | AI-Powered Crypto Insights</p>
        <p style="font-size:11px; color:#999; text-align:center; background:#f9f9f9; padding:10px; border-radius:4px; border:1px solid #eee;"><b>⚠️ Risk Disclaimer:</b> This signal is for educational purposes only. Trading carries substantial risk. All trading decisions are made at your own will and discretion. We are not responsible for any losses incurred.</p>
      </div>
    </body>
    </html>
    """
    return body_html

# Add this to your existing notifications.py file (after format_signal_email function)

def format_performance_email(perf_data):
    """
    Create a nicely formatted HTML email for performance/backtest result notifications.
    
    perf_data comes from signal_performance table columns:
    {
        "symbol": "BNB",
        "signal_id": 123,
        "status": "COMPLETED",
        "exit_price": "1215.45",
        "pnl": "27.26",
        "pnl_percent": "2.29",
        "trade_duration": "30 minutes",
        "final_result": "SUCCESS",  # or FAILURE
        "exit_reason": "TP",  # TP = Take Profit, SL = Stop Loss, TIME = Timeout
        "confidence": 62,
        "sentiment": "bullish",
        "analysis_notes": "...",
    }
    """
    symbol = perf_data.get("symbol", "N/A")
    signal_id = perf_data.get("signal_id", "N/A")
    status = perf_data.get("status", "UNKNOWN")
    exit_price = perf_data.get("exit_price", "N/A")
    pnl = perf_data.get("pnl", 0)
    pnl_percent = perf_data.get("pnl_percent", 0)
    trade_duration = perf_data.get("trade_duration", "-")
    final_result = perf_data.get("final_result", "UNKNOWN")
    exit_reason = perf_data.get("exit_reason", "-")
    confidence = perf_data.get("confidence", "N/A")
    sentiment = perf_data.get("sentiment", "neutral")
    analysis_notes = perf_data.get("analysis_notes", "No additional notes")

    def safe_format(value):
        """Format numeric values safely"""
        if value == "N/A" or value == "-" or value is None:
            return "N/A"
        try:
            return f"${float(value):,.2f}"
        except (ValueError, TypeError):
            return str(value)

    def format_percent(value):
        """Format percentage values"""
        if value == "N/A" or value is None or value == "-":
            return "N/A"
        try:
            val = float(value)
            color = "#2ecc71" if val >= 0 else "#e74c3c"
            sign = "+" if val >= 0 else ""
            return f"<span style='color:{color};'>{sign}{val:.2f}%</span>"
        except (ValueError, TypeError):
            return str(value)

    # Pick status color
    status_color_map = {
        "COMPLETED": "#2ecc71",
        "FAILED": "#e74c3c",
        "ERROR": "#c0392b",
    }
    status_color = status_color_map.get(status, "#3498db")

    # Pick result color and emoji
    if final_result == "SUCCESS":
        result_color = "#2ecc71"
        result_emoji = "🎉"
        result_text = "WIN"
    elif final_result == "FAILURE":
        result_color = "#e74c3c"
        result_emoji = "📉"
        result_text = "LOSS"
    else:
        result_color = "#95a5a6"
        result_emoji = "❓"
        result_text = final_result

    # Map exit reason
    exit_reason_map = {
        "TP": "Take Profit ✅",
        "SL": "Stop Loss ⛔",
        "TIME": "Time Expired ⏱️",
    }
    exit_reason_text = exit_reason_map.get(exit_reason, exit_reason)

    body_html = f"""
    <html>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">

      <div style="max-width: 700px; margin:auto; background:white; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.1); padding:25px;">
        
        <h2 style="color:#333;">📊 {symbol}/USDT — Performance Report</h2>
        <p style="font-size:14px; color:#777;">Signal ID: #{signal_id}</p>
        
        <div style="background:{status_color}; color:white; padding:12px; border-radius:6px; text-align:center; margin:15px 0; font-weight:bold; font-size:16px;">
          Status: {status}
        </div>

        <hr style="border:none; border-top:1px solid #eee; margin:20px 0;"/>

        <h3 style="color:#444;">🎯 Trade Result</h3>
        <div style="background:#f9f9f9; padding:15px; border-radius:6px; border-left:4px solid {result_color};">
          <p style="font-size:20px; font-weight:bold; color:{result_color}; margin:5px 0;">
            {result_emoji} {result_text}
          </p>
          <p style="color:#555; margin:10px 0; font-size:15px;">
            <b>P&L:</b> {safe_format(pnl)} ({format_percent(pnl_percent)})
          </p>
        </div>

        <h3 style="color:#444; margin-top:20px;">💼 Trade Details</h3>
        <table style="width:100%; border-collapse:collapse; font-size:14px;">
          <tr style="background:#f5f5f5;">
            <td style="padding:10px; font-weight:bold;">Exit Price</td>
            <td style="padding:10px;">{safe_format(exit_price)}</td>
          </tr>
          <tr>
            <td style="padding:10px; font-weight:bold;">Exit Reason</td>
            <td style="padding:10px;">{exit_reason_text}</td>
          </tr>
          <tr style="background:#f5f5f5;">
            <td style="padding:10px; font-weight:bold;">Trade Duration</td>
            <td style="padding:10px;">{trade_duration}</td>
          </tr>
        </table>

        <h3 style="color:#444; margin-top:20px;">🔍 Signal Metrics</h3>
        <ul style="line-height:1.8; color:#555;">
          <li><b>Confidence:</b> {confidence}%</li>
          <li><b>Sentiment:</b> {sentiment.capitalize()}</li>
        </ul>

        <h3 style="color:#444; margin-top:20px;">📝 Analysis Notes</h3>
        <div style="background:#fffbea; padding:12px; border-radius:6px; border-left:4px solid #f39c12;">
          <p style="color:#555; font-size:14px; margin:0;">{analysis_notes}</p>
        </div>

        <hr style="border:none; border-top:1px solid #eee; margin:20px 0;"/>
        
        <div style="background:#e8f5e9; border-left:4px solid #4caf50; padding:12px; margin:15px 0; border-radius:4px;">
          <p style="color:#2e7d32; font-size:14px; margin:0;"><b>✅ Keep Learning:</b> Review this trade to improve your trading strategy!</p>
        </div>

        <p style="font-size:12px; color:#aaa; text-align:center; margin-bottom:10px;">Dollaraptor © 2025 | AI-Powered Crypto Insights</p>
        <p style="font-size:11px; color:#999; text-align:center; background:#f9f9f9; padding:10px; border-radius:4px; border:1px solid #eee;"><b>📌 Disclaimer:</b> This is a performance report based on backtesting/simulation. Past performance does not guarantee future results. Always trade responsibly.</p>
      </div>
    </body>
    </html>
    """
    return body_html


def get_user_sub_from_email(email):
    """
    Look up user_sub by email address.
    This is useful when you only have the email but need the user_sub for preference checking.
    
    Args:
        email: User's email address
    
    Returns:
        user_sub if found, None otherwise
    """
    try:
        from models import get_session_context, User
        with get_session_context() as session:
            user = session.query(User).filter_by(email=email).first()
            if user:
                print(f"🔍 [EMAIL_LOOKUP] Found user_sub {user.user_sub} for email {email}")
                return user.user_sub
            else:
                print(f"🔍 [EMAIL_LOOKUP] No user found for email {email}")
                return None
    except Exception as e:
        print(f"⚠️ [EMAIL_LOOKUP] Error looking up user_sub for {email}: {e}")
        return None


def send_performance_email(to_email, perf_data, user_sub):
    """
    Send performance report email via AWS SES
    
    Args:
        to_email: recipient email address
        perf_data: performance data dictionary
        user_sub: user ID (REQUIRED for email preference check)
    
    Returns:
        True if sent or skipped (due to preference), False if error
    """
    symbol = perf_data.get("symbol", "UNKNOWN")
    final_result = perf_data.get("final_result", "UNKNOWN")
    
    print(f"📧 [PERF_EMAIL] Sending performance email for {symbol} to {to_email} (user: {user_sub})")
    
    # Create subject with emoji based on result
    emoji_map = {"SUCCESS": "🎉", "FAILURE": "📉", "ERROR": "⚠️"}
    emoji = emoji_map.get(final_result, "📊")
    
    subject = f"{emoji} {symbol} Performance Report - {final_result}"
    
    body_html = format_performance_email(perf_data)
    
    result = send_email(to_email, subject, body_html=body_html, user_sub=user_sub)
    
    if result:
        print(f"✅ [PERF_EMAIL] Performance email sent successfully for {symbol}")
    else:
        print(f"❌ [PERF_EMAIL] Failed to send performance email for {symbol}")
    
    return result

def send_email(to_email, subject, body_text=None, body_html=None, user_sub=None):
    """
    Send email via AWS SES with error handling
    
    Checks user's email_notifications preference before sending.
    If user_sub is provided, checks if user has email notifications enabled.
    If disabled, skips sending and logs it.
    If the user doesn't exist or there's an error checking preferences, logs a warning but still sends the email (fail-open).
    
    Args:
        to_email: recipient email address
        subject: email subject
        body_text: plain text body (optional)
        body_html: HTML body (optional)
        user_sub: user ID for preference checking (optional)
    
    Returns:
        True if sent or skipped (due to preference), False if error
    """
    print(f"📧 [SES] send_email called: to={to_email}, subject='{subject}', user_sub={user_sub}")
    
    if body_html is None and body_text is None:
        print(f"❌ [SES] Error: Either body_text or body_html must be provided")
        raise ValueError("Either body_text or body_html must be provided")

    if body_html is None:
        body_html = f"<html><body>{body_text}</body></html>"

    # Check email notifications preference if user_sub is provided
    if user_sub:
        print(f"🔍 [SES] Checking email preferences for user {user_sub}")
        try:
            from models import get_session_context, User
            with get_session_context() as session:
                user = session.query(User).filter_by(user_sub=user_sub).first()
                if user:
                    print(f"👤 [SES] User found: {user.email}, email_notifications={user.email_notifications}")
                    if not user.email_notifications:
                        print(f"📧 [SES] ✋ Email notifications DISABLED for user {user_sub}, skipping email to {to_email}")
                        return True  # Return success to avoid breaking existing flows
                    else:
                        print(f"📧 [SES] ✅ Email notifications ENABLED for user {user_sub}, proceeding with send")
                else:
                    print(f"⚠️ [SES] User {user_sub} not found in database, proceeding with send (fail-open)")
        except Exception as e:
            print(f"⚠️ [SES] Could not check email preference for {user_sub}: {e}")
            print(f"⚠️ [SES] Proceeding with email send (fail-open behavior)")
            # Continue with sending email if we can't check preference
    else:
        print(f"📧 [SES] No user_sub provided, skipping preference check")

    print(f"📤 [SES] Attempting to send email via AWS SES...")
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
        print(f"✅ [SES] Email sent successfully to {to_email}")
        print(f"📧 [SES] MessageId: {response['MessageId']}")
        print(f"📧 [SES] Subject: {subject}")
        return True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        
        print(f"❌ [SES] Failed to send email to {to_email}")
        print(f"❌ [SES] Error Code: {error_code}")
        print(f"❌ [SES] Message: {error_msg}")
        print(f"❌ [SES] Subject: {subject}")
        
        # Provide specific troubleshooting
        if error_code == "InvalidParameterValue":
            print(f"💡 [SES] → Check that your sender email is verified in AWS SES")
        elif error_code == "AuthFailure":
            print(f"💡 [SES] → Check your AWS credentials (Access Key & Secret Key)")
        elif error_code == "MessageRejected":
            print(f"💡 [SES] → Check if recipient email is verified (you're in Sandbox mode)")
        
        return False
    except Exception as e:
        print(f"❌ [SES] Unexpected error sending email to {to_email}: {e}")
        return False


# Quick local test
if __name__ == "__main__":
    import sys
    from datetime import datetime, timedelta
    
    # ✅ CHANGE THESE TO YOUR VALUES
    TEST_USER_SUB = "492e7498-30d1-7070-2185-54303665d035"  # Your user_sub
    TEST_EMAIL = "dhanurk25@gmail.com"                   # Your email
    
    print("\n" + "="*70)
    print("🧪 EMAIL NOTIFICATIONS PREFERENCE TEST")
    print("="*70)
    print(f"\n📋 Testing with:")
    print(f"   User Sub: {TEST_USER_SUB}")
    print(f"   Email: {TEST_EMAIL}")
    
    # Check SES first
    config_ok = check_ses_configuration()
    if not config_ok:
        print("\n⛔ SES configuration issues detected!")
        sys.exit(1)
    
    # Create test signal
    test_signal = {
        "symbol": "BTC",
        "interval": "1h",
        "ltf": "15m",
        "htf": "4h",
        "signal": "BUY",
        "confidence": 62,
        "price": 1188.19,
        "sentiment": "bullish",
        "indicators": {
            "15m": {"macd": "bullish", "rsi_value": 57.32, "rsi_signal": "neutral", "bb": "within_range", "volatility": "medium"},
            "1h": {"macd": "bearish", "rsi_value": 52.93, "rsi_signal": "neutral", "bb": "within_range", "volatility": "medium"},
            "4h": {"macd": "bullish", "rsi_value": 65.5, "rsi_signal": "neutral", "bb": "breakout_up", "volatility": "low"},
        },
        "risk": {
            "risk_reward_label": "1:2.84",
            "suggested_stop_loss": 1177.65,
            "suggested_take_profit": 1218.11,
            "expected_profit_percent": 2.52,
            "risk_level": "low"
        },
        "decision": "APPROVED",
        "timing": {
            "start": "2025-09-29 09:35:04.094713",
            "end": "2025-09-29 10:05:04.094713",
            "duration": "~30 minutes"
        }
    }

    print("\n" + "="*70)
    print("FORMATTING EMAIL")
    print("="*70)
    
    html = format_signal_email(test_signal)
    print("✅ Email formatted")
    
    print("\n" + "="*70)
    print("SENDING EMAIL WITH USER_SUB (PREFERENCE CHECK)")
    print("="*70)
    
    # ✅ CRITICAL: Pass user_sub for preference checking!
    success = send_email(
        to_email=TEST_EMAIL,
        subject="🧪 TEST: BNB BUY Signal - Check Preferences",
        body_html=html,
        user_sub=TEST_USER_SUB  # ✅ THIS IS THE FIX!
    )
    
    print("\n" + "="*70)
    if success:
        print("✅ TEST COMPLETE - Check results above")
    else:
        print("❌ TEST FAILED")
    print("="*70)

# # Quick local test
# if __name__ == "__main__":
#     # First, check SES configuration
#     config_ok = check_ses_configuration()
    
#     if not config_ok:
#         print("\n⛔ SES configuration issues detected. Fix them before sending emails!")
#         exit(1)
    
#     # Fake data for preview - with various datetime formats to test
#     test_signal = {
#         "symbol": "BNB",
#         "interval": "1h",
#         "ltf": "15m",
#         "htf": "4h",
#         "signal": "BUY",
#         "confidence": 62,
#         "price": 1188.19,
#         "sentiment": "bullish",
#         "indicators": {
#             "15m": {"macd": "bullish", "rsi_value": 57.32, "rsi_signal": "neutral", "bb": "within_range", "volatility": "medium"},
#             "1h": {"macd": "bearish", "rsi_value": 52.93, "rsi_signal": "neutral", "bb": "within_range", "volatility": "medium"},
#             "4h": {"macd": "bullish", "rsi_value": 65.5, "rsi_signal": "neutral", "bb": "breakout_up", "volatility": "low"},
#         },
#         "risk": {
#             "risk_reward_label": "1:2.84",
#             "suggested_stop_loss": 1177.65,
#             "suggested_take_profit": 1218.11,
#             "expected_profit_percent": 2.52,
#             "risk_level": "low"
#         },
#         "decision": "APPROVED",
#         "timing": {
#             "start": "2025-09-29 09:35:04.094713",      # Database format with microseconds
#             "end": "2025-09-29 10:05:04.094713",        # Database format with microseconds
#             "duration": "~30 minutes"
#         }
#     }

#     print("\n" + "="*70)
#     print("TESTING EMAIL SEND")
#     print("="*70)
    
#     html = format_signal_email(test_signal)
#     success = send_email("dhanurk25@gmail.com", "🚀 BNB Signal Alert - BUY", body_html=html)
    
#     if success:
#         print("\n" + "="*70)
#         print("✅ EMAIL SENT SUCCESSFULLY!")
#         print("="*70)
#     else:
#         print("\n" + "="*70)
#         print("❌ EMAIL FAILED - CHECK ERROR MESSAGES ABOVE")
#         print("="*70)

# #notifications.py
# import os
# import boto3
# from botocore.exceptions import ClientError
# from datetime import datetime

# try:
#     from load_env import load_env_file
#     load_env_file()
#     print("[notifications] Loaded .env file")
# except ImportError:
#     print("[notifications] load_env.py not found, using system environment variables")

# AWS_REGION = os.environ.get("AWS_REGION")
# SENDER = os.environ.get("SES_FROM_EMAIL")

# ses_client = boto3.client("ses", region_name=AWS_REGION)

# def format_signal_email(signal_data):
#     """
#     Create a nicely formatted HTML email for trading signal notifications.
#     """
#     symbol = signal_data.get("symbol", "N/A")
#     signal = signal_data.get("signal", "N/A")
#     confidence = signal_data.get("confidence", "N/A")
#     sentiment = signal_data.get("sentiment", "neutral")
#     decision = signal_data.get("decision", "N/A")
#     timing = signal_data.get("timing", {})
#     risk = signal_data.get("risk", {})
#     price = signal_data.get("price", "N/A")

#     ltf = signal_data.get("ltf", "N/A")
#     interval = signal_data.get("interval", "N/A")
#     htf = signal_data.get("htf", "N/A")
#     ind = signal_data.get("indicators", {})

#     def safe_get(tf, key):
#         return ind.get(tf, {}).get(key, "-")

#     def safe_format(value):
#         """Format numeric values safely"""
#         if value == "N/A" or value == "-" or value is None:
#             return "N/A"
#         try:
#             return f"${float(value):,.2f}"
#         except (ValueError, TypeError):
#             return str(value)

#     def format_rsi(value):
#         """Format RSI values to 2 decimal places"""
#         if value == "-" or value is None:
#             return "-"
#         try:
#             return f"{float(value):.2f}"
#         except (ValueError, TypeError):
#             return str(value)

#     def format_datetime(date_str):
#         """Format datetime string to 'DD MMM, YYYY HH:MM:SS UTC' format"""
#         if date_str == "-" or date_str is None or date_str == "":
#             return "-"
        
#         try:
#             # Try multiple datetime formats that might come from API/database
#             formats_to_try = [
#                 "%Y-%m-%d %H:%M:%S.%f",        # 2025-09-29 09:35:04.094713 (with microseconds)
#                 "%Y-%m-%d %H:%M:%S",           # 2025-10-16 09:00:00
#                 "%Y-%m-%dT%H:%M:%S",           # 2025-10-16T09:00:00
#                 "%Y-%m-%dT%H:%M:%SZ",          # 2025-10-16T09:00:00Z (ISO format)
#                 "%Y-%m-%dT%H:%M:%S.%f",        # 2025-10-16T09:00:00.000000
#                 "%Y-%m-%dT%H:%M:%S.%fZ",       # 2025-10-16T09:00:00.000000Z
#             ]
            
#             dt = None
#             for fmt in formats_to_try:
#                 try:
#                     dt = datetime.strptime(date_str.strip().replace('Z', ''), fmt.replace('Z', ''))
#                     break
#                 except ValueError:
#                     continue
            
#             if dt is None:
#                 print(f"[DEBUG] Could not parse datetime with any format: {date_str}")
#                 return str(date_str)
            
#             # Format to desired output: 16 OCT, 2025 09:00:00 UTC
#             formatted = dt.strftime("%d %b, %Y %H:%M:%S UTC").upper()
#             print(f"[DEBUG] Successfully formatted: {date_str} -> {formatted}")
#             return formatted
            
#         except (ValueError, TypeError, AttributeError) as e:
#             print(f"[DEBUG] Error parsing datetime '{date_str}': {e}")
#             return str(date_str)

#     # Format datetime BEFORE creating HTML string
#     valid_from = format_datetime(timing.get('start', '-'))
#     valid_to = format_datetime(timing.get('end', '-'))

#     # Pick colors
#     color_map = {"BUY": "#2ecc71", "SELL": "#e74c3c", "HOLD": "#f1c40f"}
#     signal_color = color_map.get(signal, "#3498db")

#     body_html = f"""
#     <html>
#     <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">

#       <div style="max-width: 700px; margin:auto; background:white; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.1); padding:25px;">
#         <h2 style="color:#333;">🚀 {symbol}/USDT — <span style='color:{signal_color};'>{signal}</span> Signal</h2>
#         <p style="font-size:15px; color:#555;">
#           <b>Entry Price:</b> {safe_format(price)} | 
#           <b>Confidence:</b> {confidence}% | 
#           <b>Sentiment:</b> {sentiment}
#         </p>
#         <hr style="border:none; border-top:1px solid #eee; margin:15px 0;"/>

#         <h3 style="color:#444;">📊 Indicator Summary</h3>
#         <table style="width:100%; border-collapse:collapse; font-size:14px;">
#           <tr style="background:#222; color:white;">
#             <th style="padding:8px;">Indicator</th>
#             <th style="padding:8px;">{ltf}</th>
#             <th style="padding:8px;">{interval}</th>
#             <th style="padding:8px;">{htf}</th>
#           </tr>
#           <tr>
#             <td style="padding:8px;">MACD</td>
#             <td style="padding:8px;">{safe_get(ltf, 'macd')}</td>
#             <td style="padding:8px;">{safe_get(interval, 'macd')}</td>
#             <td style="padding:8px;">{safe_get(htf, 'macd')}</td>
#           </tr>
#           <tr style="background:#fafafa;">
#             <td style="padding:8px;">RSI</td>
#             <td style="padding:8px;">{format_rsi(safe_get(ltf, 'rsi_value'))} ({safe_get(ltf, 'rsi_signal')})</td>
#             <td style="padding:8px;">{format_rsi(safe_get(interval, 'rsi_value'))} ({safe_get(interval, 'rsi_signal')})</td>
#             <td style="padding:8px;">{format_rsi(safe_get(htf, 'rsi_value'))} ({safe_get(htf, 'rsi_signal')})</td>
#           </tr>
#           <tr>
#             <td style="padding:8px;">Bollinger Bands</td>
#             <td style="padding:8px;">{safe_get(ltf, 'bb')}</td>
#             <td style="padding:8px;">{safe_get(interval, 'bb')}</td>
#             <td style="padding:8px;">{safe_get(htf, 'bb')}</td>
#           </tr>
#           <tr style="background:#fafafa;">
#             <td style="padding:8px;">Volatility</td>
#             <td style="padding:8px;">{safe_get(ltf, 'volatility')}</td>
#             <td style="padding:8px;">{safe_get(interval, 'volatility')}</td>
#             <td style="padding:8px;">{safe_get(htf, 'volatility')}</td>
#           </tr>
#         </table>

#         <h3 style="color:#444; margin-top:20px;">💰 Risk & Reward</h3>
#         <ul style="line-height:1.6; color:#555;">
#           <li><b>Entry Price:</b> {safe_format(price)}</li>
#           <li><b>Stop Loss:</b> {safe_format(risk.get('suggested_stop_loss'))}</li>
#           <li><b>Take Profit:</b> {safe_format(risk.get('suggested_take_profit'))}</li>
#           <li><b>Risk-Reward Ratio:</b> {risk.get('risk_reward_label', '-')}</li>
#           <li><b>Expected Profit:</b> {risk.get('expected_profit_percent', '-')}%</li>
#           <li><b>Risk Level:</b> {risk.get('risk_level', '-')}</li>
#         </ul>

#         <h3 style="color:#444; margin-top:20px;">🕒 Timing</h3>
#         <p style="color:#555;">
#           <b>Valid From:</b> {valid_from}<br>
#           <b>Valid To:</b> {valid_to}<br>
#           <b>Duration:</b> {timing.get('duration', '-')}
#         </p>

#         <div style="background:#fffbea; border-left:4px solid #f39c12; padding:12px; margin:15px 0; border-radius:4px;">
#           <p style="color:#555; font-size:14px; margin:0;"><b>📌 Exit Note:</b> Please exit the trade once the Take Profit level, Stop Loss level, or the validity time window has been reached.</p>
#         </div>

#         <hr style="border:none; border-top:1px solid #eee; margin:20px 0;"/>
#         <p style="font-size:13px; color:#777;">✅ Decision: <b>{decision}</b></p>
#         <p style="font-size:12px; color:#aaa; text-align:center; margin-bottom:10px;">Dollaraptor © 2025 | AI-Powered Crypto Insights</p>
#         <p style="font-size:11px; color:#999; text-align:center; background:#f9f9f9; padding:10px; border-radius:4px; border:1px solid #eee;"><b>⚠️ Risk Disclaimer:</b> This signal is for educational purposes only. Trading carries substantial risk. All trading decisions are made at your own will and discretion. We are not responsible for any losses incurred.</p>
#       </div>
#     </body>
#     </html>
#     """
#     return body_html


# def send_email(to_email, subject, body_text=None, body_html=None):
#     if body_html is None and body_text is None:
#         raise ValueError("Either body_text or body_html must be provided")

#     if body_html is None:
#         body_html = f"<html><body>{body_text}</body></html>"

#     try:
#         response = ses_client.send_email(
#             Source=SENDER,
#             Destination={"ToAddresses": [to_email]},
#             Message={
#                 "Subject": {"Data": subject},
#                 "Body": {
#                     "Html": {"Data": body_html},
#                     "Text": {"Data": body_text or 'HTML Email'},
#                 },
#             },
#         )
#         print(f"[SES] Email sent to {to_email}, MessageId: {response['MessageId']}")
#         return True
#     except ClientError as e:
#         print(f"[SES] Failed to send email: {e.response['Error']['Message']}")
#         return False


# # Quick local test
# if __name__ == "__main__":
#     # Fake data for preview - with various datetime formats to test
#     test_signal = {
#         "symbol": "BNB",
#         "interval": "1h",
#         "ltf": "15m",
#         "htf": "4h",
#         "signal": "BUY",
#         "confidence": 62,
#         "price": 1188.19,
#         "sentiment": "bullish",
#         "indicators": {
#             "15m": {"macd": "bullish", "rsi_value": 57.32, "rsi_signal": "neutral", "bb": "within_range", "volatility": "medium"},
#             "1h": {"macd": "bearish", "rsi_value": 52.93, "rsi_signal": "neutral", "bb": "within_range", "volatility": "medium"},
#             "4h": {"macd": "bullish", "rsi_value": 65.5, "rsi_signal": "neutral", "bb": "breakout_up", "volatility": "low"},
#         },
#         "risk": {
#             "risk_reward_label": "1:2.84",
#             "suggested_stop_loss": 1177.65,
#             "suggested_take_profit": 1218.11,
#             "expected_profit_percent": 2.52,
#             "risk_level": "low"
#         },
#         "decision": "APPROVED",
#         "timing": {
#             "start": "2025-09-29 09:35:04.094713",      # Database format with microseconds
#             "end": "2025-09-29 10:05:04.094713",        # Database format with microseconds
#             "duration": "~30 minutes"
#         }
#     }

#     print("\n" + "="*60)
#     print("TESTING DATETIME FORMATTING")
#     print("="*60)
    
#     html = format_signal_email(test_signal)
#     send_email("dhanurk25@gmail.com", "🚀 BNB Signal Alert - BUY", body_html=html)
    
#     print("\n" + "="*60)
#     print("EMAIL SENT - CHECK DEBUG LOGS ABOVE")
#     print("="*60)

# #notifications.py
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

# def format_signal_email(signal_data):
#     """
#     Create a nicely formatted HTML email for trading signal notifications.
#     """
#     symbol = signal_data.get("symbol", "N/A")
#     signal = signal_data.get("signal", "N/A")
#     confidence = signal_data.get("confidence", "N/A")
#     sentiment = signal_data.get("sentiment", "neutral")
#     decision = signal_data.get("decision", "N/A")
#     timing = signal_data.get("timing", {})
#     risk = signal_data.get("risk", {})
#     price = signal_data.get("price", "N/A")  # Get entry price

#     ltf = signal_data.get("ltf", "N/A")
#     interval = signal_data.get("interval", "N/A")
#     htf = signal_data.get("htf", "N/A")
#     ind = signal_data.get("indicators", {})

#     def safe_get(tf, key):
#         return ind.get(tf, {}).get(key, "-")

#     def safe_format(value):
#         """Format numeric values safely"""
#         if value == "N/A" or value == "-" or value is None:
#             return "N/A"
#         try:
#             return f"${float(value):,.2f}"
#         except (ValueError, TypeError):
#             return str(value)

#     # Pick colors
#     color_map = {"BUY": "#2ecc71", "SELL": "#e74c3c", "HOLD": "#f1c40f"}
#     signal_color = color_map.get(signal, "#3498db")

#     body_html = f"""
#     <html>
#     <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">

#       <div style="max-width: 700px; margin:auto; background:white; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.1); padding:25px;">
#         <h2 style="color:#333;">🚀 {symbol}/USDT — <span style='color:{signal_color};'>{signal}</span> Signal</h2>
#         <p style="font-size:15px; color:#555;">
#           <b>Entry Price:</b> {safe_format(price)} | 
#           <b>Confidence:</b> {confidence}% | 
#           <b>Sentiment:</b> {sentiment}
#         </p>
#         <hr style="border:none; border-top:1px solid #eee; margin:15px 0;"/>

#         <h3 style="color:#444;">📊 Indicator Summary</h3>
#         <table style="width:100%; border-collapse:collapse; font-size:14px;">
#           <tr style="background:#222; color:white;">
#             <th style="padding:8px;">Indicator</th>
#             <th style="padding:8px;">{ltf}</th>
#             <th style="padding:8px;">{interval}</th>
#             <th style="padding:8px;">{htf}</th>
#           </tr>
#           <tr>
#             <td style="padding:8px;">MACD</td>
#             <td style="padding:8px;">{safe_get(ltf, 'macd')}</td>
#             <td style="padding:8px;">{safe_get(interval, 'macd')}</td>
#             <td style="padding:8px;">{safe_get(htf, 'macd')}</td>
#           </tr>
#           <tr style="background:#fafafa;">
#             <td style="padding:8px;">RSI</td>
#             <td style="padding:8px;">{safe_get(ltf, 'rsi_value')} ({safe_get(ltf, 'rsi_signal')})</td>
#             <td style="padding:8px;">{safe_get(interval, 'rsi_value')} ({safe_get(interval, 'rsi_signal')})</td>
#             <td style="padding:8px;">{safe_get(htf, 'rsi_value')} ({safe_get(htf, 'rsi_signal')})</td>
#           </tr>
#           <tr>
#             <td style="padding:8px;">Bollinger Bands</td>
#             <td style="padding:8px;">{safe_get(ltf, 'bb')}</td>
#             <td style="padding:8px;">{safe_get(interval, 'bb')}</td>
#             <td style="padding:8px;">{safe_get(htf, 'bb')}</td>
#           </tr>
#           <tr style="background:#fafafa;">
#             <td style="padding:8px;">Volatility</td>
#             <td style="padding:8px;">{safe_get(ltf, 'volatility')}</td>
#             <td style="padding:8px;">{safe_get(interval, 'volatility')}</td>
#             <td style="padding:8px;">{safe_get(htf, 'volatility')}</td>
#           </tr>
#         </table>

#         <h3 style="color:#444; margin-top:20px;">💰 Risk & Reward</h3>
#         <ul style="line-height:1.6; color:#555;">
#           <li><b>Entry Price:</b> {safe_format(price)}</li>
#           <li><b>Stop Loss:</b> {safe_format(risk.get('suggested_stop_loss'))}</li>
#           <li><b>Take Profit:</b> {safe_format(risk.get('suggested_take_profit'))}</li>
#           <li><b>Risk-Reward Ratio:</b> {risk.get('risk_reward_label', '-')}</li>
#           <li><b>Expected Profit:</b> {risk.get('expected_profit_percent', '-')}%</li>
#           <li><b>Risk Level:</b> {risk.get('risk_level', '-')}</li>
#         </ul>

#         <h3 style="color:#444; margin-top:20px;">🕒 Timing</h3>
#         <p style="color:#555;">
#           <b>Valid From:</b> {timing.get('start', '-')}<br>
#           <b>Valid To:</b> {timing.get('end', '-')}<br>
#           <b>Duration:</b> {timing.get('duration', '-')}
#         </p>

#         <hr style="border:none; border-top:1px solid #eee; margin:20px 0;"/>
#         <p style="font-size:13px; color:#777;">✅ Decision: <b>{decision}</b></p>
#         <p style="font-size:12px; color:#aaa; text-align:center;">DumbledoreCapital © 2025 | AI-Powered Crypto Insights</p>
#       </div>
#     </body>
#     </html>
#     """
#     return body_html


# def send_email(to_email, subject, body_text=None, body_html=None):
#     if body_html is None and body_text is None:
#         raise ValueError("Either body_text or body_html must be provided")

#     if body_html is None:
#         body_html = f"<html><body>{body_text}</body></html>"

#     try:
#         response = ses_client.send_email(
#             Source=SENDER,
#             Destination={"ToAddresses": [to_email]},
#             Message={
#                 "Subject": {"Data": subject},
#                 "Body": {
#                     "Html": {"Data": body_html},
#                     "Text": {"Data": body_text or 'HTML Email'},
#                 },
#             },
#         )
#         print(f"[SES] Email sent to {to_email}, MessageId: {response['MessageId']}")
#         return True
#     except ClientError as e:
#         print(f"[SES] Failed to send email: {e.response['Error']['Message']}")
#         return False


# # Quick local test
# if __name__ == "__main__":
#     # Fake data for preview
#     test_signal = {
#         "symbol": "ETH",
#         "interval": "1h",
#         "ltf": "30m",
#         "htf": "4h",
#         "signal": "BUY",
#         "confidence": 69,
#         "price": 4544.50,  # Added entry price
#         "sentiment": "neutral",
#         "indicators": {
#             "30m": {"macd": "bullish", "rsi_value": 73.6, "rsi_signal": "neutral", "bb": "within_range", "volatility": "medium"},
#             "1h": {"macd": "bullish", "rsi_value": 70.3, "rsi_signal": "neutral", "bb": "within_range", "volatility": "medium"},
#             "4h": {"macd": "bullish", "rsi_value": 74.2, "rsi_signal": "neutral", "bb": "breakout_up", "volatility": "low"},
#         },
#         "risk": {
#             "risk_reward_label": "1:2.7",
#             "suggested_stop_loss": 4536.94,
#             "suggested_take_profit": 4792.57,
#             "expected_profit_percent": 4.05,
#             "risk_level": "low"
#         },
#         "decision": "APPROVED",
#         "timing": {"start": "2025-10-05 08:00:00", "end": "2025-10-05 12:48:00", "duration": "~288 minutes"}
#     }

#     html = format_signal_email(test_signal)
#     send_email("dhanurk25@gmail.com", "🚀 ETH Signal Alert - BUY", body_html=html)

