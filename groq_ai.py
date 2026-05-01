"""
Groq AI — generates dead-simple caller scripts and email drafts.
Designed for non-technical callers who just need to read a script.

Uses Groq's free tier (llama-3.3-70b-versatile):
- 30 requests/minute
- 14,400 requests/day
- Ultra-fast (< 1 second response)
"""
import os
from groq import Groq


def get_client():
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        return None
    return Groq(api_key=key)


def generate_caller_script(lead: dict) -> dict:
    """
    Generate a simple phone script + email draft for a lead.
    Output is designed for a non-technical caller to just READ.
    """
    client = get_client()
    if not client:
        return _fallback_script(lead)

    name = lead.get("name", "the business")
    phone = lead.get("phone", "")
    email = lead.get("email", "")
    website = lead.get("website", "")
    address = lead.get("address", "")
    category = lead.get("category", "")
    source = lead.get("source", "")
    notes = lead.get("notes", "")
    signals = lead.get("signals", "")
    has_website = bool(website and website.strip() and "facebook.com" not in website and "instagram.com" not in website)

    prompt = f"""You are a sales script writer for a web design agency called AmmarBuilds.

LEAD INFO:
- Business Name: {name}
- Category: {category}
- Location: {address}
- Phone: {phone}
- Email: {email}
- Website: {website if has_website else "NONE - they don't have a website!"}
- Source found: {source}
- Extra info: {notes}
- Signals: {signals}

Generate THREE things in simple, ready-to-use format:

1. **CALL SCRIPT** (Hindi-English mix if Indian, else English) — Word-for-word script the caller reads. Keep it under 8 lines. Include:
   - Greeting with business name
   - Why you're calling (noticed they {"have an outdated website" if has_website else "don't have a website yet"})
   - What you offer (professional website starting ₹8,000 / $199)
   - Call to action (free mockup)
   - Polite close

2. **WHATSAPP MESSAGE** — Short, friendly, under 5 lines. Ready to copy-paste.

3. **EMAIL** — Subject line + body. Professional but warm. Under 10 lines.

RULES:
- Use the ACTUAL business name in every script
- Keep it SUPER simple — the caller is not technical
- {"Pitch: 'We noticed you don't have a website yet'" if not has_website else "Pitch: 'We noticed your website could use a modern upgrade'"}
- If the lead is from India, mix Hindi naturally (like "Namaste, kya aap {name} se bol rahe hain?")
- If international, keep it fully English
- Include specific details from the lead info to make it personal
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800,
        )
        content = response.choices[0].message.content
        return {"success": True, "script": content}
    except Exception as e:
        return _fallback_script(lead)


def generate_batch_summary(leads: list) -> str:
    """
    Generate a summary of all leads — which ones to call first,
    what to say, grouped by priority.
    """
    client = get_client()
    if not client:
        return _fallback_summary(leads)

    # Build a concise lead list
    lead_lines = []
    for i, lead in enumerate(leads[:30], 1):
        w = "NO WEBSITE" if not lead.get("website") else lead.get("website", "")[:40]
        lead_lines.append(
            f"{i}. {lead.get('name', '?')} | {lead.get('phone', 'no phone')} | "
            f"{lead.get('email', 'no email')} | {w} | Score: {lead.get('score', 0)} | "
            f"Source: {lead.get('source', '?')}"
        )

    leads_text = "\n".join(lead_lines)

    prompt = f"""You are a sales manager at AmmarBuilds web design agency.

Here are {len(leads[:30])} leads found by our tool. Create a SIMPLE ACTION PLAN for our caller team.

LEADS:
{leads_text}

Create:

1. **TOP 5 PRIORITY CALLS** — Which leads to call FIRST and why (1 line each)

2. **QUICK REFERENCE TABLE** — For each lead, in this format:
   Lead Name | Phone | What to Say (1 line) | Priority (🔥 Hot / ⚡ Warm / ❄ Cold)

3. **EMAIL BLAST LIST** — Which leads have email? List them with a personalized subject line for each.

4. **SKIP LIST** — Any leads to skip and why (e.g., already have a good website, no contact info)

RULES:
- Keep it DEAD SIMPLE — the caller is not technical
- Use ₹8,000 as the starting price for Indian leads, $199 for international
- Focus on leads with NO website first (they need us most!)
- Be specific — use actual business names and details
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500,
        )
        return response.choices[0].message.content
    except Exception as e:
        return _fallback_summary(leads)


def _fallback_script(lead: dict) -> dict:
    """Simple fallback when Groq is unavailable."""
    name = lead.get("name", "Sir/Ma'am")
    has_website = bool(lead.get("website"))
    pitch = "your website could use a modern upgrade" if has_website else "you don't have a professional website yet"

    return {
        "success": True,
        "script": f"""## 📞 CALL SCRIPT

"Hello, am I speaking with someone from **{name}**?

My name is [Your Name] from AmmarBuilds. I noticed {pitch}.

We build professional, mobile-friendly websites starting from just ₹8,000 that help businesses like yours get more customers from Google.

Can I send you a **free mockup** of how your website could look? No commitment needed.

Thank you for your time!"

## 💬 WHATSAPP

Hi! I'm from AmmarBuilds. We build professional websites for businesses like {name}. Starting ₹8,000. Can I show you a free mockup?

## ✉️ EMAIL

**Subject:** Professional Website for {name} — Free Mockup

Hi {name.split()[0] if name else 'there'},

I noticed {pitch}. I help local businesses get more customers with modern websites.

Starting at ₹8,000 — includes mobile-friendly design, Google SEO, and WhatsApp integration.

I'd love to create a free mockup for {name}. Reply to get started!

Best,
AmmarBuilds Team"""
    }


def _fallback_summary(leads: list) -> str:
    lines = ["# 📋 Lead Summary\n"]
    hot = [l for l in leads if l.get("score", 0) >= 70]
    warm = [l for l in leads if 40 <= l.get("score", 0) < 70]

    lines.append(f"**Total Leads:** {len(leads)}")
    lines.append(f"**🔥 Hot (score 70+):** {len(hot)}")
    lines.append(f"**⚡ Warm (score 40-69):** {len(warm)}\n")

    lines.append("## Top Leads to Call First:\n")
    for i, l in enumerate(leads[:10], 1):
        w = "❌ NO WEBSITE" if not l.get("website") else "✅ Has website"
        lines.append(f"{i}. **{l.get('name')}** — {l.get('phone', 'no phone')} — {w} — Score: {l.get('score', 0)}")

    return "\n".join(lines)
