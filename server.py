import asyncio
import csv
import io
import json
import os
import sqlite3
import uuid
from datetime import datetime

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="LeadGen Tool — AmmarBuilds")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.mount("/static", StaticFiles(directory="static"), name="static")

DB_FILE = os.getenv("DB_PATH", "leads.db")


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'pending',
            industry TEXT,
            city TEXT,
            created_at TEXT,
            completed_at TEXT,
            lead_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            job_id TEXT,
            name TEXT,
            phone TEXT,
            address TEXT,
            website TEXT,
            category TEXT,
            rating REAL DEFAULT 0,
            source TEXT,
            score INTEGER DEFAULT 0,
            signals TEXT,
            email TEXT,
            notes TEXT,
            contacted INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        );
        CREATE INDEX IF NOT EXISTS idx_leads_job ON leads(job_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score);
    """)
    conn.commit()
    conn.close()


class GenerateLeadsRequest(BaseModel):
    industry: str
    city: str


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.post("/api/generate-leads")
async def generate_leads(
    request: GenerateLeadsRequest, background_tasks: BackgroundTasks
):
    if not request.industry.strip() or not request.city.strip():
        raise HTTPException(400, "Industry and city are required")

    job_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        "INSERT INTO jobs (id, status, industry, city, created_at) VALUES (?, ?, ?, ?, ?)",
        (job_id, "pending", request.industry.strip(), request.city.strip(),
         datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    background_tasks.add_task(
        process_job, job_id, request.industry.strip(), request.city.strip()
    )
    return {"jobId": job_id, "status": "pending"}


@app.get("/api/job-status/{job_id}")
async def job_status(job_id: str):
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Job not found")

    result = dict(job)
    leads_rows = conn.execute(
        "SELECT * FROM leads WHERE job_id = ? ORDER BY score DESC",
        (job_id,),
    ).fetchall()
    conn.close()
    result["leads"] = [dict(r) for r in leads_rows]
    return result


@app.get("/api/export-csv/{job_id}")
async def export_csv(job_id: str):
    conn = get_db()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Job not found")

    leads = conn.execute(
        "SELECT * FROM leads WHERE job_id = ? ORDER BY score DESC", (job_id,)
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Name", "Phone", "Address", "Website", "Category",
        "Rating", "Source", "Score", "Signals", "Email", "Notes"
    ])
    for lead in leads:
        signals = lead["signals"] or ""
        try:
            signals = ", ".join(json.loads(signals))
        except Exception:
            pass
        writer.writerow([
            lead["name"], lead["phone"], lead["address"],
            lead["website"] or "NO WEBSITE",
            lead["category"], lead["rating"], lead["source"],
            lead["score"], signals, lead["email"] or "", lead["notes"] or ""
        ])

    output.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"leads_{job['industry']}_{job['city']}_{ts}.csv".replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/past-jobs")
async def past_jobs():
    conn = get_db()
    jobs = conn.execute(
        "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 30"
    ).fetchall()
    conn.close()
    return [dict(j) for j in jobs]


@app.patch("/api/leads/{lead_id}/contacted")
async def mark_contacted(lead_id: str):
    conn = get_db()
    conn.execute("UPDATE leads SET contacted = 1 WHERE id = ?", (lead_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@app.get("/api/script/{lead_id}")
async def get_script(lead_id: str):
    """Generate a caller script + email draft for a single lead using Groq AI."""
    from groq_ai import generate_caller_script
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    conn.close()
    if not lead:
        raise HTTPException(404, "Lead not found")
    return generate_caller_script(dict(lead))


@app.get("/api/summary/{job_id}")
async def get_summary(job_id: str):
    """Generate a batch action plan for all leads in a job using Groq AI."""
    from groq_ai import generate_batch_summary
    conn = get_db()
    leads = conn.execute(
        "SELECT * FROM leads WHERE job_id = ? ORDER BY score DESC", (job_id,)
    ).fetchall()
    conn.close()
    if not leads:
        raise HTTPException(404, "No leads found")
    summary = generate_batch_summary([dict(l) for l in leads])
    return {"summary": summary}


async def process_job(job_id: str, industry: str, city: str):
    # ─── Import ALL scrapers ─────────────────────────────────
    # Core free scrapers
    from scrapers.overpass import scrape as scrape_osm
    from scrapers.justdial import scrape as scrape_jd
    from scrapers.indiamart import scrape as scrape_im
    from scrapers.news_rss import scrape as scrape_news
    from scrapers.sulekha import scrape as scrape_sulekha
    from scrapers.google_ads import scrape as scrape_gads
    from scrapers.google_ads import scrape_google_serp_ads
    # API-key scrapers
    from scrapers.serper import scrape as scrape_serper
    from scrapers.youtube import scrape as scrape_yt
    from scrapers.meta_ads import scrape as scrape_meta
    from scrapers.meta_ads import scrape_fb_pages
    # Apify scrapers
    from scrapers.google_maps_apify import scrape as scrape_gmaps_apify
    from scrapers.instagram import scrape as scrape_ig
    from scrapers.facebook_apify import scrape as scrape_fb_apify
    from scrapers.linkedin import scrape as scrape_linkedin
    from scrapers.leads_finder import scrape as scrape_leads_finder
    from scrapers.contact_enricher import enrich_leads
    # Extra sources (Apify + free)
    from scrapers.extra_sources import (
        scrape_google_serp, scrape_yelp, scrape_tripadvisor,
        scrape_trustpilot, scrape_clutch, scrape_glassdoor,
        scrape_zomato, scrape_practo, scrape_naukri,
        scrape_foursquare, scrape_bing_places, scrape_mapmyindia,
    )

    conn = get_db()
    conn.execute("UPDATE jobs SET status = 'processing' WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()

    try:
        # ─── Phase 1: Run ALL sources concurrently ───────────
        results = await asyncio.gather(
            # FREE — always on, no key needed (6 sources)
            scrape_osm(industry, city),               #  1. OpenStreetMap
            scrape_jd(industry, city),                #  2. JustDial
            scrape_im(industry, city),                #  3. IndiaMART
            scrape_news(industry, city),              #  4. Google News RSS
            scrape_sulekha(industry, city),            #  5. Sulekha + TradeIndia
            scrape_gads(industry, city),              #  6. Google Ads Transparency
            scrape_zomato(industry, city),             #  7. Zomato (restaurants)
            scrape_practo(industry, city),             #  8. Practo (health)
            scrape_naukri(industry, city),             #  9. Naukri (hiring companies)
            scrape_bing_places(industry, city),        # 10. Bing Places
            scrape_mapmyindia(industry, city),         # 11. MapMyIndia
            # SERPER_API_KEY (2 sources)
            scrape_serper(industry, city),             # 12. Google Maps (Serper)
            scrape_google_serp_ads(industry, city),    # 13. Google Ads SERP
            # APIFY_TOKEN (11 sources)
            scrape_gmaps_apify(industry, city),        # 14. Google Maps (Compass)
            scrape_ig(industry, city),                # 15. Instagram
            scrape_fb_apify(industry, city),           # 16. Facebook Pages
            scrape_linkedin(industry, city),           # 17. LinkedIn Jobs
            scrape_leads_finder(industry, city),       # 18. Leads Finder (Apollo alt)
            scrape_google_serp(industry, city),        # 19. Google SERP organic
            scrape_yelp(industry, city),               # 20. Yelp
            scrape_tripadvisor(industry, city),        # 21. TripAdvisor
            scrape_trustpilot(industry, city),         # 22. Trustpilot
            scrape_clutch(industry, city),             # 23. Clutch.co
            scrape_glassdoor(industry, city),          # 24. Glassdoor
            # META_ACCESS_TOKEN (2 sources)
            scrape_meta(industry, city),              # 25. Meta Ads Library
            scrape_fb_pages(industry, city),           # 26. Facebook Pages (Graph)
            # YOUTUBE_API_KEY (1 source)
            scrape_yt(industry, city),                # 27. YouTube channels
            # FOURSQUARE_API_KEY (1 source)
            scrape_foursquare(industry, city),         # 28. Foursquare
            return_exceptions=True,
        )

        all_leads = []
        for r in results:
            if isinstance(r, list):
                all_leads.extend(r)

        # ─── Deduplicate ─────────────────────────────────────
        seen_phones: set = set()
        seen_names: set = set()
        deduped = []
        for lead in all_leads:
            p = (lead.get("phone") or "").strip().replace(" ", "").replace("-", "")
            n = (lead.get("name") or "").lower().strip()
            if not n:
                continue
            if p and p in seen_phones:
                continue
            if n in seen_names:
                continue
            if p:
                seen_phones.add(p)
            seen_names.add(n)
            deduped.append(lead)

        # ─── Phase 2: Contact enrichment ─────────────────────
        try:
            leads_with_sites = [l for l in deduped if (l.get("website") or "").startswith("http")]
            if leads_with_sites:
                await enrich_leads(leads_with_sites)
        except Exception:
            pass

        # ─── Score & enrich signals ──────────────────────────
        for lead in deduped:
            score, signals = calculate_score(lead)
            lead["score"] = score
            lead["signals"] = signals

        deduped.sort(key=lambda x: x["score"], reverse=True)

        # ─── Save to database ────────────────────────────────
        conn = get_db()
        for lead in deduped:
            lid = str(uuid.uuid4())
            signals_json = json.dumps(lead.get("signals", []))
            conn.execute(
                """INSERT INTO leads
                   (id, job_id, name, phone, address, website, category,
                    rating, source, score, signals, email, notes, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    lid, job_id,
                    lead.get("name", "Unknown Business"),
                    lead.get("phone", ""),
                    lead.get("address", city),
                    lead.get("website", ""),
                    lead.get("category", industry),
                    float(lead.get("rating") or 0),
                    lead.get("source", "unknown"),
                    lead["score"],
                    signals_json,
                    lead.get("email", ""),
                    lead.get("notes", ""),
                    datetime.now().isoformat(),
                ),
            )
        conn.execute(
            "UPDATE jobs SET status='completed', completed_at=?, lead_count=? WHERE id=?",
            (datetime.now().isoformat(), len(deduped), job_id),
        )
        conn.commit()
        conn.close()

    except Exception as exc:
        conn = get_db()
        conn.execute(
            "UPDATE jobs SET status='failed' WHERE id=?", (job_id,)
        )
        conn.commit()
        conn.close()
        print(f"[ERROR] Job {job_id} failed: {exc}")
        import traceback
        traceback.print_exc()


def calculate_score(lead: dict):
    score = 0
    signals = []

    website = (lead.get("website") or "").strip().lower()
    has_website = bool(
        website
        and website not in ("n/a", "none", "-", "")
        and "facebook.com" not in website
        and "instagram.com" not in website
        and "linkedin.com" not in website
    )

    source = (lead.get("source") or "").lower()
    notes = (lead.get("notes") or "").lower()

    # 40pts — no website (highest value: they need one!)
    if not has_website:
        score += 40
        signals.append("No Website ⭐")

    # 20pts — has phone (directly contactable)
    if (lead.get("phone") or "").strip():
        score += 20
        signals.append("Phone Available")

    # 15pts — has email
    if (lead.get("email") or "").strip():
        score += 15
        signals.append("Email Available")

    # 15pts — high rating (established, has budget)
    rating = float(lead.get("rating") or 0)
    if rating >= 4.0:
        score += 15
        signals.append("High Rated ★")
    elif rating >= 3.0:
        score += 8
        signals.append("Good Rating")

    # 10pts — has address (local, targetable)
    if (lead.get("address") or "").strip():
        score += 10

    # BONUS signals
    if "ads" in source or "ad " in source:
        score += 5
        signals.append("Spending on Ads 💰")
    if "linkedin" in source:
        score += 5
        signals.append("Active on LinkedIn")
    if "hiring" in notes:
        score += 5
        signals.append("Currently Hiring 🔥")
    if "instagram" in source and not has_website:
        score += 5
        signals.append("IG-only Business 📱")
    if "facebook" in source and not has_website:
        score += 5
        signals.append("FB-only Business 📘")
    if "naukri" in source:
        score += 3
        signals.append("Hiring on Naukri")
    if "trustpilot" in source or "yelp" in source or "tripadvisor" in source:
        score += 3
        signals.append("Has Review Presence")

    return min(score, 100), signals


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)
