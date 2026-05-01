"""
JustDial scraper — India's largest SMB directory.
Primary method: JSON-LD schema data (fastest, most reliable).
Fallback: HTML parsing.
Optional: Apify actor (if APIFY_TOKEN in .env).
"""
import json
import os
import re
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.justdial.com/",
    "DNT": "1",
    "Connection": "keep-alive",
}

PHONE_RE = re.compile(r"(?:\+91[-\s]?)?[6-9]\d{9}")


def _fmt(s: str) -> str:
    return s.strip().replace(" ", "-").title()


def _extract_phone(text: str) -> str:
    m = PHONE_RE.search(text.replace(" ", "").replace("-", ""))
    return m.group() if m else ""


async def _scrape_apify(industry: str, city: str, token: str) -> List[Dict]:
    """Use Apify free tier ($5/month credit) for reliable JustDial data."""
    payload = {
        "city": city,
        "category": industry,
        "maxItems": 50,
    }
    actor_id = "thirdwatch~justdial-business-scraper"
    url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items?token={token}&timeout=60"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90),
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
            "address": item.get("address") or item.get("fullAddress") or city,
            "website": item.get("website") or item.get("websiteUrl") or "",
            "email": item.get("email") or "",
            "rating": float(item.get("rating") or item.get("ratingValue") or 0),
            "category": industry,
            "source": "JustDial (Apify)",
        })
    return leads


async def _scrape_html(industry: str, city: str) -> List[Dict]:
    city_fmt = _fmt(city)
    ind_fmt = _fmt(industry)
    urls = [
        f"https://www.justdial.com/{city_fmt}/{ind_fmt}",
        f"https://www.justdial.com/{city_fmt}/{ind_fmt}-Services",
        f"https://www.justdial.com/{city_fmt}/{ind_fmt}-in-{city_fmt}",
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

    # Method 1 — JSON-LD structured data (most reliable when present)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
            if isinstance(data, list):
                items = data
            elif data.get("@type") == "ItemList":
                items = [el.get("item", {}) for el in data.get("itemListElement", [])]
            else:
                items = [data]

            for item in items:
                btype = item.get("@type", "")
                if not any(t in btype for t in ("Business", "Restaurant", "Store",
                                                  "Organization", "Service")):
                    continue
                name = item.get("name", "").strip()
                if not name or len(name) < 3:
                    continue

                phone = item.get("telephone", "")
                website = item.get("url", "") or item.get("sameAs", "")
                if isinstance(website, list):
                    website = website[0] if website else ""
                email = item.get("email", "")
                rating_obj = item.get("aggregateRating") or {}
                rating = float(rating_obj.get("ratingValue", 0) or 0)

                addr_obj = item.get("address") or {}
                if isinstance(addr_obj, str):
                    address = addr_obj
                else:
                    address = ", ".join(filter(None, [
                        addr_obj.get("streetAddress", ""),
                        addr_obj.get("addressLocality", ""),
                        addr_obj.get("addressRegion", ""),
                    ])) or city

                leads.append({
                    "name": name,
                    "phone": phone,
                    "address": address,
                    "website": website,
                    "email": email,
                    "rating": rating,
                    "category": industry,
                    "source": "JustDial",
                })
        except Exception:
            continue

    # Method 2 — HTML card parsing fallback
    if not leads:
        for card in soup.select(".resultbox_info, .jsx-parser, .store-info")[:30]:
            name_el = card.select_one(".store-name a, .bname a, .fn, h2 a, h3 a")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name:
                continue

            phone = ""
            phone_el = card.select_one(".contact-info, .mobilesv, .mob-num")
            if phone_el:
                phone = _extract_phone(phone_el.get_text())

            addr_el = card.select_one(".address-info, .item-address, .address")
            address = addr_el.get_text(strip=True) if addr_el else city

            rating = 0.0
            rating_el = card.select_one(".green-box, .rating-count, .rtings")
            if rating_el:
                try:
                    rating = float(rating_el.get_text(strip=True).split()[0])
                except Exception:
                    pass

            website = ""
            for link in card.select("a[href]"):
                href = link.get("href", "")
                if href.startswith("http") and "justdial.com" not in href:
                    website = href
                    break

            leads.append({
                "name": name,
                "phone": phone,
                "address": address,
                "website": website,
                "email": "",
                "rating": rating,
                "category": industry,
                "source": "JustDial",
            })

    return leads[:40]


async def scrape(industry: str, city: str) -> List[Dict]:
    token = os.getenv("APIFY_TOKEN", "").strip()
    if token:
        result = await _scrape_apify(industry, city, token)
        if result:
            return result
    return await _scrape_html(industry, city)
