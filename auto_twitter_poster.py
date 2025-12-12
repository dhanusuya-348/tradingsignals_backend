# auto_twitter_poster.py
# Run this as a separate service (systemd, cronjob, or docker container)

import sys
import time
from datetime import datetime, timedelta
from threading import Thread

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
RATE_LIMITED_INTERVAL = 900  # 15 minutes when rate limited

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

def post_to_twitter(signal_data):
    """
    Post a single signal performance to Twitter.
    Returns True if successful.
    """
    if not twitter_service:
        print(f"[TWITTER] ⚠️  Twitter service not available")
        return False
    
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
                            
                            # Delay between tweets to avoid rate limits
                            time.sleep(5)
                        else:
                            # Stop processing on failure (will retry next loop)
                            print(f"[RETRY] Will retry this signal next loop\n")
                            # If rate limited, wait longer before next check
                            if hasattr(twitter_service, 'rate_limit_reset') and twitter_service.rate_limit_reset > time.time():
                                remaining = twitter_service.rate_limit_reset - time.time()
                                print(f"[RATE_LIMITED] Sleeping for {remaining/60:.1f} minutes...")
                                time.sleep(min(remaining, RATE_LIMITED_INTERVAL))
                            break
                else:
                    print(f"[INFO] No signals found, sleeping...\n")
        
        except Exception as e:
            print(f"[ERROR] Loop failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Adjust sleep interval based on rate limiting
        sleep_interval = CHECK_INTERVAL
        if twitter_service and hasattr(twitter_service, 'rate_limit_reset') and twitter_service.rate_limit_reset > time.time():
            remaining = twitter_service.rate_limit_reset - time.time()
            sleep_interval = min(remaining, RATE_LIMITED_INTERVAL)
            print(f"[RATE_LIMITED] Next check in {sleep_interval/60:.1f} minutes...")
        
        time.sleep(sleep_interval)

if __name__ == "__main__":
    auto_post_signals()