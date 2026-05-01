"""
IndiaMART scraper — India's largest B2B marketplace.
Free HTTP scraping — no API key needed.
Optional: Apify actor (APIFY_TOKEN in .env).
"""
import os
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
    "Referer": "https://dir.indiamart.com/",
}

PHONE_RE = re.compile(r"[6-9]\d{9}")


def _extract_phone(text: str) -> str:
    clean = re.sub(r"[\s\-\(\)]", "", text)
    m = PHONE_RE.search(clean)
    return m.group() if m else ""


async def _scrape_apify(industry: str, city: str, token: str) -> List[Dict]:
    payload = {"city": city, "category": industry, "maxItems": 50}
    actor_id = "thirdwatch~indiamart-supplier-scraper"
    url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items?token={token}&timeout=60"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=90)
            ) as resp:
                if resp.status not in (200, 201):
                    return []
                items = await resp.json(content_type=None)
    except Exception:
        return []

    leads = []
    for item in (items if isinstance(items, list) else []):
        name = item.get("name") or item.get("companyName") or ""
        if not name:
            continue
        leads.append({
            "name": name,
            "phone": item.get("phone") or item.get("mobile") or "",
            "address": item.get("address") or item.get("city") or city,
            "website": item.get("website") or "",
            "email": item.get("email") or "",
            "rating": 0.0,
            "category": industry,
            "source": "IndiaMART (Apify)",
        })
    return leads


async def _scrape_html(industry: str, city: str) -> List[Dict]:
    search = f"{industry} {city}".replace(" ", "+")
    urls = [
        f"https://dir.indiamart.com/search.mp?ss={search}&prdsrc=1",
        f"https://dir.indiamart.com/{city.lower().replace(' ', '-')}/{industry.lower().replace(' ', '-')}.html",
    ]

    html = ""
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        for url in urls:
            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=20), allow_redirects=True
                ) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        if len(html) > 5000:
                            break
            except Exception:
                continue

    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    leads = []

    # IndiaMART company cards — selectors vary across page types
    selectors = [
        ".ld",
        ".bx",
        ".company-info",
        "[class*='company']",
        ".prod-listing",
    ]
    cards = []
    for sel in selectors:
        cards = soup.select(sel)
        if cards:
            break

    for card in cards[:40]:
        name_el = card.select_one("h2 a, h3 a, .compname a, .bname a, .company-name a")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if len(name) < 3:
            continue

        phone = ""
        for ph_sel in [".mob", ".ph", "[class*='phone']", "[class*='mobile']", ".contact"]:
            ph_el = card.select_one(ph_sel)
            if ph_el:
                phone = _extract_phone(ph_el.get_text())
                if phone:
                    break

        addr_el = card.select_one(".add, .address, [class*='addr'], .location")
        address = addr_el.get_text(strip=True) if addr_el else city

        website = ""
        for a in card.select("a[href]"):
            href = a.get("href", "")
            if href.startswith("http") and "indiamart" not in href.lower():
                website = href
                break

        leads.append({
            "name": name,
            "phone": phone,
            "address": address,
            "website": website,
            "email": "",
            "rating": 0.0,
            "category": industry,
            "source": "IndiaMART",
        })

    return leads


async def scrape(industry: str, city: str) -> List[Dict]:
    token = os.getenv("APIFY_TOKEN", "").strip()
    if token:
        result = await _scrape_apify(industry, city, token)
        if result:
            return result
    return await _scrape_html(industry, city)
