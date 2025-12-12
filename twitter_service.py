import tweepy
import os
import asyncio
import tempfile
from datetime import datetime
from typing import Optional
from pathlib import Path

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
    
    def html_to_image_via_pillow(self, html_content: str, output_path: str) -> bool:
        """
        Convert HTML to PNG using Pillow + imgkit (lightweight alternative).
        Fallback if Playwright fails.
        """
        try:
            import imgkit
            # Convert HTML string to image
            options = {
                'width': 1200,
                'height': 630,
                'quiet': ''
            }
            imgkit.from_string(html_content, output_path, options=options)
            return True
        except Exception as e:
            print(f"[IMAGE] ❌ Pillow conversion failed: {e}")
            return False
    
    async def html_to_image_async(self, html_content: str, output_path: str) -> bool:
        """
        Convert HTML to PNG image using Playwright.
        Returns True if successful.
        """
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                # Use firefox which is lighter than chromium
                browser = await p.firefox.launch(args=['--disable-gpu', '--no-sandbox'])
                page = await browser.new_page(viewport={"width": 1200, "height": 630})
                
                # Set the HTML content
                await page.set_content(html_content, wait_until='networkidle')
                
                # Take screenshot
                await page.screenshot(path=output_path, full_page=False)
                
                await browser.close()
                return True
        except Exception as e:
            print(f"[IMAGE] ⚠️  Playwright failed: {e}")
            # Fallback to Pillow
            print(f"[IMAGE] 🔄 Trying Pillow fallback...")
            return self.html_to_image_via_pillow(html_content, output_path)
    
    def html_to_image(self, html_content: str, output_path: str) -> bool:
        """
        Sync wrapper for HTML to image conversion.
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.html_to_image_async(html_content, output_path))
            loop.close()
            return result
        except Exception as e:
            print(f"[IMAGE] ❌ Async error: {e}")
            return False
    
    def post_signal_performance_with_image(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        return_percent: float,
        profit_usd: float,
        result: str,
        duration_minutes: int,
        image_html: str
    ) -> Optional[str]:
        """
        Post signal performance to Twitter with a beautiful generated image.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            entry_price: Entry price
            exit_price: Exit price
            return_percent: Return percentage
            profit_usd: Profit/loss in USD
            result: "SUCCESS" or "FAILURE"
            duration_minutes: How long the trade lasted
            image_html: HTML content to render as image
        
        Returns:
            Tweet ID if successful, None otherwise
        """
        temp_image_path = None
        try:
            # Create temporary file for the image
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_image_path = tmp.name
            
            print(f"[IMAGE] 🎨 Rendering HTML to image...")
            
            # Convert HTML to image
            success = self.html_to_image(image_html, temp_image_path)
            
            if not success or not os.path.exists(temp_image_path):
                print(f"[IMAGE] ❌ Failed to create image, posting text-only fallback...")
                # Fall back to text-only post
                return self.post_signal_performance(
                    symbol=symbol,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    return_percent=return_percent,
                    profit_usd=profit_usd,
                    result=result,
                    duration_minutes=duration_minutes
                )
            
            print(f"[IMAGE] ✅ Image created: {temp_image_path}")
            
            # Build the tweet text (short caption)
            is_win = result == "SUCCESS"
            emoji = "📈" if is_win else "📉"
            
            tweet_text = f"{emoji} {symbol}\n"
            tweet_text += f"Entry: ${entry_price:.4f} → Exit: ${exit_price:.4f}\n"
            tweet_text += f"Return: {return_percent:+.2f}% | P&L: ${profit_usd:+.2f}"
            
            # Upload media using v1 API (for media_upload compatibility)
            print(f"[TWITTER] 📤 Uploading image to Twitter...")
            
            # Create a v1.1 auth for media upload
            auth = tweepy.OAuthHandler(self.api_key, self.api_secret)
            auth.set_access_token(self.access_token, self.access_token_secret)
            api_v1 = tweepy.API(auth)
            
            # Upload the image
            media_response = api_v1.media_upload(filename=temp_image_path)
            media_id = media_response.media_id
            print(f"[TWITTER] ✅ Media uploaded: {media_id}")
            
            # Post tweet with media using v2 API
            response = self.client.create_tweet(
                text=tweet_text,
                media_ids=[media_id]
            )
            
            tweet_id = response.data['id']
            print(f"[TWITTER] ✅ Tweet posted with image! ID: {tweet_id}")
            
            return tweet_id
            
        except Exception as e:
            print(f"[TWITTER] ❌ Failed to post with image: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            # Clean up temp file
            if temp_image_path and os.path.exists(temp_image_path):
                try:
                    os.unlink(temp_image_path)
                    print(f"[IMAGE] 🧹 Cleaned up temp file")
                except Exception as e:
                    print(f"[IMAGE] ⚠️  Could not delete temp file: {e}")
    
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
        Post a completed signal performance to Twitter (text only fallback).
        
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
            return None
    
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
            return None
    
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
            return None
    
    def post_custom_message(self, message: str) -> Optional[str]:
        """
        Post a custom message to Twitter.
        
        Args:
            message: The message to post
        
        Returns:
            Tweet ID if successful, None if failed
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