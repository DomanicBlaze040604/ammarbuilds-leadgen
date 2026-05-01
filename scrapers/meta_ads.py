"""
Meta Ads Library — Find businesses running Facebook/Instagram ads.
WHY THIS IS GOLD: businesses spending on Meta ads WITHOUT a website = perfect web dev leads.
They have marketing budget but no landing page to convert visitors!

FREE public API — just needs a Facebook access token.
Get one FREE at: https://developers.facebook.com/tools/explorer/
(No app review needed for Ads Library — it's public data)
Set META_ACCESS_TOKEN in .env to enable.
"""
import os
from datetime import datetime, timedelta
import aiohttp
from typing import List, Dict


async def scrape(industry: str, city: str) -> List[Dict]:
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    if not token:
        return []

    # Search for ads related to the industry in the country
    # Meta Ads Library API: https://www.facebook.com/ads/library/api/
    base_url = "https://graph.facebook.com/v19.0/ads_archive"

    # Date 6 months ago for recent ads
    six_months_ago = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

    params = {
        "access_token": token,
        "ad_reached_countries": "IN",  # India — change if needed
        "search_terms": f"{industry} {city}",
        "ad_delivery_date_min": six_months_ago,
        "ad_active_status": "ALL",
        "fields": "page_name,page_id,ad_snapshot_url,spend,impressions,ad_creation_time",
        "limit": 50,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                base_url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
    except Exception:
        return []

    leads = []
    seen_pages: set = set()

    for ad in data.get("data", []):
        page_name = (ad.get("page_name") or "").strip()
        page_id = ad.get("page_id", "")
        if not page_name or page_name.lower() in seen_pages:
            continue
        seen_pages.add(page_name.lower())

        # Construct Facebook page URL
        fb_url = f"https://www.facebook.com/{page_id}" if page_id else ""

        leads.append({
            "name": page_name,
            "phone": "",
            "address": city,
            "website": "",  # No website — they only have FB page, perfect lead!
            "email": "",
            "rating": 0.0,
            "category": industry,
            "source": "Meta Ads Library",
            "notes": f"Running Facebook/Instagram ads | Page: {fb_url}",
        })

    return leads[:30]


async def scrape_fb_pages(industry: str, city: str) -> List[Dict]:
    """
    Search Facebook Pages for local businesses — shows who has only FB presence.
    Same token as Meta Ads Library.
    """
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    if not token:
        return []

    params = {
        "access_token": token,
        "q": f"{industry} {city}",
        "type": "page",
        "fields": "name,phone,website,location,category,fan_count,about",
        "limit": 50,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://graph.facebook.com/v19.0/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
    except Exception:
        return []

    leads = []
    for page in data.get("data", []):
        name = (page.get("name") or "").strip()
        if not name:
            continue
        loc = page.get("location") or {}
        address_parts = [
            loc.get("street", ""),
            loc.get("city", city),
            loc.get("state", ""),
        ]
        address = ", ".join(p for p in address_parts if p) or city

        leads.append({
            "name": name,
            "phone": page.get("phone", ""),
            "address": address,
            "website": page.get("website", ""),  # Empty = they need one!
            "email": "",
            "rating": 0.0,
            "category": page.get("category", industry),
            "source": "Facebook Pages",
            "notes": f"FB fans: {page.get('fan_count', 0)} | {page.get('about', '')[:80]}",
        })

    return leads[:25]
