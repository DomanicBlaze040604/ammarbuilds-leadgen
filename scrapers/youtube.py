"""
YouTube Data API v3 — FREE 10,000 units/day (no credit card needed for free tier).
Finds business channels in target industry+city.
WHY IT MATTERS: A business with YouTube content but NO website is a hot lead —
they're already creating content but have nowhere to send viewers.

Get a free API key: console.cloud.google.com → Enable YouTube Data API v3
Set YOUTUBE_API_KEY in .env to enable.
"""
import os
import aiohttp
from typing import List, Dict


async def scrape(industry: str, city: str) -> List[Dict]:
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        return []

    search_queries = [
        f"{industry} {city}",
        f"{city} {industry} business",
    ]

    leads = []
    seen_channels: set = set()

    async with aiohttp.ClientSession() as session:
        for q in search_queries[:2]:
            try:
                # Search for channels
                async with session.get(
                    "https://www.googleapis.com/youtube/v3/search",
                    params={
                        "key": api_key,
                        "q": q,
                        "type": "channel",
                        "part": "snippet",
                        "maxResults": 20,
                        "relevanceLanguage": "en",
                        "regionCode": "IN",
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()

                channel_ids = [
                    item["snippet"]["channelId"]
                    for item in data.get("items", [])
                    if item.get("snippet", {}).get("channelId")
                ]

                if not channel_ids:
                    continue

                # Get channel details (website, description, custom URL)
                async with session.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={
                        "key": api_key,
                        "id": ",".join(channel_ids),
                        "part": "snippet,brandingSettings,statistics",
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp2:
                    if resp2.status != 200:
                        continue
                    details = await resp2.json()

                for ch in details.get("items", []):
                    ch_id = ch.get("id", "")
                    if ch_id in seen_channels:
                        continue
                    seen_channels.add(ch_id)

                    snippet = ch.get("snippet", {})
                    branding = ch.get("brandingSettings", {}).get("channel", {})
                    stats = ch.get("statistics", {})

                    channel_name = snippet.get("title", "").strip()
                    if not channel_name:
                        continue

                    description = snippet.get("description", "")
                    custom_url = snippet.get("customUrl", "")
                    website = branding.get("unsubscribedTrailer", "") or ""

                    # Extract website from description if present
                    import re
                    urls_in_desc = re.findall(
                        r"https?://(?!youtu|youtube|fb\.me|bit\.ly|goo\.gl)\S+",
                        description,
                    )
                    if urls_in_desc:
                        website = urls_in_desc[0].rstrip(".,)")

                    sub_count = int(stats.get("subscriberCount") or 0)
                    video_count = int(stats.get("videoCount") or 0)

                    # Only include channels that look like businesses (not personal vloggers)
                    if video_count < 3:
                        continue

                    yt_url = f"https://www.youtube.com/{custom_url or '@' + ch_id}"
                    notes = (
                        f"YouTube: {sub_count:,} subscribers, {video_count} videos | {yt_url}"
                    )

                    leads.append({
                        "name": channel_name,
                        "phone": "",
                        "address": city,
                        "website": website,  # Empty = needs a website!
                        "email": "",
                        "rating": 0.0,
                        "category": industry,
                        "source": "YouTube",
                        "notes": notes,
                    })

            except Exception:
                continue

    return leads[:20]
