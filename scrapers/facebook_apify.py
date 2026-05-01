"""
Facebook Pages & Groups scraper via Apify.
Finds local businesses that have a Facebook page but no website.

Actors used:
- apify/facebook-pages-scraper — Scrapes FB page details
- apify/facebook-search-scraper — Searches FB for businesses

Set APIFY_TOKEN in .env to enable.
"""
import os
import aiohttp
from typing import List, Dict


async def scrape(industry: str, city: str) -> List[Dict]:
    """Search Facebook for local businesses."""
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        return []

    # Use Facebook Search Scraper to find businesses
    run_input = {
        "searchQueries": [f"{industry} {city}"],
        "maxResults": 30,
        "searchType": "pages",
    }

    # Try the Facebook pages scraper actor
    actor_id = "apify~facebook-pages-scraper"
    url = (
        f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
        f"?token={token}&timeout=90"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=run_input,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status not in (200, 201):
                    # Fallback: try search scraper
                    return await _search_fallback(industry, city, token)
                items = await resp.json(content_type=None)
    except Exception:
        return await _search_fallback(industry, city, token)

    if not isinstance(items, list):
        return []

    leads = []
    for item in items[:30]:
        name = (
            item.get("name") or item.get("title") or item.get("pageName") or ""
        ).strip()
        if not name:
            continue

        website = item.get("website") or item.get("url") or ""
        # If website is a facebook.com URL, the business has NO real website
        if "facebook.com" in website:
            website = ""

        phone = item.get("phone") or item.get("phoneNumber") or ""
        email = item.get("email") or ""
        address = item.get("address") or item.get("location") or city
        if isinstance(address, dict):
            address = ", ".join(
                str(v) for v in address.values() if v
            ) or city

        category = item.get("category") or item.get("categories") or industry
        if isinstance(category, list):
            category = ", ".join(category[:2])

        followers = item.get("likes") or item.get("followers") or 0
        fb_url = item.get("pageUrl") or item.get("facebookUrl") or ""

        leads.append({
            "name": name,
            "phone": phone,
            "address": address,
            "website": website,
            "email": email,
            "rating": 0.0,
            "category": category,
            "source": "Facebook (Apify)",
            "notes": f"FB followers: {followers} | {fb_url}",
        })

    return leads


async def _search_fallback(industry: str, city: str, token: str) -> List[Dict]:
    """Fallback: use generic Facebook search."""
    run_input = {
        "searchQueries": [f"{industry} in {city}"],
        "maxPagesPerSearch": 3,
    }

    actor_id = "apify~facebook-search-scraper"
    url = (
        f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
        f"?token={token}&timeout=60"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=run_input,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                if resp.status not in (200, 201):
                    return []
                items = await resp.json(content_type=None)
    except Exception:
        return []

    if not isinstance(items, list):
        return []

    leads = []
    for item in items[:20]:
        name = (item.get("name") or item.get("title") or "").strip()
        if not name or len(name) < 3:
            continue

        leads.append({
            "name": name,
            "phone": item.get("phone", ""),
            "address": item.get("address", city),
            "website": "",  # FB search results rarely have website
            "email": item.get("email", ""),
            "rating": 0.0,
            "category": industry,
            "source": "Facebook Search",
            "notes": item.get("description", "")[:100],
        })

    return leads
