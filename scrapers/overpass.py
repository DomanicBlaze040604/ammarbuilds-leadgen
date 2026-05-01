"""
OpenStreetMap Overpass API — completely FREE, no signup needed.
Returns businesses in a radius around the target city.
"""
import aiohttp
from typing import List, Dict

CITY_COORDS: Dict[str, tuple] = {
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "hyderabad": (17.3850, 78.4867),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "pune": (18.5204, 73.8567),
    "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873),
    "surat": (21.1702, 72.8311),
    "lucknow": (26.8467, 80.9462),
    "kanpur": (26.4499, 80.3319),
    "nagpur": (21.1458, 79.0882),
    "indore": (22.7196, 75.8577),
    "bhopal": (23.2599, 77.4126),
    "visakhapatnam": (17.6868, 83.2185),
    "vizag": (17.6868, 83.2185),
    "patna": (25.5941, 85.1376),
    "vadodara": (22.3072, 73.1812),
    "coimbatore": (11.0168, 76.9558),
    "kochi": (9.9312, 76.2673),
    "chandigarh": (30.7333, 76.7794),
    "gurgaon": (28.4595, 77.0266),
    "gurugram": (28.4595, 77.0266),
    "noida": (28.5355, 77.3910),
    "thane": (19.2183, 72.9781),
    "navi mumbai": (19.0330, 73.0297),
    "dubai": (25.2048, 55.2708),
    "abu dhabi": (24.4539, 54.3773),
    "sharjah": (25.3462, 55.4210),
    "london": (51.5074, -0.1278),
    "new york": (40.7128, -74.0060),
    "singapore": (1.3521, 103.8198),
    "toronto": (43.6532, -79.3832),
    "sydney": (-33.8688, 151.2093),
}

INDUSTRY_TAGS = {
    "restaurant": 'amenity=restaurant',
    "cafe": 'amenity=cafe',
    "hotel": 'tourism=hotel',
    "gym": 'leisure=fitness_centre',
    "salon": 'shop=hairdresser',
    "pharmacy": 'amenity=pharmacy',
    "clinic": 'amenity=clinic',
    "hospital": 'amenity=hospital',
    "school": 'amenity=school',
    "college": 'amenity=college',
    "bank": 'amenity=bank',
    "supermarket": 'shop=supermarket',
    "clothing": 'shop=clothes',
    "electronics": 'shop=electronics',
    "furniture": 'shop=furniture',
    "bakery": 'shop=bakery',
    "bar": 'amenity=bar',
    "mechanic": 'shop=car_repair',
    "dentist": 'amenity=dentist',
    "lawyer": 'office=lawyer',
    "travel": 'shop=travel_agency',
    "real estate": 'office=estate_agent',
    "interior": 'office=interior_designer',
    "architect": 'office=architect',
    "it": 'office=it',
    "software": 'office=it',
    "printing": 'shop=copyshop',
    "photography": 'shop=photo',
    "grocery": 'shop=convenience',
    "sweet": 'shop=confectionery',
    "jewellery": 'shop=jewelry',
    "jewelry": 'shop=jewelry',
    "optician": 'shop=optician',
    "tailor": 'shop=tailor',
    "mobile": 'shop=mobile_phone',
    "hardware": 'shop=hardware',
    "coaching": 'amenity=college',
    "courier": 'amenity=post_office',
    "laundry": 'shop=laundry',
    "spa": 'leisure=spa',
    "yoga": 'leisure=yoga',
    "chartered": 'office=financial',
    "ca firm": 'office=financial',
    "accounting": 'office=financial',
}


def _get_tag(industry: str):
    low = industry.lower()
    for key, tag in INDUSTRY_TAGS.items():
        if key in low:
            k, v = tag.split("=", 1)
            return k, v
    return None, None


async def scrape(industry: str, city: str) -> List[Dict]:
    city_low = city.lower().strip()
    coords = CITY_COORDS.get(city_low)
    if not coords:
        # Try partial match
        for k, v in CITY_COORDS.items():
            if k in city_low or city_low in k:
                coords = v
                break

    if not coords:
        return []

    lat, lon = coords
    key, val = _get_tag(industry)

    if key and val:
        tag_filter = f'["{key}"="{val}"]'
        generic_filter = f'["name"~"{industry}",i]'
        query = f"""
[out:json][timeout:25];
(
  node{tag_filter}(around:12000,{lat},{lon});
  way{tag_filter}(around:12000,{lat},{lon});
  node{generic_filter}(around:12000,{lat},{lon});
);
out body center 60;
"""
    else:
        query = f"""
[out:json][timeout:25];
(
  node["name"~"{industry}",i](around:12000,{lat},{lon});
  way["name"~"{industry}",i](around:12000,{lat},{lon});
);
out body center 60;
"""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
    except Exception:
        return []

    leads = []
    seen = set()
    for el in data.get("elements", [])[:60]:
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())

        phone = (
            tags.get("phone") or tags.get("contact:phone")
            or tags.get("contact:mobile") or ""
        ).strip()
        website = (
            tags.get("website") or tags.get("contact:website") or ""
        ).strip()
        email = (
            tags.get("email") or tags.get("contact:email") or ""
        ).strip()

        addr_parts = [
            tags.get("addr:housenumber", ""),
            tags.get("addr:street", ""),
            tags.get("addr:suburb", ""),
            tags.get("addr:city", city),
        ]
        address = ", ".join(p for p in addr_parts if p) or city

        leads.append({
            "name": name,
            "phone": phone,
            "address": address,
            "website": website,
            "email": email,
            "rating": 0,
            "category": industry,
            "source": "OpenStreetMap",
        })

    return leads
