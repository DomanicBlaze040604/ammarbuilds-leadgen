"""
LinkedIn scrapers via Apify — find businesses that are HIRING (they have budget!)
and find decision-makers at target companies.

Actors used:
1. curious_coder/linkedin-jobs-scraper (4.9★) — Find companies posting jobs
   WHY: A company hiring = growing = has budget = needs a website/redesign
2. harvestapi/linkedin-company-employees — Find employees/owners at companies
   WHY: Get the actual decision-maker's name and title to personalize outreach

Set APIFY_TOKEN in .env to enable.
"""
import os
import aiohttp
from typing import List, Dict


# ─── LinkedIn Jobs Scraper ──────────────────────────────────
async def scrape_jobs(industry: str, city: str) -> List[Dict]:
    """
    Find companies posting jobs in target industry+city.
    Companies that are hiring have BUDGET and are growing.
    """
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token:
        return []

    run_input = {
        "searchUrl": f"https://www.linkedin.com/jobs/search/?keywords={industry}&location={city}&f_TPR=r2592000",
        "maxItems": 30,
    }

    actor_id = "curious_coder~linkedin-jobs-scraper"
    url = (
        f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
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
    seen_companies: set = set()

    for item in items:
        company = (
            item.get("companyName") or item.get("company") or ""
        ).strip()
        if not company or company.lower() in seen_companies:
            continue
        seen_companies.add(company.lower())

        job_title = item.get("title") or item.get("jobTitle") or ""
        company_url = item.get("companyUrl") or item.get("companyLinkedin") or ""
        website = item.get("companyWebsite") or ""
        location = item.get("location") or item.get("companyLocation") or city
        job_url = item.get("jobUrl") or item.get("url") or ""

        notes_parts = []
        if job_title:
            notes_parts.append(f"Hiring: {job_title}")
        if company_url:
            notes_parts.append(f"LinkedIn: {company_url}")
        if job_url:
            notes_parts.append(f"Job: {job_url}")

        leads.append({
            "name": company,
            "phone": "",
            "address": location,
            "website": website,
            "email": "",
            "rating": 0.0,
            "category": industry,
            "source": "LinkedIn Jobs",
            "notes": " | ".join(notes_parts),
        })

    return leads[:20]


# ─── LinkedIn Company Employees Scraper ─────────────────────
async def scrape_employees(company_urls: List[str]) -> List[Dict]:
    """
    Given LinkedIn company URLs, find employees (owners, managers).
    Use this as an enrichment step after discovering companies.
    """
    token = os.getenv("APIFY_TOKEN", "").strip()
    if not token or not company_urls:
        return []

    run_input = {
        "companyUrls": company_urls[:10],  # Limit for free tier
        "maxEmployees": 5,  # Just need the key people
    }

    actor_id = "harvestapi~linkedin-company-employees"
    url = (
        f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
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
        name = item.get("fullName") or item.get("name") or ""
        if not name:
            continue

        company = item.get("companyName") or ""
        title = item.get("headline") or item.get("jobTitle") or ""
        linkedin = item.get("linkedinProfile") or item.get("profileUrl") or ""
        email = item.get("email") or ""

        leads.append({
            "name": f"{company} — {name}" if company else name,
            "phone": item.get("mobileNumber", ""),
            "address": item.get("location", ""),
            "website": item.get("companyWebsite", ""),
            "email": email,
            "rating": 0.0,
            "category": title,
            "source": "LinkedIn People",
            "notes": f"{title} | {linkedin}",
        })

    return leads


# ─── Main entry point ───────────────────────────────────────
async def scrape(industry: str, city: str) -> List[Dict]:
    """Main scraper: find companies hiring in industry+city via LinkedIn."""
    return await scrape_jobs(industry, city)
