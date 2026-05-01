"""
Leads Finder (Apollo.io alternative) via Apify (code_crafter/leads-finder).
$1.50 per 1,000 leads — cheapest production-grade B2B lead source.

Returns: business email, mobile, personal email, LinkedIn URL,
company name, company website, job title, industry, and company size.

WHY USE THIS: When you want to find actual decision-makers (owners,
marketing managers) at businesses — not just the business listing.
Set APIFY_TOKEN in .env to enable.
"""
import os
import aiohttp
from typing import List, Dict


ACTOR_ID = "code_crafter~leads-finder"


async def scrape(industry: str, city: str) -> List[Dict]:
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        return []

    run_input = {
        "searchQuery": f"{industry} {city}",
        "maxResults": 30,
        "location": city,
        "industry": industry,
    }

    url = (
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
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
    for item in items[:30]:
        # Person-level data
        full_name = item.get("fullName") or item.get("name") or ""
        company = item.get("companyName") or item.get("company") or ""
        name = f"{company} ({full_name})" if company and full_name else (company or full_name)
        if not name:
            continue

        email = (
            item.get("email") or item.get("businessEmail")
            or item.get("personalEmail") or ""
        )
        phone = (
            item.get("mobileNumber") or item.get("mobile")
            or item.get("phone") or ""
        )
        website = item.get("companyWebsite") or item.get("website") or ""
        linkedin = item.get("linkedinProfile") or item.get("linkedinUrl") or ""
        job_title = item.get("jobTitle") or item.get("headline") or ""
        company_size = item.get("companySize") or ""

        location_parts = [
            item.get("city", ""),
            item.get("state", ""),
            item.get("country", ""),
        ]
        address = ", ".join(p for p in location_parts if p) or city

        notes_parts = []
        if job_title:
            notes_parts.append(f"Title: {job_title}")
        if linkedin:
            notes_parts.append(f"LinkedIn: {linkedin}")
        if company_size:
            notes_parts.append(f"Size: {company_size}")

        leads.append({
            "name": name,
            "phone": phone,
            "address": address,
            "website": website,
            "email": email,
            "rating": 0.0,
            "category": industry,
            "source": "Leads Finder",
            "notes": " | ".join(notes_parts),
        })

    return leads
