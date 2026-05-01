"""
Google News RSS — completely FREE, no API key needed.
Extracts business names from recent news in the target industry+city.
These are businesses making news = growing, expanding, worth contacting.
"""
import re
import xml.etree.ElementTree as ET
import aiohttp
from typing import List, Dict

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RSS reader/2.0)"}

# Patterns to extract company names from news headlines
NAME_PATTERNS = [
    r'"([A-Z][a-zA-Z\s&\-\.\']{3,40}(?:Ltd|Pvt|Inc|Co|Corp|LLP|Enterprises?|Solutions?|Services?|Group|Industries|International)?\.?)"',
    r'([A-Z][a-zA-Z\s&\-]{3,30}(?:Ltd|Pvt Ltd|Inc|Corp|LLP|Enterprises|Solutions|Services|Group|Industries))',
    r'([A-Z][a-zA-Z]{2,}\s[A-Z][a-zA-Z]{2,})\s+(?:launches?|opens?|expands?|starts?|founded|established)',
]


async def scrape(industry: str, city: str) -> List[Dict]:
    queries = [
        f"{industry} {city} business",
        f"{industry} company {city} launch",
        f"new {industry} {city}",
    ]

    leads = []
    seen: set = set()

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        for q in queries[:2]:
            q_enc = q.replace(" ", "+")
            url = f"https://news.google.com/rss/search?q={q_enc}&hl=en-IN&gl=IN&ceid=IN:en"
            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=12)
                ) as resp:
                    if resp.status != 200:
                        continue
                    content = await resp.text()
            except Exception:
                continue

            try:
                root = ET.fromstring(content)
                channel = root.find("channel")
                if channel is None:
                    continue

                for item in channel.findall("item")[:15]:
                    title = item.findtext("title", "")
                    desc = item.findtext("description", "")
                    full = f"{title} {desc}"

                    for pattern in NAME_PATTERNS:
                        for match in re.findall(pattern, full):
                            name = match.strip().rstrip(".")
                            if (
                                len(name) < 5
                                or name.lower() in seen
                                or city.lower() not in full.lower()
                            ):
                                continue
                            seen.add(name.lower())
                            leads.append({
                                "name": name,
                                "phone": "",
                                "address": city,
                                "website": "",
                                "email": "",
                                "rating": 0.0,
                                "category": industry,
                                "source": "Google News",
                                "notes": title[:120],
                            })
            except Exception:
                continue

    return leads[:15]
