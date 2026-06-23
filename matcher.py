"""
KrishiSetu - Matcher Engine
Reads farmers, cold storages, and transporters from data/ folder.
Finds the best matches using real distance calculations (Haversine).
"""

import json
import os
import math
from datetime import date, datetime
from districts import DISTRICT_COORDS, canonical

DATA_DIR = "data"
FARMERS_FILE      = os.path.join(DATA_DIR, "farmers.json")
COLD_STORAGE_FILE = os.path.join(DATA_DIR, "cold_storages.json")
TRANSPORTERS_FILE = os.path.join(DATA_DIR, "transporters.json")
MATCHES_FILE      = os.path.join(DATA_DIR, "matches.json")

# ── Distance thresholds (km) — edit these to tune matching ──────────────────
MAX_STORAGE_DISTANCE_KM    = 250
MAX_TRANSPORTER_DISTANCE_KM = 150
# ────────────────────────────────────────────────────────────────────────────


def get_coords(district_name):
    """
    Return (lat, lng) for a district name, or None if not found.
    FIX: normalise through canonical() so aliases and title-case all resolve.
    """
    key = canonical(district_name)
    if key is None:
        key = district_name.strip().lower()
    return DISTRICT_COORDS.get(key)


def haversine_km(lat1, lng1, lat2, lng2):
    """Straight-line distance in km between two lat/lng points."""
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_between(district_a, district_b):
    """
    Return distance in km between two district names.
    FIX: same-district now returns None with a special flag instead of 0,
         so '0 km away' never shows in output. Caller uses fmt_dist() which
         shows 'Same district' instead.
    Returns (distance_km_or_None, is_same_district).
    """
    ca = get_coords(district_a)
    cb = get_coords(district_b)
    if ca is None or cb is None:
        return None, False

    # FIX: detect same district explicitly — haversine gives 0.0 which is misleading
    key_a = canonical(district_a) or district_a.strip().lower()
    key_b = canonical(district_b) or district_b.strip().lower()
    if key_a == key_b:
        return 0.0, True

    dist = haversine_km(ca[0], ca[1], cb[0], cb[1])
    return dist, False


# ── Data loading ─────────────────────────────────────────────────────────────

def load(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r") as f:
        return json.load(f)


def save_matches(matches):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MATCHES_FILE, "w") as f:
        json.dump(matches, f, indent=2, default=str)


def to_date(s):
    if isinstance(s, date):
        return s
    return datetime.strptime(s, "%Y-%m-%d").date()


# ── Compatibility checks ──────────────────────────────────────────────────────

def crops_compatible(farmer_crop, storage_crops):
    if "All" in storage_crops:
        return True
    return farmer_crop.lower() in [c.lower() for c in storage_crops]


def dates_overlap(farmer_harvest, storage_from, storage_until):
    h  = to_date(farmer_harvest)
    sf = to_date(storage_from)
    su = to_date(storage_until)
    return sf <= h <= su


def transporter_available(farmer_harvest, transport_from, transport_until, transporter=None):
    h  = to_date(farmer_harvest)
    tf = to_date(transport_from)
    tu = to_date(transport_until)
    if not (tf <= h <= tu):
        return False
    # Also check blocked_dates from confirmed bookings
    if transporter:
        for block in transporter.get("blocked_dates", []):
            try:
                b_from  = to_date(block["from"])
                b_until = to_date(block["until"])
                if b_from <= h <= b_until:
                    return False
            except (KeyError, ValueError):
                continue
    return True


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_storage(farmer, storage, dist_km, is_same_district):
    score = 0
    if dist_km is not None:
        # FIX: same district still gets proximity bonus but is treated as ~0 km
        effective_km = dist_km
        if is_same_district:
            score += 3
        elif effective_km <= 30:
            score += 3
        elif effective_km <= 75:
            score += 2
        elif effective_km <= 150:
            score += 1
    if storage["available_capacity_mt"] >= farmer["quantity_mt"]:
        score += 2
    else:
        score += 1
    if storage["rate_per_mt_per_day"] == 0:
        score += 1
    return score


def score_transporter(farmer, transporter, dist_km, is_same_district):
    score = 0
    if dist_km is not None:
        if is_same_district:
            score += 3
        elif dist_km <= 20:
            score += 3
        elif dist_km <= 50:
            score += 2
        elif dist_km <= 100:
            score += 1

    qty = farmer["quantity_mt"]
    cap = transporter["capacity_mt"]
    if cap >= qty:
        score += 3                          # full load in one trip
    elif cap >= qty * 0.5:
        score += 1                          # needs 2 trips — workable
    elif cap >= qty * 0.25:
        score -= 1                          # needs 4+ trips — poor fit
    else:
        score -= 4                          # <25% of load — don't match this

    if transporter["is_refrigerated"]:
        score += 1
    return score


# ── Core matching ─────────────────────────────────────────────────────────────

def match_farmer(farmer, storages, transporters):
    harvest_date    = farmer["harvest_date"]
    crop            = farmer["crop"]
    farmer_district = farmer["district"]

    farmer_coords = get_coords(farmer_district)
    unknown_farmer_loc = farmer_coords is None

    warnings = []
    if unknown_farmer_loc:
        warnings.append(f"District '{farmer_district}' not in coordinates table — distance checks skipped.")

    # ── Filter storages ──
    eligible_storages = []
    for s in storages:
        if s.get("status") == "full":
            continue
        if not crops_compatible(crop, s["supported_crops"]):
            continue
        if not dates_overlap(harvest_date, s["available_from"], s["available_until"]):
            continue

        dist, is_same = distance_between(farmer_district, s["district"])
        if dist is None:
            eligible_storages.append((s, None, False))
        elif is_same or dist <= MAX_STORAGE_DISTANCE_KM:
            eligible_storages.append((s, dist, is_same))

    if not eligible_storages:
        return None, None, False, None, None, False, \
               [f"No cold storage found within {MAX_STORAGE_DISTANCE_KM} km for this crop and date."]

    eligible_storages.sort(
        key=lambda x: score_storage(farmer, x[0], x[1], x[2]), reverse=True
    )
    best_storage, storage_dist, storage_same_district = eligible_storages[0]

    # ── Filter transporters ──
    # FIX: also check operating_districts and per-transporter max_distance_km
    eligible_transporters = []
    for t in transporters:
        if t.get("status") == "booked":
            continue
        if not transporter_available(harvest_date, t["available_from"], t["available_until"], t):
            continue

        # FIX: check operating_districts if present
        op_districts = t.get("operating_districts", [])
        farmer_dist_canonical = canonical(farmer_district) or farmer_district.lower()
        operates_here = (
            not op_districts
            or "All Karnataka" in op_districts
            or any((canonical(d) or d.lower()) == farmer_dist_canonical for d in op_districts)
        )

        dist, is_same = distance_between(farmer_district, t["base_district"])

        # Both conditions must pass: base within distance AND operates in farmer's district
        if dist is None:
            if operates_here:
                eligible_transporters.append((t, None, False))
        elif is_same or dist <= MAX_TRANSPORTER_DISTANCE_KM:
            if operates_here:
                eligible_transporters.append((t, dist, is_same))

    if not eligible_transporters:
        return best_storage, storage_dist, storage_same_district, None, None, False, \
               warnings + [f"Storage found but no transporter within range of farm."]

    eligible_transporters.sort(
        key=lambda x: score_transporter(farmer, x[0], x[1], x[2]), reverse=True
    )
    best_transporter, transporter_dist, transport_same_district = eligible_transporters[0]

    return (best_storage, storage_dist, storage_same_district,
            best_transporter, transporter_dist, transport_same_district,
            warnings or None)


# ── Display ───────────────────────────────────────────────────────────────────

def print_separator(char="─", width=54):
    print(char * width)


def fmt_dist(dist_km, is_same_district=False):
    """FIX: show 'Same district' instead of '0 km away'."""
    if is_same_district:
        return "Same district"
    if dist_km is None:
        return "distance unknown"
    return f"{dist_km:.0f} km away"


def print_match(farmer, storage, s_dist, s_same,
                transporter, t_dist, t_same, warnings=None):
    print_separator("═")
    print(f"  FARMER: {farmer['farmer_name']}  |  ID: {farmer['id']}")
    print_separator()
    print(f"  Crop        : {farmer['crop']}")
    print(f"  Quantity    : {farmer['quantity_mt']} MT")
    print(f"  Harvest on  : {farmer['harvest_date']}  ({farmer['days_until_ready']} days away)")
    print(f"  Location    : {farmer['village']}, {farmer['district']}")

    if storage:
        print()
        print(f"  COLD STORAGE MATCH  ✓  [{fmt_dist(s_dist, s_same)}]")
        print_separator("·")
        print(f"  Facility    : {storage['facility_name']}")
        print(f"  Contact     : {storage['operator_name']}  📞 {storage['phone']}")
        print(f"  Location    : {storage['address']}, {storage['district']}")
        print(f"  Distance    : {fmt_dist(s_dist, s_same)}")
        print(f"  Available   : {storage['available_from']} → {storage['available_until']}")
        cap    = storage["available_capacity_mt"]
        needed = farmer["quantity_mt"]
        if cap >= needed:
            print(f"  Capacity    : {cap} MT available  ✓ (need {needed} MT)")
        else:
            print(f"  Capacity    : {cap} MT available  ⚠ (need {needed} MT — partial fit)")
        if storage["rate_per_mt_per_day"] > 0:
            est = storage["rate_per_mt_per_day"] * needed * 30
            print(f"  Rate        : ₹{storage['rate_per_mt_per_day']}/MT/day  (est. ₹{est:.0f}/30 days)")
        else:
            print(f"  Rate        : Negotiable")

    if transporter:
        print()
        print(f"  TRANSPORTER MATCH  ✓  [{fmt_dist(t_dist, t_same)} from farm]")
        print_separator("·")
        print(f"  Name        : {transporter['transporter_name']}")
        print(f"  Contact     : {transporter['driver_name']}  📞 {transporter['phone']}")
        print(f"  Base        : {transporter['base_district']}  ({fmt_dist(t_dist, t_same)} from farm)")
        print(f"  Vehicle     : {transporter['vehicle_type']}")
        print(f"  Capacity    : {transporter['capacity_mt']} MT  "
              f"{'(Refrigerated ✓)' if transporter['is_refrigerated'] else ''}")
        print(f"  Available   : {transporter['available_from']} → {transporter['available_until']}")
        if transporter["rate_per_mt_per_km"] > 0:
            print(f"  Rate        : ₹{transporter['rate_per_mt_per_km']}/MT/km")
        else:
            print(f"  Rate        : Negotiable")

    if warnings:
        for w in (warnings if isinstance(warnings, list) else [warnings]):
            print()
            print(f"  ⚠  {w}")

    print_separator("═")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 54)
    print("         KrishiSetu — Match Results")
    print("=" * 54)
    print(f"  Running at : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Max storage distance   : {MAX_STORAGE_DISTANCE_KM} km")
    print(f"  Max transport distance : {MAX_TRANSPORTER_DISTANCE_KM} km")
    print()

    farmers      = load(FARMERS_FILE)
    storages     = load(COLD_STORAGE_FILE)
    transporters = load(TRANSPORTERS_FILE)

    active_farmers      = [f for f in farmers      if f.get("status") == "unmatched"]
    active_storages     = [s for s in storages      if s.get("status") == "available"]
    active_transporters = [t for t in transporters  if t.get("status") == "available"]

    print(f"  Farmers waiting    : {len(active_farmers)}")
    print(f"  Cold storage slots : {len(active_storages)}")
    print(f"  Transporters ready : {len(active_transporters)}")
    print()

    if not active_farmers:
        print("  No farmers registered yet. Run farmer_input.py first.")
        return
    if not active_storages and not active_transporters:
        print("  No storage or transport registered. Run the other input scripts first.")
        return

    all_matches     = []
    matched_count   = 0
    partial_count   = 0
    unmatched_count = 0

    for farmer in active_farmers:
        (storage, s_dist, s_same,
         transporter, t_dist, t_same,
         warnings) = match_farmer(farmer, active_storages, active_transporters)

        all_matches.append({
            "matched_at":           datetime.now().isoformat(),
            "farmer_id":            farmer["id"],
            "farmer_name":          farmer["farmer_name"],
            "crop":                 farmer["crop"],
            "quantity_mt":          farmer["quantity_mt"],
            "harvest_date":         farmer["harvest_date"],
            "storage_id":           storage["id"]            if storage     else None,
            "storage_name":         storage["facility_name"] if storage     else None,
            # FIX: store "Same district" string instead of 0 when applicable
            "storage_dist_km":      ("Same district" if s_same else round(s_dist, 1)) if s_dist is not None else None,
            "transporter_id":       transporter["id"]                 if transporter else None,
            "transporter_name":     transporter["transporter_name"]   if transporter else None,
            "transporter_dist_km":  ("Same district" if t_same else round(t_dist, 1)) if t_dist is not None else None,
            "warnings":             warnings,
            "match_quality": (
                "full"    if storage and transporter else
                "partial" if storage or  transporter else
                "none"
            ),
        })

        if storage and transporter:
            matched_count += 1
        elif storage or transporter:
            partial_count += 1
        else:
            unmatched_count += 1

        print_match(farmer, storage, s_dist, s_same,
                    transporter, t_dist, t_same, warnings)

    save_matches(all_matches)

    print_separator("═")
    print("  SUMMARY")
    print_separator()
    print(f"  Full matches (storage + transport) : {matched_count}")
    print(f"  Partial matches                    : {partial_count}")
    print(f"  No match found                     : {unmatched_count}")
    print(f"\n  Results saved → {MATCHES_FILE}")
    print_separator("═")
    print()


if __name__ == "__main__":
    main()

# ── Dynamic rematch — called after every booking ──────────────────────────────

def rematch_affected_farmers(booked_storage_id, booked_transporter_id,
                              farmers=None, storages=None, transporters=None):
    """
    After a farmer books a slot, find all OTHER farmers who were matched
    to the same storage or transporter and re-run the matcher for them.
    Their match record is updated to the next best available option.
    Called automatically after confirming a booking.

    Pass farmers/storages/transporters from Bridge to avoid stale local JSON reads.
    """
    matches      = load(MATCHES_FILE)
    if farmers      is None: farmers      = load(FARMERS_FILE)
    if storages     is None: storages     = load(COLD_STORAGE_FILE)
    if transporters is None: transporters = load(TRANSPORTERS_FILE)

    # Find farmers whose current match is now stale
    affected = []
    for m in matches:
        if m.get("match_quality") == "none":
            continue
        storage_clash    = (booked_storage_id    and m.get("storage_id")    == booked_storage_id)
        transporter_clash = (booked_transporter_id and m.get("transporter_id") == booked_transporter_id)
        if storage_clash or transporter_clash:
            affected.append(m)

    if not affected:
        return 0   # nobody affected

    # Reload with latest capacity/status (booking.py already saved updated files)
    active_storages     = [s for s in storages     if s.get("status") != "full"]
    active_transporters = [t for t in transporters if t.get("status") != "booked"]

    updated = 0
    for m in affected:
        farmer = find_farmer(farmers, m["farmer_id"])
        if not farmer or farmer.get("status") == "booked":
            continue  # already booked, skip

        (new_storage, s_dist, s_same,
         new_transporter, t_dist, t_same,
         warnings) = match_farmer(farmer, active_storages, active_transporters)

        # Update this farmer's match record
        m["matched_at"]          = datetime.now().isoformat()
        m["rematch_reason"]      = (
            f"Storage '{booked_storage_id}' booked" if storage_clash else
            f"Transporter '{booked_transporter_id}' booked"
        )
        m["storage_id"]          = new_storage["id"]            if new_storage     else None
        m["storage_name"]        = new_storage["facility_name"] if new_storage     else None
        m["storage_dist_km"]     = ("Same district" if s_same else round(s_dist, 1)) if s_dist is not None else None
        m["transporter_id"]      = new_transporter["id"]                 if new_transporter else None
        m["transporter_name"]    = new_transporter["transporter_name"]   if new_transporter else None
        m["transporter_dist_km"] = ("Same district" if t_same else round(t_dist, 1)) if t_dist is not None else None
        m["warnings"]            = warnings
        m["match_quality"]       = (
            "full"    if new_storage and new_transporter else
            "partial" if new_storage or  new_transporter else
            "none"
        )
        updated += 1

    if updated:
        save_matches(matches)

    return updated


def find_farmer(farmers, farmer_id):
    return next((f for f in farmers if f["id"] == farmer_id), None)