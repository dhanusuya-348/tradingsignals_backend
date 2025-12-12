
# auto_twitter_poster.py
# Run this as a separate service (systemd, cronjob, or docker container)

import sys
import time
from datetime import datetime, timedelta
from threading import Thread
from typing import Optional

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

# Rate limiting
POSTS_PER_WINDOW = 15  # Twitter API limit (adjust based on your tier)
WINDOW_SECONDS = 900   # 15 minutes = 900 seconds
RETRY_AFTER_429 = 3600 # Wait 1 hour after 429 error

class RateLimiter:
    def __init__(self, max_requests, window_seconds):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = []
    
    def can_proceed(self):
        """Check if we can make a request"""
        now = time.time()
        # Remove old requests outside the window
        self.requests = [req_time for req_time in self.requests if now - req_time < self.window_seconds]
        return len(self.requests) < self.max_requests
    
    def record_request(self):
        """Record that we made a request"""
        self.requests.append(time.time())
    
    def wait_if_needed(self):
        """Wait until we can make another request"""
        while not self.can_proceed():
            oldest = min(self.requests)
            wait_time = self.window_seconds - (time.time() - oldest) + 1
            print(f"[RATE_LIMIT] 🚦 Rate limited. Waiting {wait_time:.0f}s...")
            time.sleep(min(wait_time, 30))  # Sleep max 30s at a time to check other things

rate_limiter = RateLimiter(POSTS_PER_WINDOW, WINDOW_SECONDS)
last_429_time = None

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

def generate_signal_image_html(signal_data: dict) -> str:
    """
    Generate a beautiful HTML/CSS image of the signal performance.
    Returns HTML string that can be rendered to image.
    """
    is_win = signal_data['result'] == 'SUCCESS'
    color = '#10b981' if is_win else '#ef4444'  # green or red
    icon = '✓' if is_win else '✗'
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            width: 1200px;
            height: 630px;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0;
            padding: 0;
        }}
        .container {{
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 60px;
            position: relative;
            overflow: hidden;
        }}
        .bg-glow {{
            position: absolute;
            width: 500px;
            height: 500px;
            background: radial-gradient(circle, {color}22 0%, transparent 70%);
            border-radius: 50%;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 1;
        }}
        .content {{
            position: relative;
            z-index: 2;
            text-align: center;
        }}
        .result {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: {color};
            margin-bottom: 30px;
            font-size: 60px;
            color: white;
            box-shadow: 0 20px 60px {color}40;
        }}
        .symbol {{
            font-size: 72px;
            font-weight: 900;
            color: white;
            margin-bottom: 10px;
            letter-spacing: -2px;
        }}
        .stats {{
            display: flex;
            gap: 60px;
            justify-content: center;
            margin-top: 40px;
            margin-bottom: 20px;
        }}
        .stat {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .stat-label {{
            font-size: 14px;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }}
        .stat-value {{
            font-size: 36px;
            font-weight: 700;
            color: white;
            font-family: 'Monaco', monospace;
        }}
        .return {{
            color: {color};
            font-size: 42px;
        }}
        .duration {{
            font-size: 14px;
            color: #64748b;
            margin-top: 20px;
        }}
        .branding {{
            position: absolute;
            bottom: 30px;
            right: 40px;
            font-size: 13px;
            color: #475569;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
    </style>
</head>
<body>
    <div class="bg-glow"></div>
    <div class="container">
        <div class="content">
            <div class="result">{icon}</div>
            <div class="symbol">${{signal_data['symbol']}}</div>
            
            <div class="stats">
                <div class="stat">
                    <div class="stat-label">Entry</div>
                    <div class="stat-value">${{signal_data['entry_price']:.4f}}</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Exit</div>
                    <div class="stat-value">${{signal_data['exit_price']:.4f}}</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Return</div>
                    <div class="stat-value return">{signal_data['return_percent']:.2f}%</div>
                </div>
            </div>
            
            <div class="stat">
                <div class="stat-label">Profit/Loss</div>
                <div class="stat-value" style="color: {color}">${{{signal_data['profit_usd']:.2f}}}</div>
            </div>
            
            <div class="duration">
                Trade Duration: {signal_data['duration_minutes']} minutes
            </div>
        </div>
        <div class="branding">Trading Signal</div>
    </div>
</body>
</html>"""

def post_to_twitter(signal_data):
    """
    Post a single signal performance to Twitter with an image.
    Returns True if successful.
    """
    global last_429_time
    
    if not twitter_service:
        print(f"[TWITTER] ⚠️  Twitter service not available")
        return False
    
    # Check if we're still in cooldown from 429
    if last_429_time:
        time_since_429 = time.time() - last_429_time
        if time_since_429 < RETRY_AFTER_429:
            wait_time = RETRY_AFTER_429 - time_since_429
            print(f"[TWITTER] ⏳ In 429 cooldown. Waiting {wait_time:.0f}s before retry...")
            return False
    
    # Check rate limit
    rate_limiter.wait_if_needed()
    
    try:
        print(f"\n[TWITTER] 📡 Posting {signal_data['symbol']} {signal_data['result']}...")
        print(f"[TWITTER]   Entry: ${signal_data['entry_price']:.4f} → Exit: ${signal_data['exit_price']:.4f}")
        print(f"[TWITTER]   Return: {signal_data['return_percent']:.2f}% | P&L: ${signal_data['profit_usd']:.2f}")
        
        # Generate image HTML
        html_content = generate_signal_image_html(signal_data)
        
        # Post with image
        tweet_id = twitter_service.post_signal_performance_with_image(
            symbol=signal_data['symbol'],
            entry_price=signal_data['entry_price'],
            exit_price=signal_data['exit_price'],
            return_percent=signal_data['return_percent'],
            profit_usd=signal_data['profit_usd'],
            result=signal_data['result'],
            duration_minutes=signal_data['duration_minutes'],
            image_html=html_content
        )
        
        if tweet_id:
            print(f"[TWITTER] ✅ Posted! Tweet ID: {tweet_id}")
            rate_limiter.record_request()
            last_429_time = None  # Reset cooldown on success
            return True
        else:
            print(f"[TWITTER] ❌ API returned None")
            return False
            
    except Exception as e:
        error_msg = str(e)
        
        # Check if it's a 429 error
        if '429' in error_msg or 'Too Many Requests' in error_msg:
            print(f"[TWITTER] 🚨 Hit rate limit (429). Entering cooldown...")
            last_429_time = time.time()
            return False
        
        print(f"[TWITTER] ❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def auto_post_signals():
    """
    Main loop: Find old completed signals and post them to Twitter.
    Only posts signals that are 5+ hours old (like homepage).
    """
    print(f"[{datetime.utcnow()}] 🚀 Twitter Auto-Poster started\n")
    
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
                    .limit(3)\
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
                            
                            # Longer delay between tweets to avoid rate limits
                            time.sleep(5)
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