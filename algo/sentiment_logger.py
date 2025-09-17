# sentiment_logger.py

import datetime
import pandas as pd
import os
from data.fetch_sentiment import get_sentiment_score
from config import SYMBOL_NAME_MAP

def log_sentiment():
    os.makedirs("data", exist_ok=True)
    FILENAME = "data/sentiment_history.csv"
    symbols = [sym + "USDT" for sym in list(SYMBOL_NAME_MAP.keys())][:20]  # Top 20 coins

    entries = []

    for symbol in symbols:
        coin_symbol = symbol.replace("USDT", "")
        coin_name, coin_code = SYMBOL_NAME_MAP.get(coin_symbol, (None, None))
        if not coin_name:
            continue

        try:
            sentiment, _ = get_sentiment_score(symbol, print_news=False)
        except Exception as e:
            print(f"⚠️ Error getting sentiment for {symbol}: {e}")
            continue

        entries.append({
            "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "sentiment": sentiment
        })

    if entries:
        df = pd.DataFrame(entries)
        file_exists = os.path.exists(FILENAME)

        if not file_exists:
            df.to_csv(FILENAME, index=False)
        else:
            df.to_csv(FILENAME, mode='a', header=False, index=False)

        print(f"✅ Logged {len(entries)} sentiment records.")
    else:
        print("⚠️ No sentiment data to log.")
