"""
Contact Details Enricher via Apify (vdrmota/contact-info-scraper).
Takes a list of domains/URLs and extracts emails, phones, social links.

WHY THIS MATTERS: After you find businesses with websites from JustDial,
Google Maps etc., this scraper visits each website and extracts the
ACTUAL contact details from the site itself — way more accurate than
directory listings.

Set APIFY_TOKEN in .env to enable.
"""
import os
import aiohttp
from typing import List, Dict


ACTOR_ID = "vdrmota~contact-info-scraper"


async def enrich_leads(leads_with_websites: List[Dict]) -> List[Dict]:
    """
    Given a list of leads that have websites, visit each site and
    extract actual contact details (emails, phones, social links).
    Returns enriched leads.
    """
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        return leads_with_websites  # Return unchanged

    # Collect URLs to enrich
    urls = []
    url_to_lead = {}
    for lead in leads_with_websites:
        website = (lead.get("website") or "").strip()
        if website and website.startswith("http"):
            urls.append(website)
            url_to_lead[website] = lead

    if not urls:
        return leads_with_websites

    # Limit to 20 URLs to stay within free tier
    urls = urls[:20]

    run_input = {
        "startUrls": [{"url": u} for u in urls],
        "maxRequestsPerStartUrl": 3,
        "maxDepth": 1,
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
                    return leads_with_websites
                items = await resp.json(content_type=None)
    except Exception:
        return leads_with_websites

    if not isinstance(items, list):
        return leads_with_websites

    # Merge enriched data back into leads
    for item in items:
        source_url = item.get("url") or ""
        # Find matching lead
        matched_lead = None
        for orig_url, lead in url_to_lead.items():
            if orig_url in source_url or source_url in orig_url:
                matched_lead = lead
                break

        if not matched_lead:
            continue

        # Enrich with discovered contacts
        emails = item.get("emails") or []
        phones = item.get("phones") or item.get("phoneNumbers") or []
        socials = {}
        for key in ("facebook", "twitter", "linkedin", "instagram", "youtube"):
            val = item.get(key) or item.get(f"{key}Url") or ""
            if val:
                socials[key] = val

        if emails and not matched_lead.get("email"):
            matched_lead["email"] = emails[0]
        if phones and not matched_lead.get("phone"):
            matched_lead["phone"] = phones[0]

        social_notes = " | ".join(f"{k}: {v}" for k, v in socials.items())
        if social_notes:
            existing = matched_lead.get("notes") or ""
            matched_lead["notes"] = f"{existing} | {social_notes}" if existing else social_notes

    return leads_with_websites


async def scrape_domains(domains: List[str]) -> List[Dict]:
    """
    Standalone: Given a list of domain URLs, extract contact details.
    Returns leads from the discovered contact info.
    """
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        return []

    urls = domains[:20]  # Limit for free tier

    run_input = {
        "startUrls": [{"url": u} for u in urls],
        "maxRequestsPerStartUrl": 3,
        "maxDepth": 1,
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
    for item in items:
        domain = item.get("url") or item.get("domain") or ""
        emails = item.get("emails") or []
        phones = item.get("phones") or item.get("phoneNumbers") or []
        name = item.get("companyName") or item.get("title") or domain

        if not name:
            continue

        leads.append({
            "name": name,
            "phone": phones[0] if phones else "",
            "address": "",
            "website": domain,
            "email": emails[0] if emails else "",
            "rating": 0.0,
            "category": "",
            "source": "Contact Enricher",
            "notes": f"Emails: {', '.join(emails[:3])} | Phones: {', '.join(phones[:3])}",
        })

    return leads
