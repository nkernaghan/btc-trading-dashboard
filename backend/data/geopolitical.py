"""Geopolitical risk data from GDELT (free, no API key needed)."""
import httpx
import json
import logging
from redis_client import get_redis

logger = logging.getLogger(__name__)

GDELT_BASE = "https://api.gdeltproject.org/api/v2/doc/doc"


async def fetch_geopolitical_events():
    """Fetch recent geopolitical events relevant to crypto/markets from GDELT."""
    r = await get_redis()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Get crypto-relevant geopolitical news
            resp = await client.get(GDELT_BASE, params={
                "query": "(war OR conflict OR sanctions OR military OR tariff OR nuclear OR missile OR iran OR china OR russia) (bitcoin OR crypto OR market OR economy)",
                "mode": "ArtList",
                "maxrecords": 15,
                "format": "json",
                "timespan": "3d",
            })
            if resp.status_code == 200:
                data = resp.json()
                articles = data.get("articles", [])
                events = []
                for a in articles:
                    events.append({
                        "title": a.get("title", ""),
                        "source": a.get("domain", ""),
                        "date": a.get("seendate", ""),
                        "country": a.get("sourcecountry", ""),
                        "url": a.get("url", ""),
                    })
                await r.set("geopolitical:events", json.dumps(events))
                logger.info(f"Geopolitical events updated: {len(events)} articles")
    except Exception as e:
        logger.error(f"Geopolitical events fetch error: {e}")


async def fetch_geopolitical_tone():
    """Fetch overall geopolitical tone/sentiment from GDELT.
    Negative tone = more conflict/tension = risk-off for markets."""
    r = await get_redis()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Get tone chart for conflict-related news
            resp = await client.get(GDELT_BASE, params={
                "query": "war OR conflict OR sanctions OR military OR tariff",
                "mode": "ToneChart",
                "format": "json",
                "timespan": "7d",
            })
            if resp.status_code == 200:
                data = resp.json()
                tone_data = data.get("tonechart", [])
                if tone_data:
                    # Average the recent tone values
                    # GDELT tone: negative = bad news, positive = good news
                    recent_tones = [float(t.get("tone", 0)) for t in tone_data[-24:] if t.get("tone")]
                    avg_tone = sum(recent_tones) / len(recent_tones) if recent_tones else 0

                    result = {
                        "avg_tone_24h": round(avg_tone, 3),
                        "tone_trend": "deteriorating" if avg_tone < -3 else "stable" if avg_tone > -1 else "elevated_risk",
                        "data_points": len(recent_tones),
                    }
                    await r.set("geopolitical:tone", json.dumps(result))
                    logger.info(f"Geopolitical tone updated: avg={avg_tone:.2f}")
    except Exception as e:
        logger.error(f"Geopolitical tone fetch error: {e}")


async def fetch_conflict_intensity():
    """Fetch global conflict volume from GDELT — spike in conflict articles = risk-off."""
    r = await get_redis()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(GDELT_BASE, params={
                "query": "war OR conflict OR attack OR bombing OR missile OR invasion",
                "mode": "TimelineVolInfo",
                "format": "json",
                "timespan": "7d",
            })
            if resp.status_code == 200:
                data = resp.json()
                timeline = data.get("timeline", [])
                if timeline and len(timeline) > 0:
                    series = timeline[0].get("data", [])
                    if series:
                        recent = [float(s.get("value", 0)) for s in series[-48:]]
                        older = [float(s.get("value", 0)) for s in series[-96:-48]]
                        avg_recent = sum(recent) / len(recent) if recent else 0
                        avg_older = sum(older) / len(older) if older else avg_recent
                        change_pct = ((avg_recent - avg_older) / max(avg_older, 1)) * 100

                        result = {
                            "conflict_volume_recent": round(avg_recent, 1),
                            "conflict_volume_prior": round(avg_older, 1),
                            "change_pct": round(change_pct, 1),
                            "elevated": change_pct > 20,
                        }
                        await r.set("geopolitical:conflict", json.dumps(result))
                        logger.info(f"Conflict intensity: {change_pct:+.1f}% change")
    except Exception as e:
        logger.error(f"Conflict intensity fetch error: {e}")
