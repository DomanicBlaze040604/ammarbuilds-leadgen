"""
Sulekha + TradeIndia scraper — two more major Indian SMB directories.
Free HTTP scraping — no API key needed.
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

PHONE_RE = re.compile(r"[6-9]\d{9}")


def _phone(text: str) -> str:
    m = PHONE_RE.search(re.sub(r"[\s\-\(\)\+]", "", text))
    return m.group() if m else ""


async def _scrape_sulekha(industry: str, city: str) -> List[Dict]:
    city_slug = city.lower().replace(" ", "-")
    ind_slug = industry.lower().replace(" ", "-")
    url = f"https://www.sulekha.com/{ind_slug}/{city_slug}"

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=20), allow_redirects=True
            ) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
    except Exception:
        return []

    soup = BeautifulSoup(html, "lxml")
    leads = []

    cards = soup.select(".exp-prov-card, .service-provider-card, .provider-info, .busname")
    for card in cards[:30]:
        name_el = card.select_one("h2 a, h3 a, .busname, .spname, .title a")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name:
            continue

        phone = ""
        for sel in [".mobile", ".phone", "[class*='phone']", "[class*='mobile']"]:
            el = card.select_one(sel)
            if el:
                phone = _phone(el.get_text())
                if phone:
                    break

        addr_el = card.select_one(".address, .locality, [class*='addr']")
        address = addr_el.get_text(strip=True) if addr_el else city

        website = ""
        for a in card.select("a[href]"):
            href = a.get("href", "")
            if href.startswith("http") and "sulekha.com" not in href.lower():
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
            "source": "Sulekha",
        })

    return leads


async def _scrape_tradeindia(industry: str, city: str) -> List[Dict]:
    search = f"{industry}-{city}".replace(" ", "-").lower()
    url = f"https://www.tradeindia.com/Sellers/{search}/"

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=20), allow_redirects=True
            ) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
    except Exception:
        return []

    soup = BeautifulSoup(html, "lxml")
    leads = []

    for card in soup.select(".company-detail, .product-info, .seller-info")[:25]:
        name_el = card.select_one("h2 a, h3 a, .company-name a, .biz-name")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name:
            continue

        phone_el = card.select_one(".phone, .tel, [class*='phone']")
        phone = _phone(phone_el.get_text()) if phone_el else ""

        addr_el = card.select_one(".address, .city, [class*='addr']")
        address = addr_el.get_text(strip=True) if addr_el else city

        website = ""
        for a in card.select("a[href]"):
            href = a.get("href", "")
            if href.startswith("http") and "tradeindia" not in href.lower():
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
            "source": "TradeIndia",
        })

    return leads


async def scrape(industry: str, city: str) -> List[Dict]:
    sulekha, tradeindia = await _scrape_sulekha(industry, city), []
    try:
        tradeindia = await _scrape_tradeindia(industry, city)
    except Exception:
        pass
    return sulekha + tradeindia
