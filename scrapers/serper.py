"""
Google Maps via Serper.dev — 2,500 FREE searches/month, no credit card.
Sign up at https://serper.dev — get API key instantly.
Set SERPER_API_KEY in .env to enable.
"""
import os
import aiohttp
from typing import List, Dict


async def scrape(industry: str, city: str) -> List[Dict]:
    api_key = os.getenv("SERPER_API_KEY", "").strip()
    if not api_key:
        return []

    queries = [
        f"{industry} in {city}",
        f"{industry} services {city}",
    ]

    all_places: list = []
    seen_names: set = set()

    async with aiohttp.ClientSession() as session:
        for q in queries:
            try:
                async with session.post(
                    "https://google.serper.dev/maps",
                    json={"q": q, "gl": "in", "hl": "en", "num": 20},
                    headers={
                        "X-API-KEY": api_key,
                        "Content-Type": "application/json",
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    for place in data.get("places", []):
                        title = (place.get("title") or "").strip()
                        if not title or title.lower() in seen_names:
                            continue
                        seen_names.add(title.lower())
                        all_places.append(place)
            except Exception:
                continue

    leads = []
    for place in all_places[:40]:
        leads.append({
            "name": place.get("title", "").strip(),
            "phone": place.get("phoneNumber", "").strip(),
            "address": place.get("address", "").strip(),
            "website": place.get("website", "").strip(),
            "rating": float(place.get("rating") or 0),
            "category": place.get("category", industry),
            "source": "Google Maps",
            "email": "",
            "notes": place.get("description", ""),
        })

    return leads
