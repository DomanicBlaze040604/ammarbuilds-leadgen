"""
Google Ads Transparency Center — completely FREE, no API key needed.
Scrapes the public ads transparency page for businesses running Google Ads.

WHY THIS IS GOLD: A business paying for Google Ads but without a proper
website is a PERFECT client. They're already spending money to get customers
but sending them to a poor landing experience. You can pitch:
"You're paying ₹X/day on ads but losing clicks because your site is weak."

Also great for finding businesses that DO have a website but it's terrible —
you can offer a redesign.
"""
import re
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}


async def scrape(industry: str, city: str) -> List[Dict]:
    """
    Scrape Google Ads Transparency Center for advertisers in industry+city.
    The transparency center shows who is running ads — perfect lead signal.
    """
    query = f"{industry} {city}"
    url = f"https://adstransparency.google.com/advertiser?search={query}&region=IN"

    leads: List[Dict] = []

    # Method 1: Try the transparency center API endpoint
    api_url = "https://adstransparency.google.com/anji/_/rpc/SearchService/SearchAdvertisers"
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            # The transparency center uses an internal RPC — try the public search page
            search_url = f"https://adstransparency.google.com/?search={query.replace(' ', '+')}&region=IN"
            async with session.get(
                search_url,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
    except Exception:
        return []

    # Parse advertiser names from the transparency page
    soup = BeautifulSoup(html, "lxml")

    # Look for advertiser cards/listings
    seen: set = set()

    # Pattern 1: Direct advertiser name elements
    for el in soup.select("[class*='advertiser'], [class*='Advertiser'], [data-advertiser]"):
        name = el.get_text(strip=True)
        if name and len(name) > 3 and name.lower() not in seen:
            seen.add(name.lower())
            leads.append({
                "name": name,
                "phone": "",
                "address": city,
                "website": "",
                "email": "",
                "rating": 0.0,
                "category": industry,
                "source": "Google Ads",
                "notes": f"Running Google Ads in {city} | Found on Ads Transparency Center",
            })

    # Pattern 2: Extract from structured data or scripts
    for script in soup.find_all("script"):
        text = script.string or ""
        # Look for advertiser names in JSON-like structures
        names = re.findall(r'"advertiserName"\s*:\s*"([^"]{3,60})"', text)
        for name in names:
            if name.lower() not in seen:
                seen.add(name.lower())
                leads.append({
                    "name": name,
                    "phone": "",
                    "address": city,
                    "website": "",
                    "email": "",
                    "rating": 0.0,
                    "category": industry,
                    "source": "Google Ads",
                    "notes": f"Active Google advertiser | Spending money on ads",
                })

    return leads[:25]


async def scrape_google_serp_ads(industry: str, city: str) -> List[Dict]:
    """
    Alternative: Use Serper.dev to find businesses running Google search ads.
    Shows who is paying for ads — they have budget!
    Requires SERPER_API_KEY in .env.
    """
    import os
    api_key = os.getenv("SERPER_API_KEY", "").strip()
    if not api_key:
        return []

    leads = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://google.serper.dev/search",
                json={
                    "q": f"{industry} in {city}",
                    "gl": "in",
                    "hl": "en",
                    "num": 10,
                },
                headers={
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
    except Exception:
        return []

    # Extract from paid ads section
    for ad in data.get("ads", []):
        title = (ad.get("title") or "").strip()
        if not title:
            continue

        # Clean the ad title to get business name
        # Ads often have format: "Business Name - Tagline | Brand"
        name = title.split(" - ")[0].split(" | ")[0].strip()

        link = ad.get("link", "")
        domain = ""
        if link:
            from urllib.parse import urlparse
            try:
                domain = urlparse(link).netloc
            except Exception:
                pass

        leads.append({
            "name": name,
            "phone": "",
            "address": city,
            "website": link,
            "email": "",
            "rating": 0.0,
            "category": industry,
            "source": "Google Ads (SERP)",
            "notes": f"Paying for Google Ads | Domain: {domain}",
        })

    return leads[:15]
