# auto_twitter_poster.py
# FIXED VERSION WITH PROPER RATE LIMIT HANDLING

import sys
import time
from datetime import datetime, timedelta
from threading import Thread
import json

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

# State files
STATE_FILE = "/tmp/twitter_poster_last_id.txt"
RATE_LIMIT_FILE = "/tmp/twitter_rate_limit.txt"
CHECK_INTERVAL = 60
MIN_DELAY_BETWEEN_TWEETS = 5  # 5 seconds between tweets

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

def get_rate_limit_reset_time():
    """Get when rate limit resets (if any)"""
    try:
        with open(RATE_LIMIT_FILE, "r") as f:
            return float(f.read().strip())
    except:
        return None

def save_rate_limit_reset_time(reset_time):
    """Save rate limit reset time"""
    with open(RATE_LIMIT_FILE, "w") as f:
        f.write(str(reset_time))

def check_rate_limit():
    """
    Check if we're currently rate limited.
    Returns (is_limited, seconds_to_wait)
    """
    reset_time = get_rate_limit_reset_time()
    if not reset_time:
        return False, 0
    
    now = datetime.utcnow().timestamp()
    if now < reset_time:
        wait_seconds = reset_time - now
        return True, wait_seconds
    else:
        # Rate limit has expired
        try:
            import os
            os.remove(RATE_LIMIT_FILE)
        except:
            pass
        return False, 0

def set_rate_limit(reset_timestamp):
    """Set rate limit expiry"""
    save_rate_limit_reset_time(reset_timestamp)

def get_signal_with_performance(session, perf):
    """
    Get signal + performance data in one go.
    Returns dict with all info needed to post to Twitter.
    """
    try:
        signal = session.query(Signal).filter_by(id=perf.signal_id).first()
        if not signal:
            return None
        
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
            'result': perf.result,
            'duration_minutes': perf.duration_minutes or 0,
            'created_at': signal.created_at,
            'completed_at': perf.tracked_at
        }
    except Exception as e:
        print(f"[ERROR] Failed to extract signal data: {e}")
        return None

def post_to_twitter(signal_data):
    """
    Post a single signal performance to Twitter.
    Returns (success: bool, should_retry: bool)
    """
    if not twitter_service:
        print(f"[TWITTER] ⚠️  Twitter service not available")
        return False, False
    
    try:
        print(f"\n[TWITTER] 📡 Posting {signal_data['symbol']} {signal_data['result']}...")
        print(f"[TWITTER]   Entry: ${signal_data['entry_price']:.4f} → Exit: ${signal_data['exit_price']:.4f}")
        print(f"[TWITTER]   Return: {signal_data['return_percent']:.2f}% | P&L: ${signal_data['profit_usd']:.2f}")
        
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
            return True, False
        else:
            print(f"[TWITTER] ⚠️  API returned None - might be rate limited")
            return False, True
            
    except Exception as e:
        error_str = str(e).lower()
        
        # Check if it's a rate limit error
        if "429" in str(e) or "too many requests" in error_str or "rate limit" in error_str:
            print(f"[TWITTER] 🚫 RATE LIMIT HIT: {e}")
            
            # Twitter usually tells us when limit resets (in HTTP headers)
            # Default to 15 minutes if we don't know
            reset_time = datetime.utcnow().timestamp() + (15 * 60)
            set_rate_limit(reset_time)
            print(f"[TWITTER] ⏳ Rate limit will reset at {datetime.fromtimestamp(reset_time)}")
            
            return False, True  # Retry later
        
        # Other errors - don't retry, skip this signal
        print(f"[TWITTER] ❌ Non-recoverable error: {e}")
        import traceback
        traceback.print_exc()
        return False, False

def auto_post_signals():
    """
    Main loop: Find old completed signals and post them to Twitter.
    Only posts signals that are 5+ hours old.
    Respects rate limits intelligently.
    """
    print(f"[{datetime.utcnow()}] 🚀 Twitter Auto-Poster started\n")
    
    last_posted_id = load_last_posted_id()
    print(f"[STARTUP] Last posted signal ID: {last_posted_id}\n")
    
    while True:
        try:
            # Check if we're rate limited
            is_limited, wait_seconds = check_rate_limit()
            if is_limited:
                wait_minutes = wait_seconds / 60
                print(f"[RATE_LIMITED] ⏳ Still rate limited. Waiting {wait_minutes:.1f} more minutes...\n")
                time.sleep(min(wait_seconds, 300))  # Sleep max 5 min at a time, recheck
                continue
            
            now = datetime.utcnow()
            five_hours_ago = now - timedelta(hours=5)
            
            print(f"[{now}] 🔍 Scanning for signals older than {five_hours_ago}...")
            
            with get_session_context() as session:
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
                            save_last_posted_id(last_posted_id)
                            continue
                        
                        # Try to post
                        success, should_retry = post_to_twitter(signal_data)
                        
                        if success:
                            # Update state and continue
                            last_posted_id = perf.id
                            save_last_posted_id(last_posted_id)
                            print(f"[SAVED] State: last_posted_id={last_posted_id}\n")
                            
                            # Delay between tweets (5 seconds)
                            time.sleep(MIN_DELAY_BETWEEN_TWEETS)
                        
                        elif should_retry:
                            # Hit rate limit or retriable error - stop processing
                            print(f"[RETRY] Will retry this signal next loop\n")
                            break
                        
                        else:
                            # Non-retriable error - skip this signal
                            print(f"[SKIP] Skipping failed signal {perf.id}\n")
                            last_posted_id = max(last_posted_id, perf.id)
                            save_last_posted_id(last_posted_id)
                else:
                    print(f"[INFO] No signals found, sleeping...\n")
        
        except Exception as e:
            print(f"[ERROR] Loop failed: {e}")
            import traceback
            traceback.print_exc()
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    auto_post_signals()