"""
RSS news ingester — pulls from Indian financial media feeds.
Filters articles by ticker mentions, deduplicates, and stores chunks.
"""
import asyncio
import hashlib
import re
from datetime import datetime, timezone
from typing import Optional
from email.utils import parsedate_to_datetime

import feedparser
import httpx
from bs4 import BeautifulSoup

# Indian financial news RSS feeds
NEWS_FEEDS = [
    {
        "name": "Economic Times Markets",
        "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    },
    {
        "name": "Economic Times Stocks",
        "url": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    },
    {
        "name": "Moneycontrol Top News",
        "url": "https://www.moneycontrol.com/rss/MCtopnews.xml",
    },
    {
        "name": "LiveMint Markets",
        "url": "https://www.livemint.com/rss/markets",
    },
    {
        "name": "Business Standard Markets",
        "url": "https://www.business-standard.com/rss/markets-106.rss",
    },
]

# Compile regex for common Indian company names → tickers
COMPANY_ALIASES: dict[str, list[str]] = {
    "RELIANCE": ["Reliance Industries", "Reliance", "RIL"],
    "TCS": ["Tata Consultancy", "TCS"],
    "HDFCBANK": ["HDFC Bank", "HDFCBank"],
    "INFY": ["Infosys", "INFY"],
    "ICICIBANK": ["ICICI Bank", "ICICI"],
    "WIPRO": ["Wipro"],
    "SBIN": ["State Bank", "SBI", "SBIN"],
    "BAJFINANCE": ["Bajaj Finance"],
    "HINDUNILVR": ["Hindustan Unilever", "HUL"],
    "ITC": ["ITC"],
    "AXISBANK": ["Axis Bank"],
    "KOTAKBANK": ["Kotak Mahindra", "Kotak Bank"],
    "LT": ["Larsen & Toubro", "L&T"],
    "TATAMOTORS": ["Tata Motors"],
    "TATASTEEL": ["Tata Steel"],
    "MARUTI": ["Maruti Suzuki", "Maruti"],
    "ADANIENT": ["Adani Enterprises", "Adani"],
    "ADANIPORTS": ["Adani Ports"],
    "NTPC": ["NTPC"],
    "POWERGRID": ["Power Grid"],
    "ONGC": ["ONGC", "Oil and Natural Gas"],
    "M&M": ["Mahindra & Mahindra", "M&M", "Mahindra"],
    "SUNPHARMA": ["Sun Pharmaceutical", "Sun Pharma"],
    "DRREDDY": ["Dr. Reddy", "Dr Reddy"],
    "CIPLA": ["Cipla"],
    "BHARTIARTL": ["Bharti Airtel", "Airtel"],
    "JSWSTEEL": ["JSW Steel"],
    "ULTRACEMCO": ["UltraTech Cement", "UltraTech"],
}


def find_tickers_in_text(text: str) -> list[str]:
    """Find which tickers are mentioned in the given text."""
    text_lower = text.lower()
    found = set()

    for ticker, aliases in COMPANY_ALIASES.items():
        for alias in aliases:
            if alias.lower() in text_lower:
                found.add(ticker)
                break

    return list(found)


def make_content_hash(url: str, title: str) -> str:
    """SHA-256 hash for deduplication."""
    raw = f"{url}::{title}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def parse_published_date(entry) -> Optional[datetime]:
    """Parse RSS published date to timezone-aware datetime."""
    for attr in ("published", "updated", "created"):
        val = getattr(entry, attr, None)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass
    return None


async def fetch_article_text(url: str, timeout: float = 8.0) -> str:
    """Fetch and extract main text content from an article URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; EquityBot/1.0; +https://example.com)",
        }
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return ""

        soup = BeautifulSoup(resp.text, "lxml")

        # Remove nav, ads, scripts, etc.
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
            tag.decompose()

        # Try common article content selectors
        for selector in [
            "article", ".article-body", ".story-content", ".content-wrapper",
            ".article__content", "main", "#content", ".post-content",
        ]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(separator="\n", strip=True)
                if len(text) > 200:
                    return text[:3000]  # Cap at 3000 chars

        # Fallback: all paragraphs
        paras = soup.find_all("p")
        text = "\n".join(p.get_text(strip=True) for p in paras if len(p.get_text(strip=True)) > 40)
        return text[:3000]

    except Exception:
        return ""


async def fetch_feed_entries(feed_url: str, source_name: str) -> list[dict]:
    """Fetch and parse a single RSS feed."""
    try:
        loop = asyncio.get_event_loop()
        parsed = await loop.run_in_executor(None, feedparser.parse, feed_url)
        entries = []

        for entry in parsed.entries[:30]:  # Max 30 per feed
            url = entry.get("link", "")
            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")

            if not url or not title:
                continue

            content_hash = make_content_hash(url, title)
            published = parse_published_date(entry)

            # Find ticker mentions from title + summary
            tickers = find_tickers_in_text(f"{title} {summary}")

            entries.append({
                "source_name": source_name,
                "source_url": url,
                "title": title,
                "summary": summary,
                "content_hash": content_hash,
                "published_at": published,
                "tickers_mentioned": tickers,
            })

        return entries
    except Exception as e:
        return []


async def fetch_all_feeds_for_ticker(ticker: str) -> list[dict]:
    """
    Fetch articles mentioning a specific ticker from all feeds.
    Returns list of article dicts ready for embedding.
    """
    # Fetch all feeds concurrently
    tasks = [fetch_feed_entries(f["url"], f["name"]) for f in NEWS_FEEDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    articles = []
    seen_hashes = set()

    for feed_entries in results:
        if isinstance(feed_entries, Exception):
            continue
        for entry in feed_entries:
            if ticker in entry.get("tickers_mentioned", []):
                h = entry["content_hash"]
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    articles.append(entry)

    # Enrich with full article text (concurrently, max 5 at a time)
    sem = asyncio.Semaphore(5)

    async def fetch_with_sem(article: dict) -> dict:
        async with sem:
            text = await fetch_article_text(article["source_url"])
            article["full_text"] = text or article.get("summary", "")
            return article

    enriched = await asyncio.gather(*[fetch_with_sem(a) for a in articles])
    return list(enriched)
