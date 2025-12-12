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


# import tweepy
# import os
# from datetime import datetime
# from typing import Optional

# class TwitterService:
#     """
#     Service to handle Twitter/X.com automated posting
#     for signal performance updates and summaries.
#     """
    
#     def __init__(self):
#         """Initialize Twitter API client with credentials from .env"""
#         self.api_key = os.getenv('TWITTER_API_KEY')
#         self.api_secret = os.getenv('TWITTER_API_SECRET')
#         self.access_token = os.getenv('TWITTER_ACCESS_TOKEN')
#         self.access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
#         self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        
#         # Validate credentials
#         if not all([self.api_key, self.api_secret, self.access_token, self.access_token_secret]):
#             raise ValueError("Missing Twitter API credentials in environment variables")
        
#         # Initialize Tweepy client (v2 API)
#         self.client = tweepy.Client(
#             consumer_key=self.api_key,
#             consumer_secret=self.api_secret,
#             access_token=self.access_token,
#             access_token_secret=self.access_token_secret,
#             bearer_token=self.bearer_token
#         )
    
#     def post_signal_performance(
#         self, 
#         symbol: str, 
#         entry_price: float, 
#         exit_price: float, 
#         return_percent: float, 
#         profit_usd: float, 
#         result: str,
#         duration_minutes: int
#     ) -> Optional[str]:
#         """
#         Post a completed signal performance to Twitter.
        
#         Args:
#             symbol: Crypto symbol (e.g., 'BTC', 'ETH')
#             entry_price: Entry price
#             exit_price: Exit price
#             return_percent: Return percentage
#             profit_usd: Profit in USD
#             result: 'SUCCESS' or 'FAILURE'
#             duration_minutes: How long the trade lasted
        
#         Returns:
#             Tweet ID if successful, None if failed
#         """
#         try:
#             # Determine emoji and tone based on result
#             emoji = "✅" if result == "SUCCESS" else "❌"
#             result_text = "WINNER" if result == "SUCCESS" else "LOSER"
            
#             # Format the tweet
#             tweet_text = f"""
# {emoji} SIGNAL PERFORMANCE UPDATE

# 📊 {symbol} Trading Signal Completed
# Entry: ${entry_price:.4f}
# Exit: ${exit_price:.4f}

# 📈 Return: {return_percent:.2f}%
# 💰 P&L: {"+" if profit_usd > 0 else ""}{profit_usd:.2f} USD
# ⏱️  Duration: {duration_minutes} mins

# Result: {result_text}

# #Crypto #Trading #Signals #DollaRaptor
#             """.strip()
            
#             # Post to Twitter
#             response = self.client.create_tweet(text=tweet_text)
#             tweet_id = response.data['id']
            
#             print(f"✅ Tweet posted successfully! ID: {tweet_id}")
#             return tweet_id
            
#         except Exception as e:
#             print(f"❌ Error posting to Twitter: {e}")
#             return None
    
#     def post_daily_performance_summary(
#         self, 
#         total_signals: int, 
#         wins: int, 
#         losses: int, 
#         win_rate: float, 
#         total_profit: float,
#         avg_return: float
#     ) -> Optional[str]:
#         """
#         Post a daily performance summary.
        
#         Args:
#             total_signals: Total signals completed today
#             wins: Number of winning trades
#             losses: Number of losing trades
#             win_rate: Win rate percentage
#             total_profit: Total profit in USD
#             avg_return: Average return percentage
        
#         Returns:
#             Tweet ID if successful, None if failed
#         """
#         try:
#             emoji = "🚀" if win_rate > 60 else "📊"
            
#             tweet_text = f"""
# {emoji} DAILY PERFORMANCE SNAPSHOT

# Signals Completed: {total_signals}
# ✅ Winners: {wins} | ❌ Losers: {losses}

# 📈 Win Rate: {win_rate:.1f}%
# 💰 Total Profit: ${total_profit:.2f}
# 📊 Avg Return: {avg_return:.2f}%

# Keep watching for next 5h+ delayed signals...

# #TradingSignals #Crypto #DollaRaptor
#             """.strip()
            
#             response = self.client.create_tweet(text=tweet_text)
#             tweet_id = response.data['id']
            
#             print(f"✅ Daily summary posted! ID: {tweet_id}")
#             return tweet_id
            
#         except Exception as e:
#             print(f"❌ Error posting daily summary: {e}")
#             return None
    
#     def post_weekly_backtest_results(
#         self, 
#         week: str, 
#         total_trades: int, 
#         win_rate: float, 
#         total_pnl: float, 
#         best_trade: float, 
#         worst_trade: float
#     ) -> Optional[str]:
#         """
#         Post weekly backtest results summary.
        
#         Args:
#             week: Week identifier (e.g., 'Week 1 Dec 2024')
#             total_trades: Total trades in the week
#             win_rate: Overall win rate
#             total_pnl: Total P&L
#             best_trade: Best single trade return %
#             worst_trade: Worst single trade return %
        
#         Returns:
#             Tweet ID if successful, None if failed
#         """
#         try:
#             performance_emoji = "🔥" if total_pnl > 500 else "📈" if total_pnl > 0 else "📉"
            
#             tweet_text = f"""
# {performance_emoji} WEEKLY BACKTEST RESULTS - {week}

# 📊 Total Trades: {total_trades}
# ✅ Win Rate: {win_rate:.1f}%

# 💰 Net P&L: ${total_pnl:.2f}
# 🏆 Best Trade: +{best_trade:.2f}%
# 📉 Worst Trade: {worst_trade:.2f}%

# Detailed analysis on dashboard 👉 dollaraptor.com

# #BacktestResults #TradingAlgorithm #DollaRaptor
#             """.strip()
            
#             response = self.client.create_tweet(text=tweet_text)
#             tweet_id = response.data['id']
            
#             print(f"✅ Weekly results posted! ID: {tweet_id}")
#             return tweet_id
            
#         except Exception as e:
#             print(f"❌ Error posting weekly results: {e}")
#             return None
    
#     def post_custom_message(self, message: str) -> Optional[str]:
#         """
#         Post a custom message to Twitter.
        
#         Args:
#             message: The message to post
        
#         Returns:
#             Tweet ID if successful, None if failed
#         """
#         try:
#             if len(message) > 280:
#                 print(f"⚠️ Message is {len(message)} characters (max 280). Truncating...")
#                 message = message[:277] + "..."
            
#             response = self.client.create_tweet(text=message)
#             tweet_id = response.data['id']
            
#             print(f"✅ Custom tweet posted! ID: {tweet_id}")
#             return tweet_id
            
#         except Exception as e:
#             print(f"❌ Error posting custom message: {e}")
#             return None
    
#     def test_connection(self) -> bool:
#         """
#         Test if Twitter API connection is working.
        
#         Returns:
#             True if connection successful, False otherwise
#         """
#         try:
#             # Try to get authenticated user info
#             user = self.client.get_me()
#             print(f"✅ Twitter API connection successful!")
#             print(f"   Authenticated as: @{user.data.username}")
#             return True
#         except Exception as e:
#             print(f"❌ Twitter API connection failed: {e}")
#             return False