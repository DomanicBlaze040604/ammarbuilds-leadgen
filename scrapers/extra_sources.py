"""
Maximum lead volume — ALL possible sources via Apify + free scraping.

Apify actors:
1. Google Search SERP (apify/google-search-scraper)
2. Yelp (apify/yelp-scraper)
3. TripAdvisor (maxcopell/tripadvisor)
4. Yellow Pages India + Grotal
5. Trustpilot (apify/trustpilot-scraper) — businesses with reviews
6. Clutch.co (epctex/clutch-scraper) — agencies, IT companies
7. Glassdoor (apify/glassdoor-scraper) — companies with employees

Free scrapers (no key):
8. Zomato — restaurants in India (HTML scraping)
9. Practo — doctors/clinics in India (HTML scraping)
10. Naukri.com — companies hiring in India (HTML scraping)
11. Foursquare — local businesses (free API)
12. Bing Places — Microsoft's business directory (HTML scraping)
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
}

PHONE_RE = re.compile(r"[6-9]\d{9}")


def _phone(text: str) -> str:
    m = PHONE_RE.search(re.sub(r"[\s\-\(\)\+]", "", text))
    return m.group() if m else ""


# ═══════════════════════════════════════════════════════════════
#  APIFY ACTORS
# ═══════════════════════════════════════════════════════════════

async def _run_apify_actor(actor_id: str, run_input: dict, timeout: int = 90) -> list:
    """Helper: run any Apify actor and return dataset items."""
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        return []
    url = (
        f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
        f"?token={token}&timeout={timeout}"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=run_input,
                timeout=aiohttp.ClientTimeout(total=timeout + 30),
            ) as resp:
                if resp.status not in (200, 201):
                    return []
                items = await resp.json(content_type=None)
                return items if isinstance(items, list) else []
    except Exception:
        return []


# 1. Google Search SERP
async def scrape_google_serp(industry: str, city: str) -> List[Dict]:
    items = await _run_apify_actor("apify~google-search-scraper", {
        "queries": f"{industry} in {city}\n{industry} near {city} contact number",
        "maxPagesPerQuery": 2,
        "resultsPerPage": 20,
        "languageCode": "en",
        "countryCode": "in",
    })

    leads = []
    seen: set = set()
    skip = ("wikipedia", "youtube.com", "facebook.com", "instagram.com",
            "twitter.com", "linkedin.com", "quora.com", "reddit.com",
            "gov.in", ".gov", "timesofindia", "hindustantimes", "ndtv")

    for item in items:
        for result in (item.get("organicResults") or [item]):
            title = (result.get("title") or "").strip()
            link = result.get("url") or result.get("link") or ""
            if not title or title.lower() in seen:
                continue
            if any(d in link.lower() for d in skip):
                continue
            seen.add(title.lower())
            leads.append({
                "name": title, "phone": "", "address": city,
                "website": link, "email": "", "rating": 0.0,
                "category": industry, "source": "Google SERP",
                "notes": (result.get("description") or "")[:120],
            })
    return leads[:25]


# 2. Yelp
async def scrape_yelp(industry: str, city: str) -> List[Dict]:
    items = await _run_apify_actor("apify~yelp-scraper", {
        "searchTerms": [industry], "locations": [city], "maxItems": 30,
    })
    leads = []
    for item in items[:30]:
        name = (item.get("name") or item.get("title") or "").strip()
        if not name:
            continue
        leads.append({
            "name": name,
            "phone": item.get("phone") or item.get("displayPhone") or "",
            "address": item.get("address") or city,
            "website": item.get("website") or "",
            "email": "", "rating": float(item.get("rating") or 0),
            "category": industry, "source": "Yelp",
            "notes": f"Reviews: {item.get('reviewCount', 0)}",
        })
    return leads


# 3. TripAdvisor
async def scrape_tripadvisor(industry: str, city: str) -> List[Dict]:
    items = await _run_apify_actor("maxcopell~tripadvisor", {
        "query": f"{industry} in {city}", "maxItems": 25, "language": "en",
    })
    leads = []
    for item in items[:25]:
        name = (item.get("name") or item.get("title") or "").strip()
        if not name:
            continue
        website = item.get("website") or item.get("webUrl") or ""
        if "tripadvisor" in website.lower():
            website = ""
        addr = item.get("address") or {}
        if isinstance(addr, dict):
            addr = ", ".join(str(v) for v in addr.values() if v) or city
        leads.append({
            "name": name,
            "phone": item.get("phone") or item.get("telephone") or "",
            "address": addr, "website": website,
            "email": item.get("email", ""),
            "rating": float(item.get("rating") or item.get("averageRating") or 0),
            "category": industry, "source": "TripAdvisor",
            "notes": f"Reviews: {item.get('reviewsCount') or item.get('numReviews', 0)}",
        })
    return leads


# 4. Trustpilot
async def scrape_trustpilot(industry: str, city: str) -> List[Dict]:
    items = await _run_apify_actor("apify~trustpilot-scraper", {
        "search": f"{industry} {city}", "maxItems": 20,
    })
    leads = []
    for item in items[:20]:
        name = (item.get("name") or item.get("displayName") or "").strip()
        if not name:
            continue
        website = item.get("website") or item.get("websiteUrl") or ""
        if "trustpilot" in website.lower():
            website = ""
        leads.append({
            "name": name,
            "phone": item.get("phone", ""),
            "address": item.get("location", city),
            "website": website, "email": item.get("email", ""),
            "rating": float(item.get("trustScore") or item.get("score") or 0),
            "category": industry, "source": "Trustpilot",
            "notes": f"TrustScore: {item.get('trustScore', 0)} | Reviews: {item.get('numberOfReviews', 0)}",
        })
    return leads


# 5. Clutch.co — IT companies, agencies
async def scrape_clutch(industry: str, city: str) -> List[Dict]:
    items = await _run_apify_actor("epctex~clutch-scraper", {
        "search": f"{industry} {city}", "maxItems": 20,
    })
    leads = []
    for item in items[:20]:
        name = (item.get("name") or item.get("companyName") or "").strip()
        if not name:
            continue
        leads.append({
            "name": name,
            "phone": item.get("phone", ""),
            "address": item.get("location", city),
            "website": item.get("website") or item.get("websiteUrl") or "",
            "email": item.get("email", ""),
            "rating": float(item.get("rating") or 0),
            "category": industry, "source": "Clutch",
            "notes": f"Min project: {item.get('minProjectSize', 'N/A')} | "
                     f"Employees: {item.get('numEmployees', 'N/A')}",
        })
    return leads


# 6. Glassdoor — companies with employees
async def scrape_glassdoor(industry: str, city: str) -> List[Dict]:
    items = await _run_apify_actor("apify~glassdoor-scraper", {
        "searchQuery": f"{industry} {city}", "maxItems": 15,
    })
    leads = []
    for item in items[:15]:
        name = (item.get("name") or item.get("employer") or "").strip()
        if not name:
            continue
        leads.append({
            "name": name,
            "phone": "", "address": item.get("location", city),
            "website": item.get("website") or item.get("websiteUrl") or "",
            "email": "",
            "rating": float(item.get("overallRating") or item.get("rating") or 0),
            "category": industry, "source": "Glassdoor",
            "notes": f"Glassdoor rating: {item.get('overallRating', 0)} | "
                     f"Size: {item.get('size', 'N/A')}",
        })
    return leads


# ═══════════════════════════════════════════════════════════════
#  FREE SCRAPERS (no API key needed)
# ═══════════════════════════════════════════════════════════════

# 7. Zomato — restaurants in India
async def scrape_zomato(industry: str, city: str) -> List[Dict]:
    # Only relevant for food-related industries
    food_kw = ("restaurant", "cafe", "bakery", "sweet", "food", "pizza",
               "biryani", "bar", "pub", "dhaba", "kitchen", "hotel", "dine")
    if not any(k in industry.lower() for k in food_kw):
        return []

    city_slug = city.lower().replace(" ", "-")
    ind_slug = industry.lower().replace(" ", "-")
    url = f"https://www.zomato.com/{city_slug}/{ind_slug}"

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
    except Exception:
        return []

    soup = BeautifulSoup(html, "lxml")
    leads = []

    # Extract from JSON-LD
    import json
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
            items = []
            if isinstance(data, list):
                items = data
            elif data.get("@type") == "ItemList":
                items = [e.get("item", {}) for e in data.get("itemListElement", [])]
            else:
                items = [data]

            for item in items:
                if "Restaurant" not in str(item.get("@type", "")):
                    continue
                name = (item.get("name") or "").strip()
                if not name or len(name) < 3:
                    continue
                phone = item.get("telephone", "")
                addr = item.get("address") or {}
                if isinstance(addr, dict):
                    addr = ", ".join(filter(None, [
                        addr.get("streetAddress", ""),
                        addr.get("addressLocality", ""),
                    ])) or city
                agg = item.get("aggregateRating") or {}
                leads.append({
                    "name": name, "phone": phone, "address": addr,
                    "website": "", "email": "",
                    "rating": float(agg.get("ratingValue") or 0),
                    "category": industry, "source": "Zomato",
                    "notes": f"Zomato | Votes: {agg.get('ratingCount', 0)}",
                })
        except Exception:
            continue

    # Fallback: HTML parsing
    if not leads:
        for card in soup.select("[class*='search-result'], [class*='restaurant-card']")[:20]:
            name_el = card.select_one("h4 a, h3 a, [class*='name'] a")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            if not name:
                continue
            leads.append({
                "name": name, "phone": "", "address": city,
                "website": "", "email": "", "rating": 0.0,
                "category": industry, "source": "Zomato",
            })

    return leads[:20]


# 8. Practo — doctors/clinics in India
async def scrape_practo(industry: str, city: str) -> List[Dict]:
    health_kw = ("doctor", "clinic", "hospital", "dentist", "dermatolog",
                 "physiother", "gynec", "ortho", "pediatr", "ophthalmo",
                 "cardiolog", "ayurved", "homeopath", "psycholog", "psychiatr",
                 "veterinar", "diagnos", "lab", "pharmacy", "health")
    if not any(k in industry.lower() for k in health_kw):
        return []

    city_slug = city.lower().replace(" ", "-")
    ind_slug = industry.lower().replace(" ", "-").rstrip("s")
    url = f"https://www.practo.com/{city_slug}/{ind_slug}"

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
    except Exception:
        return []

    soup = BeautifulSoup(html, "lxml")
    leads = []

    import json
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
            items = data if isinstance(data, list) else [data]
            for item in items:
                name = item.get("name", "").strip()
                if not name or len(name) < 3:
                    continue
                phone = item.get("telephone", "")
                addr = item.get("address") or {}
                if isinstance(addr, dict):
                    addr = addr.get("streetAddress", city)
                agg = item.get("aggregateRating") or {}
                leads.append({
                    "name": name, "phone": phone, "address": addr,
                    "website": item.get("url", ""), "email": "",
                    "rating": float(agg.get("ratingValue") or 0),
                    "category": industry, "source": "Practo",
                    "notes": f"Practo | Reviews: {agg.get('reviewCount', 0)}",
                })
        except Exception:
            continue

    for card in soup.select(".info-section, .doctor-card, .listing-doctor-card")[:20]:
        name_el = card.select_one("h2 a, .doctor-name a, .info-section h2")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name:
            continue
        addr_el = card.select_one(".address, .practice-locality")
        leads.append({
            "name": name, "phone": "", "address": addr_el.get_text(strip=True) if addr_el else city,
            "website": "", "email": "", "rating": 0.0,
            "category": industry, "source": "Practo",
        })

    return leads[:20]


# 9. Naukri.com — companies hiring in India
async def scrape_naukri(industry: str, city: str) -> List[Dict]:
    ind_enc = industry.replace(" ", "-").lower()
    city_enc = city.replace(" ", "-").lower()
    url = f"https://www.naukri.com/{ind_enc}-jobs-in-{city_enc}"

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
    except Exception:
        return []

    soup = BeautifulSoup(html, "lxml")
    leads = []
    seen: set = set()

    import json
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") != "JobPosting":
                    continue
                org = item.get("hiringOrganization") or {}
                company = org.get("name", "").strip()
                if not company or company.lower() in seen:
                    continue
                seen.add(company.lower())
                website = org.get("sameAs") or org.get("url") or ""
                job_title = item.get("title", "")
                leads.append({
                    "name": company, "phone": "", "address": city,
                    "website": website, "email": "",
                    "rating": 0.0, "category": industry,
                    "source": "Naukri (Hiring)",
                    "notes": f"Hiring: {job_title} | Active on Naukri",
                })
        except Exception:
            continue

    for card in soup.select(".jobTuple, .srp-jobtuple, .cust-job-tuple")[:25]:
        co_el = card.select_one(".companyInfo a, .comp-name, .subTitle a")
        if not co_el:
            continue
        company = co_el.get_text(strip=True)
        if not company or company.lower() in seen:
            continue
        seen.add(company.lower())
        title_el = card.select_one(".title, .desig a, a.title")
        job_title = title_el.get_text(strip=True) if title_el else ""
        leads.append({
            "name": company, "phone": "", "address": city,
            "website": "", "email": "", "rating": 0.0,
            "category": industry, "source": "Naukri (Hiring)",
            "notes": f"Hiring: {job_title}",
        })

    return leads[:20]


# 10. Foursquare Places API — local businesses (free tier: 950 req/day)
async def scrape_foursquare(industry: str, city: str) -> List[Dict]:
    api_key = os.getenv("FOURSQUARE_API_KEY", "").strip()
    if not api_key:
        return []

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.foursquare.com/v3/places/search",
                params={
                    "query": industry,
                    "near": city,
                    "limit": 30,
                    "fields": "name,location,tel,website,email,rating,categories",
                },
                headers={
                    "Authorization": api_key,
                    "Accept": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
    except Exception:
        return []

    leads = []
    for place in data.get("results", [])[:30]:
        name = (place.get("name") or "").strip()
        if not name:
            continue
        loc = place.get("location") or {}
        addr = loc.get("formatted_address", city)
        cats = place.get("categories") or []
        cat_name = cats[0].get("name", industry) if cats else industry

        leads.append({
            "name": name,
            "phone": place.get("tel", ""),
            "address": addr,
            "website": place.get("website", ""),
            "email": place.get("email", ""),
            "rating": float(place.get("rating") or 0),
            "category": cat_name,
            "source": "Foursquare",
        })

    return leads


# 11. Bing Places — Microsoft's business directory
async def scrape_bing_places(industry: str, city: str) -> List[Dict]:
    query = f"{industry} in {city}".replace(" ", "+")
    url = f"https://www.bing.com/maps?q={query}"

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
    except Exception:
        return []

    soup = BeautifulSoup(html, "lxml")
    leads = []

    for card in soup.select(".bm_listings_item, .b_localResult, [class*='listing']")[:20]:
        name_el = card.select_one("h2 a, .lco_title a, .b_factrow a, a.b_prominentFocusable")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name or len(name) < 3:
            continue

        phone_el = card.select_one("[class*='phone'], [class*='tel']")
        phone = _phone(phone_el.get_text()) if phone_el else ""

        addr_el = card.select_one("[class*='addr'], [class*='address']")
        address = addr_el.get_text(strip=True) if addr_el else city

        leads.append({
            "name": name, "phone": phone, "address": address,
            "website": "", "email": "", "rating": 0.0,
            "category": industry, "source": "Bing Places",
        })

    return leads[:15]


# 12. MapMyIndia / Mappls — Indian map directory
async def scrape_mapmyindia(industry: str, city: str) -> List[Dict]:
    query = f"{industry}+{city}".replace(" ", "+")
    url = f"https://www.mapmyindia.com/search?query={query}"

    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    return []
                html = await resp.text()
    except Exception:
        return []

    soup = BeautifulSoup(html, "lxml")
    leads = []

    for card in soup.select("[class*='result'], [class*='listing'], [class*='place']")[:20]:
        name_el = card.select_one("h3 a, h2 a, [class*='name']")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if not name or len(name) < 3:
            continue

        phone_el = card.select_one("[class*='phone'], [class*='mobile']")
        addr_el = card.select_one("[class*='addr'], [class*='location']")

        leads.append({
            "name": name,
            "phone": _phone(phone_el.get_text()) if phone_el else "",
            "address": addr_el.get_text(strip=True) if addr_el else city,
            "website": "", "email": "", "rating": 0.0,
            "category": industry, "source": "MapMyIndia",
        })

    return leads[:15]
