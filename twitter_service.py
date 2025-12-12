import tweepy
import os
from datetime import datetime
from typing import Optional

class RateLimitError(Exception):
    """Raised when we hit Twitter rate limit"""
    def __init__(self, reset_time: float = None):
        self.reset_time = reset_time or (datetime.utcnow().timestamp() + 15*60)
        super().__init__(f"Rate limited. Reset at {datetime.fromtimestamp(self.reset_time)}")

class TwitterService:
    """
    Service to handle Twitter/X.com automated posting
    for signal performance updates and summaries.
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
    
    def _handle_api_error(self, error: Exception) -> None:
        """
        Check if error is a rate limit error and raise RateLimitError if so.
        Otherwise re-raise the original error.
        """
        error_str = str(error).lower()
        
        # Check for 429 status code or rate limit mentions
        if "429" in str(error) or "too many requests" in error_str or "rate limit" in error_str:
            # Try to extract reset time from headers if available
            reset_time = None
            if hasattr(error, 'response') and hasattr(error.response, 'headers'):
                try:
                    reset_header = error.response.headers.get('x-rate-limit-reset')
                    if reset_header:
                        reset_time = float(reset_header)
                except:
                    pass
            
            raise RateLimitError(reset_time)
        else:
            raise error
    
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
            
        Raises:
            RateLimitError: If we hit Twitter rate limit
        """
        try:
            # Determine emoji and tone based on result
            emoji = "✅" if result == "SUCCESS" else "❌"
            result_text = "WINNER" if result == "SUCCESS" else "LOSER"
            
            # Format the tweet
            tweet_text = f"""
{emoji} SIGNAL PERFORMANCE UPDATE

📊 {symbol} Trading Signal Completed
Entry: ${entry_price:.4f}
Exit: ${exit_price:.4f}

📈 Return: {return_percent:.2f}%
💰 P&L: {"+" if profit_usd > 0 else ""}{profit_usd:.2f} USD
⏱️  Duration: {duration_minutes} mins

Result: {result_text}

#Crypto #Trading #Signals #DollaRaptor
            """.strip()
            
            # Post to Twitter
            response = self.client.create_tweet(text=tweet_text)
            tweet_id = response.data['id']
            
            print(f"✅ Tweet posted successfully! ID: {tweet_id}")
            return tweet_id
            
        except Exception as e:
            print(f"❌ Error posting to Twitter: {e}")
            self._handle_api_error(e)
    
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
            
        Raises:
            RateLimitError: If we hit Twitter rate limit
        """
        try:
            emoji = "🚀" if win_rate > 60 else "📊"
            
            tweet_text = f"""
{emoji} DAILY PERFORMANCE SNAPSHOT

Signals Completed: {total_signals}
✅ Winners: {wins} | ❌ Losers: {losses}

📈 Win Rate: {win_rate:.1f}%
💰 Total Profit: ${total_profit:.2f}
📊 Avg Return: {avg_return:.2f}%

Keep watching for next 5h+ delayed signals...

#TradingSignals #Crypto #DollaRaptor
            """.strip()
            
            response = self.client.create_tweet(text=tweet_text)
            tweet_id = response.data['id']
            
            print(f"✅ Daily summary posted! ID: {tweet_id}")
            return tweet_id
            
        except Exception as e:
            print(f"❌ Error posting daily summary: {e}")
            self._handle_api_error(e)
    
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
            
        Raises:
            RateLimitError: If we hit Twitter rate limit
        """
        try:
            performance_emoji = "🔥" if total_pnl > 500 else "📈" if total_pnl > 0 else "📉"
            
            tweet_text = f"""
{performance_emoji} WEEKLY BACKTEST RESULTS - {week}

📊 Total Trades: {total_trades}
✅ Win Rate: {win_rate:.1f}%

💰 Net P&L: ${total_pnl:.2f}
🏆 Best Trade: +{best_trade:.2f}%
📉 Worst Trade: {worst_trade:.2f}%

Detailed analysis on dashboard 👉 dollaraptor.com

#BacktestResults #TradingAlgorithm #DollaRaptor
            """.strip()
            
            response = self.client.create_tweet(text=tweet_text)
            tweet_id = response.data['id']
            
            print(f"✅ Weekly results posted! ID: {tweet_id}")
            return tweet_id
            
        except Exception as e:
            print(f"❌ Error posting weekly results: {e}")
            self._handle_api_error(e)
    
    def post_custom_message(self, message: str) -> Optional[str]:
        """
        Post a custom message to Twitter.
        
        Args:
            message: The message to post
        
        Returns:
            Tweet ID if successful, None if failed
            
        Raises:
            RateLimitError: If we hit Twitter rate limit
        """
        try:
            if len(message) > 280:
                print(f"⚠️ Message is {len(message)} characters (max 280). Truncating...")
                message = message[:277] + "..."
            
            response = self.client.create_tweet(text=message)
            tweet_id = response.data['id']
            
            print(f"✅ Custom tweet posted! ID: {tweet_id}")
            return tweet_id
            
        except Exception as e:
            print(f"❌ Error posting custom message: {e}")
            self._handle_api_error(e)
    
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

# #twitter_service.py
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