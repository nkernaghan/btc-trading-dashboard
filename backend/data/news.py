"""News fetchers — NewsAPI + RSS feeds. ETF flows live in data/etf.py."""

import json
import logging
import xml.etree.ElementTree as ET

import httpx

from config import settings
from redis_client import get_redis, set_with_ts

logger = logging.getLogger(__name__)

BTC_KEYWORDS = [
    "bitcoin", "btc", "crypto", "cryptocurrency", "blockchain",
    "halving", "mining", "satoshi", "lightning network", "etf",
]

RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]


def _is_btc_relevant(title: str, description: str = "") -> bool:
    """Check if an article is BTC-relevant based on keywords."""
    text = (title + " " + description).lower()
    return any(kw in text for kw in BTC_KEYWORDS)


async def _fetch_rss(client: httpx.AsyncClient, url: str) -> list[dict]:
    """Parse RSS feed and return list of article dicts."""
    articles = []
    try:
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        for item in root.iter("item"):
            title = item.findtext("title", "")
            description = item.findtext("description", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")

            if _is_btc_relevant(title, description):
                articles.append(
                    {
                        "title": title,
                        "description": description[:500],
                        "url": link,
                        "published_at": pub_date,
                        "source": "rss",
                    }
                )
    except Exception as e:
        logger.warning("RSS fetch failed for %s: %s", url, e)

    return articles


async def fetch_news_api():
    """Fetch BTC-relevant news from NewsAPI and RSS feeds. Store in Redis."""
    try:
        articles = []

        async with httpx.AsyncClient(timeout=15) as client:
            # NewsAPI
            if settings.newsapi_key:
                try:
                    resp = await client.get(
                        "https://newsapi.org/v2/everything",
                        params={
                            "q": "bitcoin OR BTC OR crypto",
                            "sortBy": "publishedAt",
                            "pageSize": 20,
                            "language": "en",
                            "apiKey": settings.newsapi_key,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    for a in data.get("articles", []):
                        title = a.get("title", "")
                        desc = a.get("description", "")
                        if _is_btc_relevant(title, desc):
                            articles.append(
                                {
                                    "title": title,
                                    "description": (desc or "")[:500],
                                    "url": a.get("url", ""),
                                    "published_at": a.get("publishedAt", ""),
                                    "source": a.get("source", {}).get("name", "NewsAPI"),
                                    "image_url": a.get("urlToImage", ""),
                                }
                            )
                except Exception as e:
                    logger.warning("NewsAPI fetch failed: %s", e)

            # RSS feeds
            for feed_url in RSS_FEEDS:
                rss_articles = await _fetch_rss(client, feed_url)
                articles.extend(rss_articles)

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique_articles = []
        for a in articles:
            url = a.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(a)

        r = await get_redis()
        await set_with_ts(r, "news:articles", json.dumps(unique_articles))
        logger.info("Stored %d BTC news articles", len(unique_articles))

    except Exception as e:
        logger.error("fetch_news_api failed: %s", e)
