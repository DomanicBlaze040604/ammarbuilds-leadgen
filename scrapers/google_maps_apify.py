"""
Google Maps via Apify Compass actor (compass/crawler-google-places).
THE BEST source — returns name, phone, website, email, address, rating,
reviews, categories, opening hours, social media links, and more.

$2.10 per 1,000 places — your $5 free credit = ~2,380 places/month.
Set APIFY_TOKEN in .env to enable.
"""
import os
import aiohttp
from typing import List, Dict


ACTOR_ID = "compass~crawler-google-places"


async def scrape(industry: str, city: str) -> List[Dict]:
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        return []

    run_input = {
        "searchStringsArray": [
            f"{industry} in {city}",
        ],
        "locationQuery": city,
        "maxCrawledPlacesPerSearch": 40,
        "language": "en",
        "deeperCityScrape": False,
        "skipClosedPlaces": True,
        "includeWebResults": False,
        "scrapeContacts": False,       # Free tier: don't use paid add-ons
        "scrapeDirectories": False,
        "scrapeReviewsPersonalData": False,
    }

    # Use run-sync endpoint — waits for completion, returns dataset items
    url = (
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
        f"?token={token}&timeout=120"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=run_input,
                timeout=aiohttp.ClientTimeout(total=150),
            ) as resp:
                if resp.status not in (200, 201):
                    return []
                items = await resp.json(content_type=None)
    except Exception:
        return []

    if not isinstance(items, list):
        return []

    leads = []
    for item in items[:50]:
        title = (item.get("title") or "").strip()
        if not title:
            continue

        website = (item.get("website") or "").strip()
        phone = (
            item.get("phone") or item.get("phoneUnformatted") or ""
        ).strip()

        # Build address from structured fields
        address_parts = [
            item.get("street", ""),
            item.get("neighborhood", ""),
            item.get("city", city),
            item.get("state", ""),
        ]
        address = ", ".join(p for p in address_parts if p) or item.get("address", city)

        leads.append({
            "name": title,
            "phone": phone,
            "address": address,
            "website": website,
            "email": "",  # Maps rarely exposes email in basic mode
            "rating": float(item.get("totalScore") or 0),
            "category": item.get("categoryName", industry),
            "source": "Google Maps (Apify)",
            "notes": f"Reviews: {item.get('reviewsCount', 0)} | "
                     f"Place ID: {item.get('placeId', '')}",
        })

    return leads


async def scrape_with_contacts(industry: str, city: str) -> List[Dict]:
    """
    Enhanced version: uses Company contacts enrichment add-on.
    Returns social media links (Instagram, Facebook, LinkedIn, YouTube, TikTok).
    More expensive — only use if you have budget.
    """
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        return []

    run_input = {
        "searchStringsArray": [f"{industry} in {city}"],
        "locationQuery": city,
        "maxCrawledPlacesPerSearch": 25,
        "language": "en",
        "skipClosedPlaces": True,
        "scrapeContacts": True,  # Paid add-on: $0.50 per company
    }

    url = (
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
        f"?token={token}&timeout=120"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=run_input,
                timeout=aiohttp.ClientTimeout(total=150),
            ) as resp:
                if resp.status not in (200, 201):
                    return []
                items = await resp.json(content_type=None)
    except Exception:
        return []

    if not isinstance(items, list):
        return []

    leads = []
    for item in items[:30]:
        title = (item.get("title") or "").strip()
        if not title:
            continue

        socials = []
        for key in ("instagrams", "facebooks", "linkedIns", "youtubes", "tiktoks"):
            urls_list = item.get(key) or []
            if urls_list:
                socials.append(f"{key}: {urls_list[0]}")

        leads.append({
            "name": title,
            "phone": (item.get("phone") or "").strip(),
            "address": item.get("address", city),
            "website": (item.get("website") or "").strip(),
            "email": "",
            "rating": float(item.get("totalScore") or 0),
            "category": item.get("categoryName", industry),
            "source": "Google Maps (Apify+)",
            "notes": " | ".join(socials) if socials else "",
        })

    return leads
