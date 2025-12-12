import tweepy
import os
import time
from datetime import datetime
from typing import Optional

class TwitterService:
    """
    Service to handle Twitter/X.com automated posting
    for signal performance updates and summaries.
    Includes rate limit handling with exponential backoff.
    """
    
    def __init__(self):
        """Initialize Twitter API client with credentials from .env"""
        self.api_key = os.getenv('TWITTER_API_KEY')
        self.api_secret = os.getenv('TWITTER_API_SECRET')
        self.access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        
        # Validate credentials
        if not all([self.api_key, self.api_secret, self.access_token, self.access_token_secret]):
            raise ValueError("Missing Twitter API credentials in environment variables")
        
        # Initialize Tweepy client (v2 API)
        self.client = tweepy.Client(
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
            bearer_token=self.bearer_token
        )
        
        # Rate limit tracking
        self.rate_limit_reset = None
        self.requests_remaining = None
    
    def _handle_rate_limit(self, error_response):
        """
        Extract rate limit info from error response and wait appropriately.
        """
        try:
            # Check if this is a rate limit error (429)
            if hasattr(error_response, 'response'):
                headers = error_response.response.headers
                if 'x-rate-limit-reset' in headers:
                    reset_timestamp = int(headers['x-rate-limit-reset'])
                    current_time = int(time.time())
                    wait_seconds = max(reset_timestamp - current_time, 0)
                    
                    print(f"\n⏸️  RATE LIMIT HIT!")
                    print(f"   Reset at: {datetime.fromtimestamp(reset_timestamp)}")
                    print(f"   Waiting {wait_seconds} seconds...\n")
                    
                    time.sleep(wait_seconds + 2)  # Add 2 second buffer
                    return True
        except Exception as e:
            print(f"[DEBUG] Error extracting rate limit: {e}")
        
        return False
    
    def _make_request_with_backoff(self, request_func, *args, **kwargs):
        """
        Make a request with exponential backoff for rate limits.
        
        Args:
            request_func: The API call function
            *args, **kwargs: Arguments to pass to request_func
        
        Returns:
            Response from API or None if failed
        """
        max_retries = 3
        base_wait = 1  # Start with 1 second
        
        for attempt in range(max_retries):
            try:
                return request_func(*args, **kwargs)
            except tweepy.TweepyException as e:
                # Check if it's a rate limit error (429)
                if hasattr(e, 'response') and e.response.status_code == 429:
                    if self._handle_rate_limit(e):
                        # Retry after waiting
                        continue
                    else:
                        # Couldn't extract reset time, use exponential backoff
                        wait_time = base_wait * (2 ** attempt)
                        print(f"⏸️  Rate limited. Exponential backoff: waiting {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                else:
                    # Not a rate limit error, re-raise
                    raise
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                raise
        
        print("❌ Failed after all retries")
        return None
    
    def format_signal_performance(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        return_percent: float,
        profit_usd: float,
        result: str,
        duration_minutes: int
    ) -> str:
        """
        Format a signal performance update with professional styling.
        Similar to the email notification format.
        """
        # Color-coded result emoji
        if result == "SUCCESS":
            result_emoji = "✅"
            result_text = "WINNER"
            trend = "📈"
        else:
            result_emoji = "❌"
            result_text = "LOSER"
            trend = "📉"
        
        # Format values
        entry_fmt = f"${entry_price:.4f}"
        exit_fmt = f"${exit_price:.4f}"
        return_fmt = f"{return_percent:+.2f}%"
        profit_fmt = f"{profit_usd:+.2f}"
        duration_fmt = f"{duration_minutes}m"
        
        # Determine risk level
        if abs(return_percent) <= 1:
            risk_level = "LOW"
        elif abs(return_percent) <= 3:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"
        
        # Professional format similar to email
        tweet = f"""{result_emoji} {symbol}/USDT — {result_text}

{trend} Performance Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━
Entry:     {entry_fmt}
Exit:      {exit_fmt}
Duration:  {duration_fmt}

📊 Return: {return_fmt}
💰 P&L:    ${profit_fmt} USD
⚡ Risk:    {risk_level}

#Crypto #Trading #DollaRaptor"""
        
        return tweet
    
    def post_signal_performance(
        self, 
        symbol: str, 
        entry_price: float, 
        exit_price: float, 
        return_percent: float, 
        profit_usd: float, 
        result: str,
        duration_minutes: int
    ) -> Optional[str]:
        """
        Post a completed signal performance to Twitter.
        
        Args:
            symbol: Crypto symbol (e.g., 'BTC', 'ETH')
            entry_price: Entry price
            exit_price: Exit price
            return_percent: Return percentage
            profit_usd: Profit in USD
            result: 'SUCCESS' or 'FAILURE'
            duration_minutes: How long the trade lasted
        
        Returns:
            Tweet ID if successful, None if failed
        """
        tweet_text = self.format_signal_performance(
            symbol=symbol,
            entry_price=entry_price,
            exit_price=exit_price,
            return_percent=return_percent,
            profit_usd=profit_usd,
            result=result,
            duration_minutes=duration_minutes
        )
        
        # Post with rate limit handling
        response = self._make_request_with_backoff(
            self.client.create_tweet,
            text=tweet_text
        )
        
        if response:
            tweet_id = response.data['id']
            print(f"✅ Tweet posted successfully! ID: {tweet_id}")
            return tweet_id
        else:
            print(f"❌ Failed to post tweet after retries")
            return None
    
    def format_daily_performance_summary(
        self,
        total_signals: int,
        wins: int,
        losses: int,
        win_rate: float,
        total_profit: float,
        avg_return: float
    ) -> str:
        """
        Format a daily performance summary with professional styling.
        """
        # Performance indicator
        if win_rate >= 70:
            perf_emoji = "🔥"
            perf_label = "EXCELLENT"
        elif win_rate >= 50:
            perf_emoji = "🚀"
            perf_label = "SOLID"
        else:
            perf_emoji = "📊"
            perf_label = "NEUTRAL"
        
        # Format values
        win_rate_fmt = f"{win_rate:.1f}%"
        profit_fmt = f"${total_profit:+.2f}"
        avg_return_fmt = f"{avg_return:+.2f}%"
        
        tweet = f"""{perf_emoji} Daily Performance — {perf_label}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Signals: {total_signals} | ✅ {wins} | ❌ {losses}

📈 Win Rate: {win_rate_fmt}
💰 Net P&L: {profit_fmt}
📊 Avg Return: {avg_return_fmt}

Dollaraptor © 2025
#TradingSignals #Crypto"""
        
        return tweet
    
    def post_daily_performance_summary(
        self, 
        total_signals: int, 
        wins: int, 
        losses: int, 
        win_rate: float, 
        total_profit: float,
        avg_return: float
    ) -> Optional[str]:
        """
        Post a daily performance summary.
        
        Args:
            total_signals: Total signals completed today
            wins: Number of winning trades
            losses: Number of losing trades
            win_rate: Win rate percentage
            total_profit: Total profit in USD
            avg_return: Average return percentage
        
        Returns:
            Tweet ID if successful, None if failed
        """
        tweet_text = self.format_daily_performance_summary(
            total_signals=total_signals,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            total_profit=total_profit,
            avg_return=avg_return
        )
        
        response = self._make_request_with_backoff(
            self.client.create_tweet,
            text=tweet_text
        )
        
        if response:
            tweet_id = response.data['id']
            print(f"✅ Daily summary posted! ID: {tweet_id}")
            return tweet_id
        else:
            print(f"❌ Failed to post daily summary after retries")
            return None
    
    def format_weekly_backtest_results(
        self,
        week: str,
        total_trades: int,
        win_rate: float,
        total_pnl: float,
        best_trade: float,
        worst_trade: float
    ) -> str:
        """
        Format weekly backtest results with professional styling.
        """
        # Performance indicator
        if total_pnl >= 500:
            perf_emoji = "🔥"
        elif total_pnl >= 100:
            perf_emoji = "🚀"
        elif total_pnl >= 0:
            perf_emoji = "📈"
        else:
            perf_emoji = "📉"
        
        # Format values
        win_rate_fmt = f"{win_rate:.1f}%"
        pnl_fmt = f"${total_pnl:+.2f}"
        best_fmt = f"{best_trade:+.2f}%"
        worst_fmt = f"{worst_trade:+.2f}%"
        
        tweet = f"""{perf_emoji} {week} — Backtest Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Trades: {total_trades} | Win Rate: {win_rate_fmt}

💰 Net P&L: {pnl_fmt}
🏆 Best Trade: {best_fmt}
📉 Worst Trade: {worst_fmt}

Dashboard: dollaraptor.com
#BacktestResults #TradingAlgorithm"""
        
        return tweet
    
    def post_weekly_backtest_results(
        self, 
        week: str, 
        total_trades: int, 
        win_rate: float, 
        total_pnl: float, 
        best_trade: float, 
        worst_trade: float
    ) -> Optional[str]:
        """
        Post weekly backtest results summary.
        
        Args:
            week: Week identifier (e.g., 'Week 1 Dec 2024')
            total_trades: Total trades in the week
            win_rate: Overall win rate
            total_pnl: Total P&L
            best_trade: Best single trade return %
            worst_trade: Worst single trade return %
        
        Returns:
            Tweet ID if successful, None if failed
        """
        tweet_text = self.format_weekly_backtest_results(
            week=week,
            total_trades=total_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            best_trade=best_trade,
            worst_trade=worst_trade
        )
        
        response = self._make_request_with_backoff(
            self.client.create_tweet,
            text=tweet_text
        )
        
        if response:
            tweet_id = response.data['id']
            print(f"✅ Weekly results posted! ID: {tweet_id}")
            return tweet_id
        else:
            print(f"❌ Failed to post weekly results after retries")
            return None
    
    def post_custom_message(self, message: str) -> Optional[str]:
        """
        Post a custom message to Twitter.
        
        Args:
            message: The message to post
        
        Returns:
            Tweet ID if successful, None if failed
        """
        if len(message) > 280:
            print(f"⚠️ Message is {len(message)} characters (max 280). Truncating...")
            message = message[:277] + "..."
        
        response = self._make_request_with_backoff(
            self.client.create_tweet,
            text=message
        )
        
        if response:
            tweet_id = response.data['id']
            print(f"✅ Custom tweet posted! ID: {tweet_id}")
            return tweet_id
        else:
            print(f"❌ Failed to post custom message after retries")
            return None
    
    def test_connection(self) -> bool:
        """
        Test if Twitter API connection is working.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to get authenticated user info
            user = self.client.get_me()
            print(f"✅ Twitter API connection successful!")
            print(f"   Authenticated as: @{user.data.username}")
            return True
        except Exception as e:
            print(f"❌ Twitter API connection failed: {e}")
            return False

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