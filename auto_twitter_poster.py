# auto_twitter_poster.py
# Run this as a separate service (systemd, cronjob, or docker container)
# This version:
# - Only posts signals 5+ hours old
# - Respects rate limits with smart backoff
# - Starts fresh from Dec 12 02:30 UTC (ignores older signals)
# - Has delays between tweets to avoid API limits

import sys
import time
import json
from datetime import datetime, timedelta

sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

# Load environment
try:
    from load_env import load_env_file
    load_env_file()
    print(f"[{datetime.utcnow()}] ✅ Loaded .env variables")
except ImportError:
    print(f"[{datetime.utcnow()}] ⚠️ load_env.py not found, using system env vars")

from models import get_session_context, Signal, SignalPerformance
from twitter_service import TwitterService, RateLimitError

# Initialize Twitter
twitter_service = None
try:
    twitter_service = TwitterService()
    if twitter_service.test_connection():
        print(f"[{datetime.utcnow()}] ✅ Twitter service connected!\n")
    else:
        twitter_service = None
except Exception as e:
    print(f"[{datetime.utcnow()}] ❌ Twitter init failed: {e}\n")
    twitter_service = None

# State files
STATE_FILE = "/tmp/twitter_poster_last_id.txt"
RATE_LIMIT_FILE = "/tmp/twitter_rate_limit.txt"

# Configuration
CHECK_INTERVAL = 120  # Check every 2 minutes
MIN_DELAY_BETWEEN_TWEETS = 8  # 8 seconds between tweets (safe margin)
MIN_SIGNAL_AGE_HOURS = 5  # Only post signals 5+ hours old
CUTOFF_DATE = datetime(2025, 12, 12, 2, 30, 0)  # Dec 12 02:30 UTC - START FRESH FROM HERE

def initialize_last_posted_id():
    """
    Initialize the last posted ID by finding the highest signal ID 
    created BEFORE the cutoff date. This ensures we skip all old signals.
    """
    try:
        with open(STATE_FILE, "r") as f:
            saved_id = int(f.read().strip())
            if saved_id > 0:
                print(f"[INIT] Using saved last_posted_id: {saved_id}")
                return saved_id
    except:
        pass
    
    # Find highest signal ID before cutoff
    print(f"[INIT] Finding highest signal ID before {CUTOFF_DATE}...")
    try:
        with get_session_context() as session:
            old_signal = session.query(Signal.id)\
                .filter(Signal.created_at < CUTOFF_DATE)\
                .order_by(Signal.id.desc())\
                .first()
            
            if old_signal:
                max_old_id = old_signal[0]
                print(f"[INIT] Found max old signal ID: {max_old_id}")
                save_last_posted_id(max_old_id)
                return max_old_id
            else:
                print(f"[INIT] No signals before cutoff, starting from 0")
                return 0
    except Exception as e:
        print(f"[INIT] Error finding cutoff: {e}, defaulting to 0")
        return 0

def load_last_posted_id():
    """Load the ID of the last signal we posted to Twitter"""
    try:
        with open(STATE_FILE, "r") as f:
            return int(f.read().strip())
    except:
        return 0

def save_last_posted_id(signal_id):
    """Save the last posted signal ID"""
    try:
        with open(STATE_FILE, "w") as f:
            f.write(str(signal_id))
    except Exception as e:
        print(f"[ERROR] Failed to save state: {e}")

def get_rate_limit_reset_time():
    """Get when rate limit resets (if any)"""
    try:
        with open(RATE_LIMIT_FILE, "r") as f:
            return float(f.read().strip())
    except:
        return None

def save_rate_limit_reset_time(reset_time):
    """Save rate limit reset time"""
    try:
        with open(RATE_LIMIT_FILE, "w") as f:
            f.write(str(reset_time))
    except Exception as e:
        print(f"[ERROR] Failed to save rate limit: {e}")

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
        # Rate limit has expired, clean up
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
            'result': perf.result,  # SUCCESS or FAILURE
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
            print(f"[TWITTER] ⚠️  API returned None")
            return False, False
    
    except RateLimitError as e:
        print(f"[TWITTER] 🚫 RATE LIMIT HIT!")
        set_rate_limit(e.reset_time)
        reset_dt = datetime.fromtimestamp(e.reset_time)
        print(f"[TWITTER] ⏳ Rate limit will reset at {reset_dt}")
        return False, True  # Retry later
            
    except Exception as e:
        print(f"[TWITTER] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False, False

def auto_post_signals():
    """
    Main loop: Find completed signals and post them to Twitter.
    Only posts signals that are 5+ hours old AND created after Dec 12 02:30 UTC.
    Respects rate limits with smart backoff.
    """
    print(f"[{datetime.utcnow()}] 🚀 Twitter Auto-Poster started")
    print(f"[CONFIG] Cutoff date (ignore before): {CUTOFF_DATE} UTC")
    print(f"[CONFIG] Minimum signal age: {MIN_SIGNAL_AGE_HOURS} hours")
    print(f"[CONFIG] Check interval: {CHECK_INTERVAL} seconds")
    print(f"[CONFIG] Delay between tweets: {MIN_DELAY_BETWEEN_TWEETS} seconds\n")
    
    # Initialize - find cutoff point on first run
    last_posted_id = initialize_last_posted_id()
    print(f"[STARTUP] Starting from signal ID: {last_posted_id}\n")
    
    while True:
        try:
            # Check if we're rate limited
            is_limited, wait_seconds = check_rate_limit()
            if is_limited:
                wait_minutes = wait_seconds / 60
                print(f"[RATE_LIMITED] ⏳ Rate limited for {wait_minutes:.1f} more minutes")
                print(f"[RATE_LIMITED] Sleeping for {min(wait_seconds, 300):.0f}s...\n")
                time.sleep(min(wait_seconds, 300))  # Check again in max 5 min
                continue
            
            now = datetime.utcnow()
            min_age_threshold = now - timedelta(hours=MIN_SIGNAL_AGE_HOURS)
            
            print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Scanning for signals...")
            print(f"[FILTER] Created after: {CUTOFF_DATE}")
            print(f"[FILTER] Older than: {min_age_threshold}\n")
            
            with get_session_context() as session:
                # Find signals that:
                # 1. Are 5+ hours old
                # 2. Created AFTER Dec 12 02:30 UTC (ignore old signals)
                # 3. Have performance data (completed)
                # 4. Haven't been posted yet
                
                completed_perfs = session.query(SignalPerformance)\
                    .join(Signal, Signal.id == SignalPerformance.signal_id)\
                    .filter(Signal.created_at >= CUTOFF_DATE)\
                    .filter(Signal.created_at <= min_age_threshold)\
                    .filter(SignalPerformance.id > last_posted_id)\
                    .order_by(SignalPerformance.id.asc())\
                    .limit(1)\
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
                            print(f"[SAVED] State updated: last_posted_id={last_posted_id}")
                            
                            # Delay before next tweet (to avoid rate limits)
                            print(f"[DELAY] Waiting {MIN_DELAY_BETWEEN_TWEETS}s before next tweet...\n")
                            time.sleep(MIN_DELAY_BETWEEN_TWEETS)
                        
                        elif should_retry:
                            # Hit rate limit - stop and wait
                            print(f"[STOP] Stopping to respect rate limit\n")
                            break
                        
                        else:
                            # Non-retriable error - skip this signal
                            print(f"[SKIP] Skipping signal {perf.id} due to error\n")
                            last_posted_id = max(last_posted_id, perf.id)
                            save_last_posted_id(last_posted_id)
                else:
                    print(f"[INFO] No signals ready. Sleeping {CHECK_INTERVAL}s...\n")
        
        except Exception as e:
            print(f"[ERROR] Loop failed: {e}")
            import traceback
            traceback.print_exc()
            print(f"[ERROR] Sleeping {CHECK_INTERVAL}s before retry...\n")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    auto_post_signals()


# # auto_twitter_poster.py
# # FIXED VERSION WITH PROPER RATE LIMIT HANDLING

# import sys
# import time
# from datetime import datetime, timedelta
# from threading import Thread
# import json

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

# # State files
# STATE_FILE = "/tmp/twitter_poster_last_id.txt"
# RATE_LIMIT_FILE = "/tmp/twitter_rate_limit.txt"
# CHECK_INTERVAL = 60
# MIN_DELAY_BETWEEN_TWEETS = 5  # 5 seconds between tweets

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

# def get_rate_limit_reset_time():
#     """Get when rate limit resets (if any)"""
#     try:
#         with open(RATE_LIMIT_FILE, "r") as f:
#             return float(f.read().strip())
#     except:
#         return None

# def save_rate_limit_reset_time(reset_time):
#     """Save rate limit reset time"""
#     with open(RATE_LIMIT_FILE, "w") as f:
#         f.write(str(reset_time))

# def check_rate_limit():
#     """
#     Check if we're currently rate limited.
#     Returns (is_limited, seconds_to_wait)
#     """
#     reset_time = get_rate_limit_reset_time()
#     if not reset_time:
#         return False, 0
    
#     now = datetime.utcnow().timestamp()
#     if now < reset_time:
#         wait_seconds = reset_time - now
#         return True, wait_seconds
#     else:
#         # Rate limit has expired
#         try:
#             import os
#             os.remove(RATE_LIMIT_FILE)
#         except:
#             pass
#         return False, 0

# def set_rate_limit(reset_timestamp):
#     """Set rate limit expiry"""
#     save_rate_limit_reset_time(reset_timestamp)

# def get_signal_with_performance(session, perf):
#     """
#     Get signal + performance data in one go.
#     Returns dict with all info needed to post to Twitter.
#     """
#     try:
#         signal = session.query(Signal).filter_by(id=perf.signal_id).first()
#         if not signal:
#             return None
        
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
#             'result': perf.result,
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
#     Returns (success: bool, should_retry: bool)
#     """
#     if not twitter_service:
#         print(f"[TWITTER] ⚠️  Twitter service not available")
#         return False, False
    
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
#             return True, False
#         else:
#             print(f"[TWITTER] ⚠️  API returned None - might be rate limited")
#             return False, True
            
#     except Exception as e:
#         error_str = str(e).lower()
        
#         # Check if it's a rate limit error
#         if "429" in str(e) or "too many requests" in error_str or "rate limit" in error_str:
#             print(f"[TWITTER] 🚫 RATE LIMIT HIT: {e}")
            
#             # Twitter usually tells us when limit resets (in HTTP headers)
#             # Default to 15 minutes if we don't know
#             reset_time = datetime.utcnow().timestamp() + (15 * 60)
#             set_rate_limit(reset_time)
#             print(f"[TWITTER] ⏳ Rate limit will reset at {datetime.fromtimestamp(reset_time)}")
            
#             return False, True  # Retry later
        
#         # Other errors - don't retry, skip this signal
#         print(f"[TWITTER] ❌ Non-recoverable error: {e}")
#         import traceback
#         traceback.print_exc()
#         return False, False

# def auto_post_signals():
#     """
#     Main loop: Find old completed signals and post them to Twitter.
#     Only posts signals that are 5+ hours old.
#     Respects rate limits intelligently.
#     """
#     print(f"[{datetime.utcnow()}] 🚀 Twitter Auto-Poster started\n")
    
#     last_posted_id = load_last_posted_id()
#     print(f"[STARTUP] Last posted signal ID: {last_posted_id}\n")
    
#     while True:
#         try:
#             # Check if we're rate limited
#             is_limited, wait_seconds = check_rate_limit()
#             if is_limited:
#                 wait_minutes = wait_seconds / 60
#                 print(f"[RATE_LIMITED] ⏳ Still rate limited. Waiting {wait_minutes:.1f} more minutes...\n")
#                 time.sleep(min(wait_seconds, 300))  # Sleep max 5 min at a time, recheck
#                 continue
            
#             now = datetime.utcnow()
#             five_hours_ago = now - timedelta(hours=5)
            
#             print(f"[{now}] 🔍 Scanning for signals older than {five_hours_ago}...")
            
#             with get_session_context() as session:
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
#                             save_last_posted_id(last_posted_id)
#                             continue
                        
#                         # Try to post
#                         success, should_retry = post_to_twitter(signal_data)
                        
#                         if success:
#                             # Update state and continue
#                             last_posted_id = perf.id
#                             save_last_posted_id(last_posted_id)
#                             print(f"[SAVED] State: last_posted_id={last_posted_id}\n")
                            
#                             # Delay between tweets (5 seconds)
#                             time.sleep(MIN_DELAY_BETWEEN_TWEETS)
                        
#                         elif should_retry:
#                             # Hit rate limit or retriable error - stop processing
#                             print(f"[RETRY] Will retry this signal next loop\n")
#                             break
                        
#                         else:
#                             # Non-retriable error - skip this signal
#                             print(f"[SKIP] Skipping failed signal {perf.id}\n")
#                             last_posted_id = max(last_posted_id, perf.id)
#                             save_last_posted_id(last_posted_id)
#                 else:
#                     print(f"[INFO] No signals found, sleeping...\n")
        
#         except Exception as e:
#             print(f"[ERROR] Loop failed: {e}")
#             import traceback
#             traceback.print_exc()
        
#         time.sleep(CHECK_INTERVAL)

# if __name__ == "__main__":
#     auto_post_signals()