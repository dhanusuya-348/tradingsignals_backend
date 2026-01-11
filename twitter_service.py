import tweepy
import os
import time
from datetime import datetime
from typing import Optional
from urllib.parse import quote

class TwitterService:
    """
    Service to handle Twitter/X.com automated posting
    for signal performance updates and summaries.
    """
    
    # Mapping of crypto symbols to full names
    COIN_NAMES = {
        'BTC': 'Bitcoin', 'ETH': 'Ethereum', 'BNB': 'BNB', 'XRP': 'XRP',
        'ADA': 'Cardano', 'DOGE': 'Dogecoin', 'SOL': 'Solana', 'TRX': 'TRON',
        'DOT': 'Polkadot', 'MATIC': 'Polygon', 'LTC': 'Litecoin', 'SHIB': 'Shiba Inu',
        'AVAX': 'Avalanche', 'UNI': 'Uniswap', 'LINK': 'Chainlink', 'ATOM': 'Cosmos',
        'XLM': 'Stellar', 'BCH': 'Bitcoin Cash', 'NEAR': 'NEAR Protocol', 'ALGO': 'Algorand',
        'VET': 'VeChain', 'ICP': 'Internet Computer', 'FIL': 'Filecoin', 'HBAR': 'Hedera',
        'APT': 'Aptos', 'QNT': 'Quant', 'CRO': 'Cronos', 'LDO': 'Lido DAO',
        'ARB': 'Arbitrum', 'OP': 'Optimism', 'MKR': 'Maker', 'GRT': 'The Graph'
    }
    
    def __init__(self):
        self.last_post_time = 0
        self.min_interval = 60  # Minimum 60 seconds between posts
        self.rate_limit_reset = 0
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
    
    def _get_coin_name(self, symbol: str) -> str:
        """Get full coin name from symbol"""
        return self.COIN_NAMES.get(symbol.upper(), symbol)
    
    def _get_tradingview_link(self, symbol: str, entry_time: datetime, exit_time: datetime) -> str:
        """Generate TradingView chart link for specific timeframe"""
        try:
            # Convert to timestamps
            entry_ts = int(entry_time.timestamp())
            exit_ts = int(exit_time.timestamp())
            
            # TradingView chart URL with time range
            base_url = "https://www.tradingview.com/chart/"
            symbol_pair = f"BINANCE:{symbol}USDT"
            time_params = f"?symbol={quote(symbol_pair)}&interval=1H&from={entry_ts}&to={exit_ts}"
            
            return base_url + time_params
        except:
            return f"https://www.tradingview.com/symbols/{symbol}USDT/"
    
    def _calculate_risk_reward(self, entry_price: float, exit_price: float, result: str) -> str:
        """Calculate risk-reward ratio (simplified)"""
        try:
            if result == "SUCCESS":
                return_pct = abs((exit_price - entry_price) / entry_price * 100)
                # Assume 2% risk for successful trades
                rr_ratio = return_pct / 2.0
                return f"1:{rr_ratio:.1f}"
            else:
                # For losses, show as negative
                return "1:0.5"  # Conservative estimate
        except:
            return "N/A"
    
    def _wait_for_rate_limit(self):
        """Wait if we're posting too frequently"""
        current_time = time.time()
        time_since_last = current_time - self.last_post_time
        
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            print(f"⏳ Rate limiting: waiting {wait_time:.1f}s...")
            time.sleep(wait_time)
    
    def _handle_rate_limit_error(self, error):
        """Handle 429 rate limit errors with exponential backoff"""
        if "429" in str(error) or "Too Many Requests" in str(error):
            # Start with 15 minutes, then exponential backoff
            wait_time = 900  # 15 minutes
            print(f"🚫 Rate limit hit! Waiting {wait_time/60:.1f} minutes...")
            self.rate_limit_reset = time.time() + wait_time
            return True
        return False
    
    def post_signal_performance(
        self, 
        symbol: str, 
        entry_price: float, 
        exit_price: float, 
        return_percent: float, 
        profit_usd: float, 
        result: str,
        duration_minutes: int,
        entry_time: datetime = None,
        exit_time: datetime = None
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
            entry_time: Signal entry time
            exit_time: Signal exit time
        
        Returns:
            Tweet ID if successful, None if failed
        """
        # Check if we're still in rate limit cooldown
        if time.time() < self.rate_limit_reset:
            remaining = self.rate_limit_reset - time.time()
            print(f"⏳ Still in rate limit cooldown: {remaining/60:.1f} minutes remaining")
            return None
        
        # Wait for rate limiting
        self._wait_for_rate_limit()
        
        try:
            # Get coin full name and additional data
            coin_name = self._get_coin_name(symbol)
            risk_reward = self._calculate_risk_reward(entry_price, exit_price, result)
            
            # Format timestamps
            entry_str = entry_time.strftime("%m/%d %H:%M UTC") if entry_time else "N/A"
            exit_str = exit_time.strftime("%m/%d %H:%M UTC") if exit_time else "N/A"
            
            # Determine emoji and tone based on result
            emoji = "✅" if result == "SUCCESS" else "❌"
            result_text = "WINNER" if result == "SUCCESS" else "LOSER"
            
            # Generate TradingView link if times available
            chart_link = ""
            if entry_time and exit_time:
                tv_link = self._get_tradingview_link(symbol, entry_time, exit_time)
                chart_link = f"\n📈 Chart: {tv_link}"
            
            # Format the tweet
            tweet_text = f"""
{emoji} SIGNAL PERFORMANCE UPDATE

📊 {coin_name} ({symbol}) Trading Signal
Entry: ${entry_price:.4f} | {entry_str}
Exit: ${exit_price:.4f} | {exit_str}

📈 Return: {return_percent:.2f}%
💰 P&L: {"+" if profit_usd > 0 else ""}${profit_usd:.2f}
⚖️ Risk:Reward: {risk_reward}
⏱️ Duration: {duration_minutes}m

Result: {result_text}{chart_link}

🔗 https://dollaraptor.com
#Crypto #Trading #Signals #DollaRaptor
            """.strip()
            
            # Truncate if too long (Twitter limit is 280 chars)
            if len(tweet_text) > 280:
                # Remove chart link first if present
                if chart_link:
                    tweet_text = tweet_text.replace(chart_link, "")
                # If still too long, truncate
                if len(tweet_text) > 280:
                    tweet_text = tweet_text[:277] + "..."
            
            # Post to Twitter
            response = self.client.create_tweet(text=tweet_text)
            tweet_id = response.data['id']
            
            # Update last post time on success
            self.last_post_time = time.time()
            print(f"✅ Tweet posted successfully! ID: {tweet_id}")
            return tweet_id
            
        except Exception as e:
            print(f"❌ Error posting to Twitter: {e}")
            # Handle rate limiting
            if self._handle_rate_limit_error(e):
                return None  # Will retry later
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
        if time.time() < self.rate_limit_reset:
            return None
        
        self._wait_for_rate_limit()
        
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

🔗 https://dollaraptor.com
#TradingSignals #Crypto #DollaRaptor
            """.strip()
            
            response = self.client.create_tweet(text=tweet_text)
            tweet_id = response.data['id']
            
            self.last_post_time = time.time()
            print(f"✅ Daily summary posted! ID: {tweet_id}")
            return tweet_id
            
        except Exception as e:
            print(f"❌ Error posting daily summary: {e}")
            self._handle_rate_limit_error(e)
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
        if time.time() < self.rate_limit_reset:
            return None
        
        self._wait_for_rate_limit()
        
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

🔗 https://dollaraptor.com
#BacktestResults #TradingAlgorithm #DollaRaptor
            """.strip()
            
            response = self.client.create_tweet(text=tweet_text)
            tweet_id = response.data['id']
            
            self.last_post_time = time.time()
            print(f"✅ Weekly results posted! ID: {tweet_id}")
            return tweet_id
            
        except Exception as e:
            print(f"❌ Error posting weekly results: {e}")
            self._handle_rate_limit_error(e)
            return None
    
    def post_custom_message(self, message: str) -> Optional[str]:
        """
        Post a custom message to Twitter.
        
        Args:
            message: The message to post
        
        Returns:
            Tweet ID if successful, None if failed
        """
        if time.time() < self.rate_limit_reset:
            return None
        
        self._wait_for_rate_limit()
        
        try:
            if len(message) > 280:
                print(f"⚠️ Message is {len(message)} characters (max 280). Truncating...")
                message = message[:277] + "..."
            
            response = self.client.create_tweet(text=message)
            tweet_id = response.data['id']
            
            self.last_post_time = time.time()
            print(f"✅ Custom tweet posted! ID: {tweet_id}")
            return tweet_id
            
        except Exception as e:
            print(f"❌ Error posting custom message: {e}")
            self._handle_rate_limit_error(e)
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