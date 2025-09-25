from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import os
import re

# Safe import for transformers - fallback if not available
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    FINBERT_AVAILABLE = True
    print("Transformers available - FinBERT enabled")
except ImportError:
    print("Transformers not available - using VADER-only sentiment analysis")
    FINBERT_AVAILABLE = False
    torch = None

# Fix: Import config and fetch_news_utils from correct paths
try:
    from ..config import RSS_FEEDS, SYMBOL_NAME_MAP
    from .fetch_news_utils import fetch_rss_headlines
    print("Config and news utils imported successfully")
except ImportError:
    # Fallback: try direct import with path manipulation
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    try:
        from ..config import RSS_FEEDS, SYMBOL_NAME_MAP
        from ..data.fetch_news_utils import fetch_rss_headlines
        print("Config and news utils imported via fallback")
    except ImportError:
        # Final fallback
        RSS_FEEDS = [
            "https://cryptopanic.com/feed/rss",
            "https://cointelegraph.com/rss",
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://www.cryptoglobe.com/latest/feed/",
            "https://decrypt.co/feed",
            "https://cryptobriefing.com/feed/",
            "https://bitcoinmagazine.com/.rss/full/",
        ]
        SYMBOL_NAME_MAP = {
            "BTC": ("Bitcoin", "BTC"),
            "ETH": ("Ethereum", "ETH"),
            "SOL": ("Solana", "SOL"),
            "ADA": ("Cardano", "ADA"),
            "AVAX": ("Avalanche", "AVAX"),
            "DOT": ("Polkadot", "DOT"),
            "LINK": ("Chainlink", "LINK"),
            "MATIC": ("Polygon", "MATIC"),
            "UNI": ("Uniswap", "UNI"),
            "LTC": ("Litecoin", "LTC"),
        }
        print("Using fallback config values for sentiment analysis")
        
        # Mock fetch_rss_headlines function
        def fetch_rss_headlines(feeds, coin_name, coin_code, extract_full_articles=False):
            print(f"Mock news fetch for {coin_name} ({coin_code})")
            return []

# --- CONFIG: tweak weights here ---
if FINBERT_AVAILABLE:
    HEADLINE_WEIGHT = 0.30   # VADER weight on the headline
    ARTICLE_WEIGHT = 0.70    # FinBERT weight on the full article
else:
    HEADLINE_WEIGHT = 0.50   # VADER weight on the headline
    ARTICLE_WEIGHT = 0.50    # VADER weight on the article content (no FinBERT)

FINBERT_MODEL_NAME = "yiyanghkust/finbert-tone"  # good finance tone model
LOCAL_FINBERT_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "finbert")  # saved copy

# --- FinBERT loader & cache (only if available) ---
def load_finbert(model_name=FINBERT_MODEL_NAME, cache_dir=LOCAL_FINBERT_DIR, device=None):
    if not FINBERT_AVAILABLE:
        return None, None, "cpu"
        
    os.makedirs(cache_dir, exist_ok=True)
    try:
        if os.path.exists(os.path.join(cache_dir, "config.json")) or os.path.exists(os.path.join(cache_dir, "tokenizer.json")):
            tokenizer = AutoTokenizer.from_pretrained(cache_dir)
            model = AutoModelForSequenceClassification.from_pretrained(cache_dir)
        else:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSequenceClassification.from_pretrained(model_name)
            try:
                tokenizer.save_pretrained(cache_dir)
                model.save_pretrained(cache_dir)
            except Exception:
                pass
    except Exception as e:
        print(f"Error loading FinBERT: {e}")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    return tokenizer, model, device

# Initialize FinBERT and VADER
if FINBERT_AVAILABLE:
    try:
        print("Loading FinBERT model (this happens once)...")
        _tokenizer, _finbert_model, _device = load_finbert()
        print("FinBERT ready on device:", _device)
    except Exception as e:
        print(f"FinBERT loading failed: {e}")
        _tokenizer, _finbert_model, _device = None, None, "cpu"
        FINBERT_AVAILABLE = False
else:
    _tokenizer, _finbert_model, _device = None, None, "cpu"

_analyzer = SentimentIntensityAnalyzer()  # VADER


def finbert_predict_probs(text, tokenizer=None, model=None, device=None):
    """
    Predict sentiment probabilities using FinBERT.
    Falls back to VADER if FinBERT is not available.
    """
    if not FINBERT_AVAILABLE or not text or not text.strip() or not tokenizer or not model:
        # Fallback to VADER sentiment analysis
        if text and text.strip():
            vader_scores = _analyzer.polarity_scores(text)
            compound = vader_scores['compound']
            
            # Convert VADER compound score to probabilities
            if compound >= 0.1:
                pos_prob = min(0.8, (compound + 1) / 2)
                neg_prob = max(0.1, (1 - compound) / 4)
            elif compound <= -0.1:
                neg_prob = min(0.8, (1 - compound) / 2)
                pos_prob = max(0.1, (compound + 1) / 4)
            else:
                pos_prob = 0.3
                neg_prob = 0.3
            
            neutral_prob = 1.0 - pos_prob - neg_prob
            
            return {
                "negative": float(neg_prob),
                "neutral": float(neutral_prob), 
                "positive": float(pos_prob)
            }, float(compound)
        else:
            return {"negative": 0.0, "neutral": 1.0, "positive": 0.0}, 0.0
    
    # Use FinBERT if available
    try:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            probs = torch.nn.functional.softmax(logits, dim=-1).cpu().numpy()[0]
    except Exception as e:
        print(f"FinBERT prediction error: {e}")
        return {"negative": 0.0, "neutral": 1.0, "positive": 0.0}, 0.0

    id2label = getattr(model.config, "id2label", None)
    if id2label:
        labels = [id2label[i].lower() for i in sorted(id2label.keys())]
    else:
        labels = ["negative", "neutral", "positive"]

    label_probs = {labels[i]: float(probs[i]) for i in range(min(len(labels), len(probs)))}
    pos = label_probs.get("positive", 0.0)
    neg = label_probs.get("negative", 0.0)
    scalar = float(pos - neg)
    return label_probs, scalar


def _is_generic_title(title):
    if not title or len(title.strip()) < 8:
        return True
    t = title.lower()
    generic_phrases = [
        "here's what", "here is what", "what happened", "what's happened", 
        "what happened today", "here's what happened", "in crypto today", 
        "quick take", "daily roundup", "top news", "what happened in"
    ]
    return any(g in t for g in generic_phrases)


def make_meaningful_title(orig_title, summary_text):
    orig_title = (orig_title or "").strip()
    if orig_title and not _is_generic_title(orig_title):
        return orig_title
    if summary_text:
        sentences = re.split(r'(?<=[.!?])\s+', summary_text.strip())
        candidate = sentences[0] if sentences else summary_text
        candidate = candidate.strip()
        if len(candidate) > 120:
            candidate = candidate[:120].rsplit(' ', 1)[0] + "..."
        return candidate[0].upper() + candidate[1:] if candidate else "News"
    return "News"


def extract_pos_neg_lines_vader(summary_text):
    """
    Break summary into sentences, run sentiment analysis on each,
    return positive and negative ones separately.
    Uses VADER when FinBERT is not available.
    """
    if not summary_text:
        return [], []
    
    sentences = re.split(r'(?<=[.!?])\s+', summary_text.strip())
    positives, negatives = [], []
    
    for sent in sentences:
        if not sent.strip():
            continue
            
        if FINBERT_AVAILABLE:
            probs, scalar = finbert_predict_probs(sent, _tokenizer, _finbert_model, _device)
            if probs["positive"] > 0.5:
                positives.append(sent.strip())
            elif probs["negative"] > 0.5:
                negatives.append(sent.strip())
        else:
            # Use VADER for sentence-level sentiment
            vader_scores = _analyzer.polarity_scores(sent)
            compound = vader_scores['compound']
            
            if compound > 0.3:
                positives.append(sent.strip())
            elif compound < -0.3:
                negatives.append(sent.strip())
    
    return positives, negatives


def get_sentiment_score(symbol, print_news=True, debug=False):
    coin_symbol = symbol.replace("USDT", "")
    coin_name, coin_code = SYMBOL_NAME_MAP.get(coin_symbol, (None, None))

    headlines = fetch_rss_headlines(RSS_FEEDS, coin_name, coin_code, extract_full_articles=True)
    if not headlines:
        if print_news:
            print("\nNo news headlines found for sentiment analysis.\n")
        return "neutral", []

    scored_headlines = []
    sum_weighted, count = 0.0, 0

    for item in headlines:
        title = item.get("title", "") or ""
        full_text = item.get("full_text") or item.get("summary_news") or item.get("text") or ""
        base_summary = item.get("summary_news") or ""

        # Always use VADER for headlines
        vader_compound = _analyzer.polarity_scores(title)["compound"]
        
        # Use FinBERT for full text if available, otherwise VADER
        if FINBERT_AVAILABLE and full_text:
            probs, finbert_scalar = finbert_predict_probs(full_text, _tokenizer, _finbert_model, _device)
        else:
            # Fallback to VADER for full text
            if full_text:
                vader_full = _analyzer.polarity_scores(full_text)["compound"]
            else:
                vader_full = vader_compound
            
            # Mock FinBERT-style output for consistency
            probs = {"negative": 0.0, "neutral": 1.0, "positive": 0.0}
            finbert_scalar = vader_full

        score = (HEADLINE_WEIGHT * vader_compound) + (ARTICLE_WEIGHT * finbert_scalar)
        meaningful_title = make_meaningful_title(title, base_summary)

        # Extract positive/negative sentences from the summary
        pos_lines, neg_lines = extract_pos_neg_lines_vader(base_summary)
        sentiment_section = ""
        if pos_lines:
            sentiment_section += "\n\nPositive Points:\n- " + "\n- ".join(pos_lines)
        if neg_lines:
            sentiment_section += "\n\nNegative Points:\n- " + "\n- ".join(neg_lines)

        # Final summary: full summary + sentiment notes
        final_summary = base_summary + sentiment_section if base_summary else sentiment_section

        item["title"] = meaningful_title
        item["orig_title"] = title
        item["summary_news"] = final_summary
        item["full_text"] = full_text
        item["vader_title"] = float(vader_compound)
        item["finbert_probs"] = probs
        item["finbert_scalar"] = float(finbert_scalar)
        item["score"] = float(score)
        scored_headlines.append(item)

        sum_weighted += score
        count += 1

        if debug and print_news:
            analysis_method = "FinBERT" if FINBERT_AVAILABLE else "VADER"
            print(f"DBG: {meaningful_title[:80]} | vader={vader_compound:.3f} | {analysis_method.lower()}={finbert_scalar:.3f} | score={score:.3f}")

    aggregate = sum_weighted / count if count else 0.0

    if print_news:
        analysis_info = f"Sentiment: {'FinBERT + VADER' if FINBERT_AVAILABLE else 'VADER-only'}"
        print(f"Total news items collected: {len(scored_headlines)}")
        print(analysis_info)

    if aggregate >= 0.20:
        sentiment_label = "bullish"
    elif aggregate <= -0.20:
        sentiment_label = "bearish"
    else:
        sentiment_label = "neutral"

    return sentiment_label, scored_headlines