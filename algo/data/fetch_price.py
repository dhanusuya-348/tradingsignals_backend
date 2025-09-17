# data/fetch_price.py

import requests
import pandas as pd
from datetime import datetime
from config import BINANCE_BASE_URL, HISTORICAL_LIMIT

def get_price_data(symbol: str, interval: str) -> pd.DataFrame:
    """
    Fetch historical OHLCV candlestick data for a given symbol and interval from Binance.
    Uses pagination to fetch more than 1000 candles if needed.
    """
    all_data = []
    end_time = int(datetime.now().timestamp() * 1000)
    remaining = HISTORICAL_LIMIT
    limit = 1000  # Binance max per request

    while remaining > 0:
        fetch_limit = min(remaining, limit)
        url = f"{BINANCE_BASE_URL}/api/v3/klines"
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "endTime": end_time,
            "limit": fetch_limit
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"❌ Error fetching data from Binance: {e}")
            break

        if not data:
            break

        all_data = data + all_data  # Prepend to maintain chronological order
        end_time = data[0][0] - 1  # Move window back
        remaining -= len(data)

    if not all_data:
        print("⚠️ No data returned.")
        return pd.DataFrame()

    df = pd.DataFrame(all_data, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
    df.set_index("timestamp", inplace=True)
    return df[["open", "high", "low", "close", "volume"]].astype(float)

def fetch_binance_1m_data(symbol: str, start_time: datetime, end_time: datetime) -> pd.DataFrame:
    """
    Fetch 1-minute OHLCV data from Binance between start_time and end_time.
    Returns a DataFrame with timestamp index.
    """
    all_candles = []
    base_url = f"{BINANCE_BASE_URL}/api/v3/klines"
    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(end_time.timestamp() * 1000)
    limit = 1000

    while start_ms < end_ms:
        params = {
            "symbol": symbol.upper(),
            "interval": "1m",
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": limit
        }

        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"❌ Error fetching 1m data: {e}")
            break

        if not data:
            break

        all_candles.extend(data)
        last_time = data[-1][0]
        start_ms = last_time + 60_000  # move forward 1 minute

    if not all_candles:
        return pd.DataFrame()

    df = pd.DataFrame(all_candles, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    return df[["open", "high", "low", "close", "volume"]].astype(float)
