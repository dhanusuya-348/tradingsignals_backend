else:
                    print(f"[INFO] No signals found, sleeping...\n")
        
        except Exception as e:
            print(f"[ERROR] Loop failed: {e}")
            import traceback
            traceback.print_exc()
            # Wait longer on error to avoid hammering API
            time.sleep(CHECK_INTERVAL * 2)
            continue
        
        time.sleep(CHECK_INTERVAL)# auto_twitter_poster.py
# Run this as a separate service (systemd, cronjob, or docker container)

import sys
import time
from datetime import datetime, timedelta
from threading import Thread
import io
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# Load environment
try:
    from load_env import load_env_file
    load_env_file()
    print(f"[{datetime.utcnow()}] ✅ Loaded .env variables")
except ImportError:
    print(f"[{datetime.utcnow()}] ⚠️ load_env.py not found, using system env vars")

from models import get_session_context, Signal, SignalPerformance
from twitter_service import TwitterService
import json
import os
import boto3

# Initialize Twitter
twitter_service = None
try:
    twitter_service = TwitterService()
    if twitter_service.test_connection():
        print(f"[{datetime.utcnow()}] ✅ Twitter service connected!")
    else:
        twitter_service = None
except Exception as e:
    print(f"[{datetime.utcnow()}] ❌ Twitter init failed: {e}")
    twitter_service = None

# State file to track last posted signal
STATE_FILE = "/tmp/twitter_poster_last_id.txt"
CHECK_INTERVAL = 60  # Check every 60 seconds
TWEET_DELAY = 5  # Seconds between tweets (avoid rate limit)

def load_last_posted_id():
    """Load the ID of the last signal we posted to Twitter"""
    try:
        with open(STATE_FILE, "r") as f:
            return int(f.read().strip())
    except:
        return 0

def save_last_posted_id(signal_id):
    """Save the last posted signal ID"""
    with open(STATE_FILE, "w") as f:
        f.write(str(signal_id))

def get_signal_with_performance(session, perf):
    """
    Get signal + performance data in one go.
    Returns dict with all info needed to post to Twitter.
    """
    try:
        # Get the signal
        signal = session.query(Signal).filter_by(id=perf.signal_id).first()
        if not signal:
            return None
        
        # Extract entry price from signal payload
        payload = signal.payload or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        
        entry_price = None
        if 'price' in payload:
            entry_price = float(payload['price'])
        elif 'risk' in payload and 'entry_price' in payload['risk']:
            entry_price = float(payload['risk']['entry_price'])
        
        if not entry_price:
            return None
        
        return {
            'signal_id': signal.id,
            'symbol': signal.symbol,
            'entry_price': entry_price,
            'exit_price': float(perf.exit_price) if perf.exit_price else 0,
            'return_percent': float(perf.return_percent) if perf.return_percent else 0,
            'profit_usd': float(perf.profit_usd) if perf.profit_usd else 0,
            'result': perf.result,  # SUCCESS or FAILURE
            'duration_minutes': perf.duration_minutes or 0,
            'created_at': signal.created_at,
            'completed_at': perf.tracked_at
        }
    except Exception as e:
        print(f"[ERROR] Failed to extract signal data: {e}")
        return None

def generate_signal_image(signal_data):
    """
    Generate a beautiful aesthetic image for the signal performance.
    Returns path to saved image.
    """
    try:
        # Image dimensions
        width, height = 1200, 630  # Twitter card size
        
        # Colors
        bg_color = (15, 23, 42)  # Dark blue-black
        accent_color = (6, 182, 212)  # Cyan
        success_color = (34, 197, 94)  # Green
        failure_color = (239, 68, 68)  # Red
        text_light = (226, 232, 240)  # Light gray
        text_muted = (148, 163, 184)  # Muted gray
        
        # Create image
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Try to use nice fonts, fallback to default
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
            large_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
            normal_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
        except:
            # Fallback to default font
            title_font = large_font = normal_font = small_font = ImageFont.load_default()
        
        # Draw gradient-like background (top darker, bottom slightly lighter)
        for y in range(height):
            intensity = int(15 + (y / height) * 10)
            draw.line([(0, y), (width, y)], fill=(intensity, intensity+8, intensity+27))
        
        # Draw accent line at top
        draw.rectangle([(0, 0), (width, 4)], fill=accent_color)
        
        # Result badge (top right)
        is_success = signal_data['result'] == 'SUCCESS'
        badge_color = success_color if is_success else failure_color
        badge_text = "✓ WIN" if is_success else "✗ LOSS"
        
        draw.rectangle([(width - 280, 40), (width - 40, 100)], fill=badge_color)
        draw.text((width - 160, 70), badge_text, fill=(255, 255, 255), font=normal_font, anchor="mm")
        
        # Symbol (large, left side)
        draw.text((80, 130), signal_data['symbol'], fill=accent_color, font=title_font, anchor="lm")
        
        # Signal type
        signal_type = signal_data['result']
        draw.text((80, 200), f"Signal: {signal_type}", fill=text_muted, font=small_font, anchor="lm")
        
        # Entry → Exit (middle section)
        entry_text = f"Entry: ${signal_data['entry_price']:.4f}"
        exit_text = f"Exit: ${signal_data['exit_price']:.4f}"
        
        draw.text((80, 300), entry_text, fill=text_light, font=normal_font, anchor="lm")
        draw.text((80, 380), exit_text, fill=text_light, font=normal_font, anchor="lm")
        
        # Return % (large, right side)
        return_text = f"{signal_data['return_percent']:+.2f}%"
        return_color = success_color if signal_data['return_percent'] >= 0 else failure_color
        draw.text((width - 100, 320), return_text, fill=return_color, font=title_font, anchor="rm")
        
        # P&L amount
        pnl_text = f"P&L: ${signal_data['profit_usd']:+.2f}"
        draw.text((width - 100, 420), pnl_text, fill=return_color, font=normal_font, anchor="rm")
        
        # Duration (bottom left)
        duration_text = f"⏱ {signal_data['duration_minutes']} min"
        draw.text((80, height - 80), duration_text, fill=text_muted, font=small_font, anchor="lm")
        
        # Timestamp (bottom right)
        time_text = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        draw.text((width - 80, height - 80), time_text, fill=text_muted, font=small_font, anchor="rm")
        
        # DollaRaptor branding (bottom center)
        draw.text((width // 2, height - 30), "DollaRaptor Trading Signals", fill=accent_color, font=small_font, anchor="mm")
        
        # Save image
        img_path = f"/tmp/signal_{signal_data['symbol']}_{signal_data['signal_id']}.png"
        img.save(img_path)
        
        print(f"[IMAGE] ✅ Generated: {img_path}")
        return img_path
        
    except Exception as e:
        print(f"[IMAGE] ❌ Failed to generate image: {e}")
        import traceback
        traceback.print_exc()
        return None

def upload_image_to_s3(img_path):
    """
    Upload image to S3 and return the URL.
    """
    try:
        s3_client = boto3.client(
            's3',
            region_name=os.environ.get('AWS_REGION', 'ap-southeast-2'),
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
        )
        
        bucket_name = os.environ.get('S3_BUCKET_NAME', 'tradingsignals-pdfs')
        file_name = f"twitter-signals/{os.path.basename(img_path)}"
        
        s3_client.upload_file(img_path, bucket_name, file_name)
        
        # Generate presigned URL (valid for 24 hours)
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': file_name},
            ExpiresIn=86400
        )
        
        print(f"[S3] ✅ Uploaded to: {url}")
        return url
        
    except Exception as e:
        print(f"[S3] ⚠️ Upload failed, posting without image: {e}")
        return None

def post_to_twitter(signal_data):
    """
    Post a single signal performance to Twitter with image.
    Returns True if successful.
    """
    if not twitter_service:
        print(f"[TWITTER] ⚠️  Twitter service not available")
        return False
    
    try:
        print(f"\n[TWITTER] 📡 Posting {signal_data['symbol']} {signal_data['result']}...")
        print(f"[TWITTER]   Entry: ${signal_data['entry_price']:.4f} → Exit: ${signal_data['exit_price']:.4f}")
        print(f"[TWITTER]   Return: {signal_data['return_percent']:.2f}% | P&L: ${signal_data['profit_usd']:.2f}")
        
        # Generate beautiful image
        print(f"[IMAGE] 🎨 Generating signal image...")
        img_path = generate_signal_image(signal_data)
        
        # Try to upload to S3 (optional, for image attachment)
        img_url = None
        if img_path and os.path.exists(img_path):
            print(f"[S3] 📤 Uploading image to S3...")
            img_url = upload_image_to_s3(img_path)
        
        # Create tweet text (with or without image)
        if signal_data['return_percent'] >= 0:
            emoji = "🟢"
        else:
            emoji = "🔴"
        
        tweet_text = f"""{emoji} SIGNAL COMPLETED

{signal_data['symbol']} {signal_data['result']}
Entry: ${signal_data['entry_price']:.4f}
Exit: ${signal_data['exit_price']:.4f}

Return: {signal_data['return_percent']:+.2f}%
P&L: ${signal_data['profit_usd']:+.2f}

Duration: {signal_data['duration_minutes']}m

#Trading #Crypto #DollaRaptor"""
        
        # Post to Twitter
        tweet_id = twitter_service.post_signal_performance(
            symbol=signal_data['symbol'],
            entry_price=signal_data['entry_price'],
            exit_price=signal_data['exit_price'],
            return_percent=signal_data['return_percent'],
            profit_usd=signal_data['profit_usd'],
            result=signal_data['result'],
            duration_minutes=signal_data['duration_minutes']
        )
        
        if tweet_id:
            print(f"[TWITTER] ✅ Posted! Tweet ID: {tweet_id}")
            if img_path and os.path.exists(img_path):
                os.remove(img_path)
            return True
        else:
            print(f"[TWITTER] ❌ API returned None")
            return False
            
    except Exception as e:
        print(f"[TWITTER] ❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def auto_post_signals():
    """
    Main loop: Find old completed signals and post them to Twitter.
    Only posts signals that are 5+ hours old (like homepage).
    """
    print(f"[{datetime.utcnow()}] 🚀 Twitter Auto-Poster started (Aesthetic Mode)\n")
    
    last_posted_id = load_last_posted_id()
    print(f"[STARTUP] Last posted signal ID: {last_posted_id}\n")
    
    while True:
        try:
            now = datetime.utcnow()
            five_hours_ago = now - timedelta(hours=5)
            
            print(f"[{now}] 🔍 Scanning for signals older than {five_hours_ago}...")
            
            with get_session_context() as session:
                # Find signals that:
                # 1. Are 5+ hours old (created before five_hours_ago)
                # 2. Have performance data (completed)
                # 3. Haven't been posted yet (ID > last_posted_id)
                
                completed_perfs = session.query(SignalPerformance)\
                    .join(Signal, Signal.id == SignalPerformance.signal_id)\
                    .filter(Signal.created_at <= five_hours_ago)\
                    .filter(SignalPerformance.id > last_posted_id)\
                    .order_by(SignalPerformance.id.asc())\
                    .limit(5)\
                    .all()
                
                if completed_perfs:
                    print(f"[FOUND] {len(completed_perfs)} signal(s) ready to post\n")
                    
                    for perf in completed_perfs:
                        # Extract all data
                        signal_data = get_signal_with_performance(session, perf)
                        
                        if not signal_data:
                            print(f"[SKIP] SignalPerf {perf.id}: Could not extract data")
                            last_posted_id = max(last_posted_id, perf.id)
                            continue
                        
                        # Try to post
                        success = post_to_twitter(signal_data)
                        
                        if success:
                            # Move forward only on success
                            last_posted_id = perf.id
                            save_last_posted_id(last_posted_id)
                            print(f"[SAVED] State: last_posted_id={last_posted_id}\n")
                            
                            # Delay between tweets (respect rate limits)
                            print(f"[DELAY] ⏳ Waiting {TWEET_DELAY}s before next tweet...\n")
                            time.sleep(TWEET_DELAY)
                        else:
                            # Stop processing on failure (will retry next loop)
                            print(f"[RETRY] Will retry this signal next loop\n")
                            break
                else:
                    print(f"[INFO] No signals found, sleeping...\n")
        
        except Exception as e:
            print(f"[ERROR] Loop failed: {e}")
            import traceback
            traceback.print_exc()
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    auto_post_signals()

# # auto_twitter_poster.py
# # Run this as a separate service (systemd, cronjob, or docker container)

# import sys
# import time
# from datetime import datetime, timedelta
# from threading import Thread

# sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# # Load environment
# try:
#     from load_env import load_env_file
#     load_env_file()
#     print(f"[{datetime.utcnow()}] ✅ Loaded .env variables")
# except ImportError:
#     print(f"[{datetime.utcnow()}] ⚠️ load_env.py not found, using system env vars")

# from models import get_session_context, Signal, SignalPerformance
# from twitter_service import TwitterService
# import json

# # Initialize Twitter
# twitter_service = None
# try:
#     twitter_service = TwitterService()
#     if twitter_service.test_connection():
#         print(f"[{datetime.utcnow()}] ✅ Twitter service connected!")
#     else:
#         twitter_service = None
# except Exception as e:
#     print(f"[{datetime.utcnow()}] ❌ Twitter init failed: {e}")
#     twitter_service = None

# # State file to track last posted signal
# STATE_FILE = "/tmp/twitter_poster_last_id.txt"
# CHECK_INTERVAL = 60  # Check every 60 seconds

# def load_last_posted_id():
#     """Load the ID of the last signal we posted to Twitter"""
#     try:
#         with open(STATE_FILE, "r") as f:
#             return int(f.read().strip())
#     except:
#         return 0

# def save_last_posted_id(signal_id):
#     """Save the last posted signal ID"""
#     with open(STATE_FILE, "w") as f:
#         f.write(str(signal_id))

# def get_signal_with_performance(session, perf):
#     """
#     Get signal + performance data in one go.
#     Returns dict with all info needed to post to Twitter.
#     """
#     try:
#         # Get the signal
#         signal = session.query(Signal).filter_by(id=perf.signal_id).first()
#         if not signal:
#             return None
        
#         # Extract entry price from signal payload
#         payload = signal.payload or {}
#         if isinstance(payload, str):
#             payload = json.loads(payload)
        
#         entry_price = None
#         if 'price' in payload:
#             entry_price = float(payload['price'])
#         elif 'risk' in payload and 'entry_price' in payload['risk']:
#             entry_price = float(payload['risk']['entry_price'])
        
#         if not entry_price:
#             return None
        
#         return {
#             'signal_id': signal.id,
#             'symbol': signal.symbol,
#             'entry_price': entry_price,
#             'exit_price': float(perf.exit_price) if perf.exit_price else 0,
#             'return_percent': float(perf.return_percent) if perf.return_percent else 0,
#             'profit_usd': float(perf.profit_usd) if perf.profit_usd else 0,
#             'result': perf.result,  # SUCCESS or FAILURE
#             'duration_minutes': perf.duration_minutes or 0,
#             'created_at': signal.created_at,
#             'completed_at': perf.tracked_at
#         }
#     except Exception as e:
#         print(f"[ERROR] Failed to extract signal data: {e}")
#         return None

# def post_to_twitter(signal_data):
#     """
#     Post a single signal performance to Twitter.
#     Returns True if successful.
#     """
#     if not twitter_service:
#         print(f"[TWITTER] ⚠️  Twitter service not available")
#         return False
    
#     try:
#         print(f"\n[TWITTER] 📡 Posting {signal_data['symbol']} {signal_data['result']}...")
#         print(f"[TWITTER]   Entry: ${signal_data['entry_price']:.4f} → Exit: ${signal_data['exit_price']:.4f}")
#         print(f"[TWITTER]   Return: {signal_data['return_percent']:.2f}% | P&L: ${signal_data['profit_usd']:.2f}")
        
#         tweet_id = twitter_service.post_signal_performance(
#             symbol=signal_data['symbol'],
#             entry_price=signal_data['entry_price'],
#             exit_price=signal_data['exit_price'],
#             return_percent=signal_data['return_percent'],
#             profit_usd=signal_data['profit_usd'],
#             result=signal_data['result'],
#             duration_minutes=signal_data['duration_minutes']
#         )
        
#         if tweet_id:
#             print(f"[TWITTER] ✅ Posted! Tweet ID: {tweet_id}")
#             return True
#         else:
#             print(f"[TWITTER] ❌ API returned None")
#             return False
            
#     except Exception as e:
#         print(f"[TWITTER] ❌ Exception: {e}")
#         import traceback
#         traceback.print_exc()
#         return False

# def auto_post_signals():
#     """
#     Main loop: Find old completed signals and post them to Twitter.
#     Only posts signals that are 5+ hours old (like homepage).
#     """
#     print(f"[{datetime.utcnow()}] 🚀 Twitter Auto-Poster started\n")
    
#     last_posted_id = load_last_posted_id()
#     print(f"[STARTUP] Last posted signal ID: {last_posted_id}\n")
    
#     while True:
#         try:
#             now = datetime.utcnow()
#             five_hours_ago = now - timedelta(hours=5)
            
#             print(f"[{now}] 🔍 Scanning for signals older than {five_hours_ago}...")
            
#             with get_session_context() as session:
#                 # Find signals that:
#                 # 1. Are 5+ hours old (created before five_hours_ago)
#                 # 2. Have performance data (completed)
#                 # 3. Haven't been posted yet (ID > last_posted_id)
                
#                 completed_perfs = session.query(SignalPerformance)\
#                     .join(Signal, Signal.id == SignalPerformance.signal_id)\
#                     .filter(Signal.created_at <= five_hours_ago)\
#                     .filter(SignalPerformance.id > last_posted_id)\
#                     .order_by(SignalPerformance.id.asc())\
#                     .limit(5)\
#                     .all()
                
#                 if completed_perfs:
#                     print(f"[FOUND] {len(completed_perfs)} signal(s) ready to post\n")
                    
#                     for perf in completed_perfs:
#                         # Extract all data
#                         signal_data = get_signal_with_performance(session, perf)
                        
#                         if not signal_data:
#                             print(f"[SKIP] SignalPerf {perf.id}: Could not extract data")
#                             last_posted_id = max(last_posted_id, perf.id)
#                             continue
                        
#                         # Try to post
#                         success = post_to_twitter(signal_data)
                        
#                         if success:
#                             # Move forward only on success
#                             last_posted_id = perf.id
#                             save_last_posted_id(last_posted_id)
#                             print(f"[SAVED] State: last_posted_id={last_posted_id}\n")
                            
#                             # Small delay between tweets
#                             time.sleep(2)
#                         else:
#                             # Stop processing on failure (will retry next loop)
#                             print(f"[RETRY] Will retry this signal next loop\n")
#                             break
#                 else:
#                     print(f"[INFO] No signals found, sleeping...\n")
        
#         except Exception as e:
#             print(f"[ERROR] Loop failed: {e}")
#             import traceback
#             traceback.print_exc()
        
#         time.sleep(CHECK_INTERVAL)

# if __name__ == "__main__":
#     auto_post_signals()