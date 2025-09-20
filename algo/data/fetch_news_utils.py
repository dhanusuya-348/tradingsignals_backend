import feedparser
import re
import requests
from bs4 import BeautifulSoup
import time

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^\w\s.,!?';:()\-\"]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def simple_summarize(text, sentence_count=4):
    """Simple text summarizer without sumy dependency"""
    if not text:
        return ""
    
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    if len(sentences) <= sentence_count:
        return text
    
    # Simple scoring: prefer sentences with more words and common keywords
    keywords = ['bitcoin', 'crypto', 'ethereum', 'trading', 'price', 'market', 'blockchain', 'investment']
    
    scored_sentences = []
    for i, sentence in enumerate(sentences):
        if len(sentence.strip()) < 10:  # Skip very short sentences
            continue
            
        score = len(sentence.split())  # Base score on word count
        
        # Boost score for sentences with keywords
        for keyword in keywords:
            if keyword.lower() in sentence.lower():
                score += 5
        
        # Prefer sentences from the beginning
        if i < 3:
            score += 2
        
        scored_sentences.append((score, sentence.strip()))
    
    # Sort by score and take top sentences
    scored_sentences.sort(key=lambda x: x[0], reverse=True)
    top_sentences = [sent[1] for sent in scored_sentences[:sentence_count]]
    
    # Return in original order
    result_sentences = []
    for sentence in sentences:
        if sentence.strip() in top_sentences:
            result_sentences.append(sentence.strip())
    
    return " ".join(result_sentences)

def _extract_from_selectors(soup, selectors, min_chars=30):
    chunks = []
    for sel in selectors:
        nodes = soup.select(sel)
        if not nodes:
            continue
        for node in nodes:
            ps = node.find_all("p")
            if ps:
                for p in ps:
                    t = p.get_text().strip()
                    if len(t) >= min_chars:
                        chunks.append(t)
            else:
                t = node.get_text().strip()
                if len(t) >= min_chars:
                    chunks.append(t)
        if chunks:
            break
    return " ".join(chunks)

def extract_article_content(url, max_length=4000, summary_sentences=4):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, None
        soup = BeautifulSoup(response.content, 'html.parser')
        article_text = ""
        
        # Try to find article content
        article_tag = soup.find('article')
        if article_tag:
            ps = article_tag.find_all('p')
            article_text = " ".join([p.get_text().strip() for p in ps if len(p.get_text().strip()) > 30])
        
        if not article_text or len(article_text) < 200:
            selectors = [
                '.post-content', '.post__content', '.article-content', '.entry-content',
                '.content', 'main', '.article', '.post', 'div[class*="article"]', 'div[class*="post"]'
            ]
            article_text = _extract_from_selectors(soup, selectors, min_chars=25)
        
        if not article_text or len(article_text) < 200:
            paragraphs = soup.find_all('p')
            article_text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
        
        if not article_text:
            page_text = soup.get_text(separator=" ", strip=True)
            if len(page_text) < 100:
                return None, None
            article_text = page_text

        cleaned_content = clean_text(article_text)
        if len(cleaned_content) > max_length:
            cleaned_content = cleaned_content[:max_length].rsplit('.', 1)[0] + '.'

        # Use simple summarizer instead of sumy
        if len(cleaned_content.split()) > 40:
            summary_text = simple_summarize(cleaned_content, sentence_count=summary_sentences)
        else:
            summary_text = cleaned_content
            
        return cleaned_content.strip(), summary_text.strip()
    except Exception as e:
        print(f"Warning: Error extracting article from {url}: {e}")
        return None, None

def get_combined_text_from_entry(entry):
    texts = []
    if hasattr(entry, 'title') and entry.title:
        texts.append(entry.title)
    if hasattr(entry, 'content') and entry.content:
        if isinstance(entry.content, list):
            for content_item in entry.content:
                if hasattr(content_item, 'value'):
                    texts.append(content_item.value)
        else:
            texts.append(str(entry.content))
    if hasattr(entry, 'summary') and entry.summary:
        texts.append(entry.summary)
    if hasattr(entry, 'description') and entry.description:
        texts.append(entry.description)
    combined = " ".join(texts)
    return clean_text(combined)

def get_enhanced_content(entry, extract_full_articles=True, summary_sentences=4):
    combined_text = get_combined_text_from_entry(entry)
    if extract_full_articles and (not combined_text or len(combined_text) < 300) and hasattr(entry, 'link'):
        print(f"Fetching full article content...")
        full_article, summary_article = extract_article_content(entry.link, summary_sentences=summary_sentences)
        if full_article:
            print(f"Got full article content ({len(full_article)} chars)")
            if len(full_article.split()) > 40:
                summary = simple_summarize(full_article, sentence_count=summary_sentences)
            else:
                summary = full_article
            return full_article, summary
    if combined_text:
        if len(combined_text.split()) > 40:
            summary = simple_summarize(combined_text, sentence_count=summary_sentences)
        else:
            summary = combined_text
        return combined_text, summary
    return None, None

def fetch_rss_headlines(rss_feeds, coin_name=None, coin_symbol=None, extract_full_articles=True, max_per_feed=10, summary_sentences=4):
    all_news = []
    for feed_url in rss_feeds:
        try:
            feed = feedparser.parse(feed_url)
            print(f"Parsing feed: {feed_url} - Found {len(feed.entries)} entries")
            for i, entry in enumerate(feed.entries):
                if extract_full_articles and i > 0:
                    time.sleep(0.5)
                    
                title = clean_text(entry.get("title", "")) or ""
                full_text, summary_text = get_enhanced_content(entry, extract_full_articles, summary_sentences)
                summary_news = summary_text or ""
                full_text = full_text or summary_news or ""
                link = entry.get("link", "")
                published = entry.get("published", "")
                source = feed.feed.get("title", "Unknown Source")

                combined = f"{title}. {summary_news}"
                print(f"'{title[:80]}...' | Summary length: {len(summary_news)} | Full length: {len(full_text)}")

                if coin_name and coin_symbol:
                    if (coin_name.lower() in combined.lower()) or (coin_symbol.lower() in combined.lower()):
                        all_news.append({
                            "title": title,
                            "summary_news": summary_news,
                            "full_text": full_text,
                            "published": published,
                            "source": source,
                            "link": link,
                            "text": combined
                        })
                else:
                    all_news.append({
                        "title": title,
                        "summary_news": summary_news,
                        "full_text": full_text,
                        "published": published,
                        "source": source,
                        "link": link,
                        "text": combined
                    })
                if i >= max_per_feed - 1:
                    break
        except Exception as e:
            print(f"Error parsing feed: {feed_url} - {e}")
    print(f"Total news items collected: {len(all_news)}")
    return all_news