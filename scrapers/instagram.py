"""
Instagram Business scraper — TWO paths:

Path 1 (BEST): Apify Instagram Scraper (apify/instagram-scraper, actor ID: shu8hvrXbJbY3Eb9W)
  - Searches hashtags like #restaurantmumbai, #gymbangalore
  - Returns posts with captions (often contain phone/email/address)
  - $1.50 per 1,000 results — your $5 credit = ~3,300 results/month

Path 2: Apify Instagram Search Scraper (apify/instagram-search-scraper)
  - Searches IG for business accounts by keyword
  - Returns profile bio, website, category, follower count
  - Great for finding IG-only businesses that need a website

Path 3 (Fallback): Meta Graph API (if META_ACCESS_TOKEN set)

WHY THIS MATTERS: Cafes, gyms, salons, and shops are Instagram-first.
They have 10k followers but no website = PERFECT web dev lead.
"""
import os
import re
import aiohttp
from typing import List, Dict


# ─── Apify Instagram Scraper (shu8hvrXbJbY3Eb9W) ───────────
async def _scrape_apify_hashtag(industry: str, city: str, token: str) -> List[Dict]:
    """Search Instagram by hashtag — finds businesses posting about their services."""
    ind = industry.lower().replace(" ", "")
    c = city.lower().replace(" ", "")
    hashtags = [f"{ind}{c}", f"{c}{ind}", f"{ind}india"]

    run_input = {
        "resultsType": "posts",
        "search": f"#{hashtags[0]}",
        "searchType": "hashtag",
        "searchLimit": 3,
        "resultsLimit": 30,
        "addParentData": False,
    }

    url = (
        f"https://api.apify.com/v2/acts/shu8hvrXbJbY3Eb9W/run-sync-get-dataset-items"
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
                    return []
                items = await resp.json(content_type=None)
    except Exception:
        return []

    if not isinstance(items, list):
        return []

    leads = []
    seen_owners: set = set()

    for item in items:
        owner = item.get("ownerUsername") or item.get("ownerId") or ""
        if not owner or owner in seen_owners:
            continue
        seen_owners.add(owner)

        caption = item.get("caption") or ""
        name = _extract_business_name(caption, owner, industry)
        phone = _extract_phone(caption)
        email = _extract_email(caption)
        website = _extract_url(caption)

        ig_url = f"https://instagram.com/{owner}" if owner else ""

        leads.append({
            "name": name,
            "phone": phone,
            "address": city,
            "website": website,  # Empty = needs a website!
            "email": email,
            "rating": 0.0,
            "category": industry,
            "source": "Instagram (Apify)",
            "notes": f"IG: @{owner} | Likes: {item.get('likesCount', 0)} | {ig_url}",
        })

    return leads[:20]


# ─── Apify Instagram Search Scraper ─────────────────────────
async def _scrape_apify_search(industry: str, city: str, token: str) -> List[Dict]:
    """Search Instagram for business profiles matching industry+city."""
    run_input = {
        "resultsType": "details",
        "search": f"{industry} {city}",
        "searchType": "user",
        "searchLimit": 20,
        "resultsLimit": 1,  # Just profile details, not posts
    }

    url = (
        f"https://api.apify.com/v2/acts/shu8hvrXbJbY3Eb9W/run-sync-get-dataset-items"
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
                    return []
                items = await resp.json(content_type=None)
    except Exception:
        return []

    if not isinstance(items, list):
        return []

    leads = []
    for item in items:
        username = item.get("username") or ""
        name = item.get("fullName") or item.get("name") or username
        if not name:
            continue

        bio = item.get("biography") or item.get("bio") or ""
        website = item.get("externalUrl") or item.get("website") or ""
        email = _extract_email(bio) or item.get("businessEmail") or ""
        phone = _extract_phone(bio) or item.get("businessPhoneNumber") or ""
        followers = item.get("followersCount") or item.get("followers") or 0
        category = item.get("businessCategoryName") or industry

        ig_url = f"https://instagram.com/{username}"

        leads.append({
            "name": name,
            "phone": phone,
            "address": city,
            "website": website,
            "email": email,
            "rating": 0.0,
            "category": category,
            "source": "Instagram Search",
            "notes": f"@{username} | {followers:,} followers | {ig_url}",
        })

    return leads[:15]


# ─── Meta Graph API fallback ────────────────────────────────
async def _scrape_meta_graph(industry: str, city: str) -> List[Dict]:
    """Fallback: Use Meta Graph API if META_ACCESS_TOKEN is set."""
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    if not token:
        return []

    ind = industry.lower().replace(" ", "")
    c = city.lower().replace(" ", "")
    hashtags = [f"{ind}{c}", f"{c}{ind}"]

    leads = []
    seen: set = set()

    async with aiohttp.ClientSession() as session:
        for tag in hashtags[:2]:
            try:
                async with session.get(
                    "https://graph.facebook.com/v19.0/ig_hashtag_search",
                    params={
                        "access_token": token,
                        "user_id": await _get_ig_user_id(session, token),
                        "q": tag,
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        continue
                    hashtag_data = await resp.json()

                hashtag_id = (hashtag_data.get("data") or [{}])[0].get("id")
                if not hashtag_id:
                    continue

                async with session.get(
                    f"https://graph.facebook.com/v19.0/{hashtag_id}/recent_media",
                    params={
                        "access_token": token,
                        "fields": "id,caption,permalink,owner",
                        "limit": 20,
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp2:
                    if resp2.status != 200:
                        continue
                    media_data = await resp2.json()

                for post in media_data.get("data", []):
                    caption = post.get("caption", "") or ""
                    owner_id = (post.get("owner") or {}).get("id", "")
                    if owner_id in seen:
                        continue
                    seen.add(owner_id)

                    phone = _extract_phone(caption)
                    email = _extract_email(caption)
                    website = _extract_url(caption)
                    name = _extract_business_name(caption, "", industry)
                    if not name:
                        continue

                    leads.append({
                        "name": name,
                        "phone": phone,
                        "address": city,
                        "website": website,
                        "email": email,
                        "rating": 0.0,
                        "category": industry,
                        "source": "Instagram (Meta API)",
                        "notes": f"Post: {post.get('permalink', '')}",
                    })
            except Exception:
                continue

    return leads[:15]


async def _get_ig_user_id(session, token: str) -> str:
    try:
        async with session.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={"access_token": token},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            data = await resp.json()
            pages = data.get("data", [])
            if pages:
                return pages[0].get("id", "")
    except Exception:
        pass
    return ""


# ─── Main entry point ───────────────────────────────────────
async def scrape(industry: str, city: str) -> List[Dict]:
    """Try Apify first (best data), then Meta Graph API fallback."""
    apify_token = os.getenv("APIFY_TOKEN", "").strip()
    if apify_token:
        # Try hashtag search first, then profile search
        results = await _scrape_apify_hashtag(industry, city, apify_token)
        if not results:
            results = await _scrape_apify_search(industry, city, apify_token)
        if results:
            return results

    # Fallback to Meta Graph API
    return await _scrape_meta_graph(industry, city)


# ─── Utility extractors ─────────────────────────────────────
def _extract_phone(text: str) -> str:
    m = re.search(r"(?:\+91[-\s]?)?[6-9]\d{9}", re.sub(r"[\s\-]", "", text))
    return m.group() if m else ""


def _extract_email(text: str) -> str:
    m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return m.group() if m else ""


def _extract_url(text: str) -> str:
    m = re.search(r"https?://(?!instagram\.com|linktr\.ee|bit\.ly|fb\.me)\S+", text)
    return m.group().rstrip(".,)") if m else ""


def _extract_business_name(caption: str, username: str, industry: str) -> str:
    """Try to extract business name from Instagram caption or use username."""
    patterns = [
        rf"(?:at|by|visit|from)\s+([A-Z][a-zA-Z\s&\-']{{3,30}})",
        r"^([A-Z][a-zA-Z\s&\-']{3,30})\s*[\|•\-]",
        rf"([A-Z][a-zA-Z\s&]{{3,25}}(?:{industry[:5]}|Cafe|Gym|Shop|Studio|Salon|Kitchen))",
    ]
    for p in patterns:
        m = re.search(p, caption, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()

    # Use username as name (cleaned up)
    if username:
        clean = username.replace("_", " ").replace(".", " ").title()
        if len(clean) > 3:
            return clean

    # Fallback: first meaningful line of caption
    for line in caption.split("\n"):
        line = line.strip()
        if 5 < len(line) < 50 and not line.startswith("#") and not line.startswith("@"):
            return line[:40]
    return ""
