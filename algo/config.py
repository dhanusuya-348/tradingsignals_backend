# config.py

from pycoingecko import CoinGeckoAPI

# === BINANCE SETTINGS ===
BINANCE_BASE_URL = "https://api.binance.com"
HISTORICAL_LIMIT = 2500 # Number of candles to fetch

# === SENTIMENT SETTINGS ===
RSS_FEEDS = [
    "https://cryptopanic.com/feed/rss",
    "https://cointelegraph.com/rss",
    #"https://news.bitcoin.com/feed/",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",  # Coindesk
    "https://www.cryptoglobe.com/latest/feed/",         # CryptoGlobe
    "https://decrypt.co/feed",                          # Decrypt
    "https://cryptobriefing.com/feed/",                 # CryptoBriefing
    "https://bitcoinmagazine.com/.rss/full/",           # Bitcoin Magazine
]

USE_FINBERT = False  # If False, fall back to VADER

# === PATHS ===
DATA_FOLDER = "data/"
REPORT_FOLDER = "reports/"
LOG_FILE = "logs/trading_signals.log"

# === OTHER SETTINGS ===
DEBUG = True

# config.py


def build_symbol_name_map(top_n=100):
    cg = CoinGeckoAPI()
    coins = cg.get_coins_markets(vs_currency='usd', per_page=top_n, page=1)
    mapping = {}
    for coin in coins:
        symbol = coin['symbol'].upper()
        name = coin['name']
        mapping[symbol] = (name, symbol)
    return mapping

# Pre-build top‑100
SYMBOL_NAME_MAP = build_symbol_name_map(100)

# SYMBOL_NAME_MAP = {
#     "BTC": ("Bitcoin", "BTC"),
#     "ETH": ("Ethereum", "ETH"),
#     "BNB": ("Binance Coin", "BNB"),
#     "SOL": ("Solana", "SOL"),
#     "ADA": ("Cardano", "ADA"),
#     "XRP": ("Ripple", "XRP"),
#     "DOGE": ("Dogecoin", "DOGE"),
#     "DOT": ("Polkadot", "DOT"),
#     "MATIC": ("Polygon", "MATIC"),
#     "LTC": ("Litecoin", "LTC"),
#     # Add more as needed...
# }

