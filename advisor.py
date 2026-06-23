"""
advisor.py — KrishiSetu Proactive Harvest Advisor
Reads all registered farmers and tells each one:
  - What the next 14 days look like for storage + transport
  - Which days to AVOID (nothing available)
  - Which window is BEST to harvest
  - What competing supply exists from other FPOs
  - Cost estimate for different storage durations

Run standalone:  python advisor.py
Or from menu:    option 8 in run.py
"""

import json
import os
import math
from datetime import date, timedelta, datetime
from matcher import get_coords, haversine_km, MAX_STORAGE_DISTANCE_KM, MAX_TRANSPORTER_DISTANCE_KM

DATA_DIR          = "data"

# How many days ahead to show per crop (from harvest date onward)
HORIZON_BY_CROP = {
    "Tomato":       7,
    "Banana":       5,
    "Mango":        7,
    "Onion":       21,
    "Grapes":      14,
    "Pomegranate": 21,
    "Pineapple":   10,
}
DEFAULT_HORIZON = 14

# How many days BEFORE the ready date we allow as early-harvest suggestion
# (crop stress, weather risk etc — keep this small)
PRE_HARVEST_BUFFER_BY_CROP = {
    "Tomato":      2,   # can pull 2 days early if market is very good
    "Banana":      1,
    "Mango":       2,
    "Onion":       3,   # more flexible
    "Grapes":      2,
    "Pomegranate": 3,
    "Pineapple":   1,
}
DEFAULT_PRE_HARVEST_BUFFER = 2
FARMERS_FILE      = os.path.join(DATA_DIR, "farmers.json")
STORAGES_FILE     = os.path.join(DATA_DIR, "cold_storages.json")
TRANSPORTERS_FILE = os.path.join(DATA_DIR, "transporters.json")
BOOKINGS_FILE     = os.path.join(DATA_DIR, "bookings.json")


# ── Loaders ───────────────────────────────────────────────────────────────────

def load(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        raw = f.read().strip()
        return json.loads(raw) if raw else []


# ── Storage availability for a given window ───────────────────────────────────

def free_mt_on_date(storage, target_date: date, bookings: list) -> float:
    """
    Real free capacity on a specific date = total capacity
    minus all confirmed bookings whose window overlaps that date.
    """
    used = 0.0
    for b in bookings:
        if b.get("storage_id") != storage["id"]:
            continue
        if b.get("status") == "cancelled":
            continue
        try:
            b_from  = date.fromisoformat(b["storage_from"])
            b_until = date.fromisoformat(b["storage_until"])
        except (KeyError, ValueError):
            continue
        if b_from <= target_date <= b_until:
            used += b.get("quantity_mt", 0)
    return max(0.0, storage["available_capacity_mt"] - used)


def storage_available_on(storage, target_date: date, quantity_mt: float, bookings: list) -> bool:
    """
    True if storage exists and has ANY free capacity on this date.
    Does NOT require free_mt >= quantity_mt — partial fits are still options.
    Use free_mt_on_date() separately to check the actual gap.
    """
    try:
        sf = date.fromisoformat(storage["available_from"])
        su = date.fromisoformat(storage["available_until"])
    except (KeyError, ValueError):
        return False
    if not (sf <= target_date <= su):
        return False
    if storage.get("status") == "full":
        return False
    return free_mt_on_date(storage, target_date, bookings) > 0


# ── Transport availability for a given date ───────────────────────────────────

def transport_free_on(transporter, target_date: date, bookings: list) -> bool:
    """True if transporter has no confirmed booking blocking this date."""
    # Check availability window
    try:
        tf = date.fromisoformat(transporter["available_from"])
        tu = date.fromisoformat(transporter["available_until"])
    except (KeyError, ValueError):
        return False
    if not (tf <= target_date <= tu):
        return False
    if transporter.get("status") == "booked":
        return False

    # Check blocked_dates from bookings
    for block in transporter.get("blocked_dates", []):
        try:
            b_from  = date.fromisoformat(block["from"])
            b_until = date.fromisoformat(block["until"])
        except (KeyError, ValueError):
            continue
        if b_from <= target_date <= b_until:
            return False
    return True


# ── Competing supply ──────────────────────────────────────────────────────────

def competing_mt_on(farmer_id: str, crop: str, district: str,
                    target_date: date, farmers: list) -> float:
    """
    How many MT of the same crop from the same district
    are other farmers planning to harvest on this date?
    """
    total = 0.0
    for f in farmers:
        if f["id"] == farmer_id:
            continue
        if f.get("crop", "").lower() != crop.lower():
            continue
        if f.get("district", "").lower() != district.lower():
            continue
        try:
            h = date.fromisoformat(str(f["harvest_date"]))
        except (KeyError, ValueError):
            continue
        # Count as competing if they plan to harvest within ±2 days
        if abs((h - target_date).days) <= 2:
            total += f.get("quantity_mt", 0)
    return total


# ── Core: build 14-day outlook for one farmer ─────────────────────────────────

def build_outlook(farmer, storages, transporters, bookings, all_farmers, horizon_days=None):
    """
    For each day in the harvest window, compute:
      - Any storage available? How much free MT?
      - Any transport available? How many trucks?
      - How much competing supply?
      - A score (higher = better day to harvest)

    Window starts from (harvest_date - pre_harvest_buffer) — never before today.
    Window length is crop-specific via HORIZON_BY_CROP.

    Returns list of day-dicts, sorted by date.
    """
    today    = date.today()
    crop     = farmer["crop"]
    district = farmer["district"]
    qty      = farmer["quantity_mt"]

    harvest_date   = date.fromisoformat(str(farmer["harvest_date"]))
    pre_buffer     = PRE_HARVEST_BUFFER_BY_CROP.get(crop, DEFAULT_PRE_HARVEST_BUFFER)
    horizon_days   = horizon_days or HORIZON_BY_CROP.get(crop, DEFAULT_HORIZON)

    # Window starts from earliest realistic harvest (never before today)
    window_start = max(today, harvest_date - timedelta(days=pre_buffer))
    # Window ends horizon_days after the original harvest date
    window_end   = harvest_date + timedelta(days=horizon_days)

    # Filter storages that serve this crop and are within distance
    relevant_storages = []
    farmer_coords = get_coords(district)
    for s in storages:
        if s.get("status") == "full":
            continue
        supported = s.get("supported_crops", [])
        if "All" not in supported and crop.lower() not in [c.lower() for c in supported]:
            continue
        # Distance check
        if farmer_coords:
            storage_coords = get_coords(s["district"])
            if storage_coords:
                dist_km = haversine_km(farmer_coords[0], farmer_coords[1],
                                       storage_coords[0], storage_coords[1])
                if dist_km > MAX_STORAGE_DISTANCE_KM:
                    continue
        relevant_storages.append(s)

    # Filter transporters that serve this district AND are within distance
    from districts import canonical
    farmer_key = canonical(district) or district.lower()
    relevant_transporters = []
    for t in transporters:
        if t.get("status") == "booked":
            continue
        # Distance check — transporter base must be within threshold
        if farmer_coords:
            t_coords = get_coords(t["base_district"])
            if t_coords:
                dist_km = haversine_km(farmer_coords[0], farmer_coords[1],
                                       t_coords[0], t_coords[1])
                if dist_km > MAX_TRANSPORTER_DISTANCE_KM:
                    continue
        # Operating districts check (only if distance passed)
        op_districts = t.get("operating_districts", [])
        if op_districts and "All Karnataka" not in op_districts:
            if not any((canonical(d) or d.lower()) == farmer_key for d in op_districts):
                continue
        relevant_transporters.append(t)

    days = []
    current = window_start
    while current <= window_end:
        day = current
        current += timedelta(days=1)

        # Storage on this day
        storage_options = []
        for s in relevant_storages:
            if storage_available_on(s, day, qty, bookings):
                free = free_mt_on_date(s, day, bookings)
                storage_options.append({
                    "id":   s["id"],
                    "name": s["facility_name"],
                    "free_mt": round(free, 1),
                    "rate": s["rate_per_mt_per_day"],
                })

        # Transport on this day — check truck is free for the FULL block
        # (base→farm→storage→base round trip), not just on the harvest day itself
        transport_options = []
        for t in relevant_transporters:
            if not transport_free_on(t, day, bookings):
                continue
            # Simulate the full transport block for this harvest day
            from booking import calc_transport_block
            from matcher import distance_between
            d1, _ = distance_between(t["base_district"], farmer["district"])
            d2, _ = distance_between(farmer["district"],  storage_options[0]["id"] if False else farmer["district"])
            # Use first storage option's district for farm→storage leg if available
            if storage_options:
                # find full storage record to get district
                s_rec = next((s for s in relevant_storages if s["id"] == storage_options[0]["id"]), None)
                d2, _ = distance_between(farmer["district"], s_rec["district"]) if s_rec else (0, False)
                d3, _ = distance_between(s_rec["district"] if s_rec else farmer["district"], t["base_district"])
            else:
                d2, d3 = 0, d1  # no storage — just base→farm→base
            sim_start, sim_end = calc_transport_block(
                day,
                farm_to_storage_km=d2 or 0,
                base_to_farm_km=d1 or 0,
                storage_to_base_km=d3 or 0,
            )
            # Check simulated block doesn't overlap any existing block
            clash = False
            for block in t.get("blocked_dates", []):
                try:
                    b_from  = date.fromisoformat(block["from"])
                    b_until = date.fromisoformat(block["until"])
                    if not (sim_end < b_from or sim_start > b_until):
                        clash = True
                        break
                except (KeyError, ValueError):
                    continue
            if not clash:
                transport_options.append({
                    "id":       t["id"],
                    "name":     t["transporter_name"],
                    "capacity": t["capacity_mt"],
                })

        competing = competing_mt_on(farmer["id"], crop, district, day, all_farmers)

        # Score this day
        score, flags = _score_day(qty, storage_options, transport_options, competing, day)

        days.append({
            "date":              day,
            "storage_options":   storage_options,
            "transport_options": transport_options,
            "competing_mt":      round(competing, 1),
            "score":             score,
            "flags":             flags,
            "storage_count":     len(storage_options),
            "transport_count":   len(transport_options),
            "total_free_mt":     sum(s["free_mt"] for s in storage_options),
            "total_truck_cap":   sum(t["capacity"] for t in transport_options),
        })

    return days


def _score_day(qty, storage_options, transport_options, competing_mt, day) -> tuple:
    """Score a single day. Returns (score, [flags])."""
    score = 0
    flags = []

    if storage_options:
        total_free = sum(s["free_mt"] for s in storage_options)
        if total_free >= qty:
            score += 3
            flags.append("plenty of storage")
        elif total_free >= qty * 0.5:
            score += 1
            flags.append(f"storage partial — {total_free:.0f} MT free, need {qty:.0f} MT")
        else:
            score += 0
            flags.append(f"storage very limited — only {total_free:.0f} MT free of {qty:.0f} MT needed")
    else:
        score -= 3
        flags.append("NO storage available in this district")

    if transport_options:
        total_cap = sum(t["capacity"] for t in transport_options)
        if total_cap >= qty:
            score += 2
            flags.append(f"{len(transport_options)} truck(s) available")
        else:
            score += 1
            flags.append(f"transport limited ({total_cap:.1f} MT capacity)")
    else:
        score -= 10   # hard penalty — no transport = not a viable harvest day
        flags.append("NO transport available")

    if competing_mt > qty * 2:
        score -= 2
        flags.append(f"high competition ({competing_mt:.0f} MT from other farmers)")
    elif competing_mt > qty:
        score -= 1
        flags.append(f"some competition ({competing_mt:.0f} MT nearby)")
    elif competing_mt == 0:
        score += 1
        flags.append("no competing supply")

    if day.weekday() == 6:   # Sunday
        score -= 1
        flags.append("Sunday — some mandis closed")

    return score, flags


# ── Display ───────────────────────────────────────────────────────────────────

def sep(c="─", w=58): print(c * w)


def print_advisor_report(farmer, outlook, storages, transporters, bookings):
    harvest_date = date.fromisoformat(str(farmer["harvest_date"]))
    days_left    = (harvest_date - date.today()).days
    qty          = farmer["quantity_mt"]
    crop         = farmer["crop"]

    sep("═")
    print(f"  HARVEST ADVISORY — {farmer['farmer_name']}")
    sep()
    print(f"  Crop         : {crop}  |  {qty} MT")
    print(f"  Your district: {farmer['district']}")
    print(f"  Current plan : Harvest on {harvest_date}  ({days_left} days away)")
    sep()

    # ── Best window ───────────────────────────────────────────────────────
    # Only days with BOTH storage and transport qualify as "best"
    viable_days = [
        d for d in outlook
        if d["storage_count"] > 0 and d["transport_count"] > 0
    ]
    best_days = sorted(viable_days, key=lambda x: x["score"], reverse=True)
    avoid_days = [d for d in outlook if d["score"] < 0]

    if best_days:
        best = best_days[0]
        print()
        print(f"  ✅  BEST WINDOW TO HARVEST")
        sep("·")
        print(f"  Date     : {best['date'].strftime('%A, %d %b %Y')}")
        for flag in best["flags"]:
            icon = "✓" if any(w in flag for w in ["available","plenty","no competing","truck"]) else "⚠"
            print(f"  {icon}  {flag.capitalize()}")
        if best["storage_options"]:
            cheapest = min(best["storage_options"], key=lambda s: s["rate"])
            print(f"  Storage  : {cheapest['name']}  (₹{cheapest['rate']}/MT/day, {cheapest['free_mt']} MT free)")
        if best["transport_options"]:
            total_cap = best["total_truck_cap"]
            truck_names = ", ".join(t["name"] for t in best["transport_options"])
            print(f"  Transport: {truck_names}  ({total_cap:.1f} MT total capacity)")
            if total_cap < qty:
                gap = qty - total_cap
                trips = math.ceil(qty / total_cap)
                print(f"  ⚠  CAPACITY GAP: Only {total_cap:.1f} MT can move in one trip.")
                print(f"     Your crop: {qty} MT  →  Shortfall: {gap:.1f} MT")
                print(f"     Options:")
                print(f"       1. Book {trips} trips with same truck (check availability)")
                print(f"       2. Find {math.ceil(gap / total_cap)} more truck(s) for remaining {gap:.1f} MT")
                print(f"       3. Store {gap:.1f} MT locally and transport {total_cap:.1f} MT now")
    else:
        has_storage   = any(d["storage_count"] > 0 for d in outlook)
        has_transport = any(d["transport_count"] > 0 for d in outlook)
        max_free_mt   = max((d["total_free_mt"] for d in outlook), default=0)

        if has_storage and not has_transport:
            print()
            print("  🟡  PARTIAL MATCH — Storage available, no transport found.")
            sep("·")
            best_storage_day = max(
                (d for d in outlook if d["storage_count"] > 0),
                key=lambda d: d["total_free_mt"]
            )
            print(f"  ✓  Cold storage available near your district ({max_free_mt:.0f} MT free).")
            print(f"     Best option: {best_storage_day['storage_options'][0]['name']}")
            print(f"  ❌  No transporter registered within range of {farmer['district']}.")
            print()
            print("  What you can do:")
            print("  1. Ask a local truck owner to register on KrishiSetu.")
            print("  2. Contact the cold storage directly — they may know local transporters.")
            print(f"     → {best_storage_day['storage_options'][0]['name']}")
            print("  3. Arrange your own transport and use the storage slot.")

        elif has_transport and not has_storage:
            print()
            print("  🟡  PARTIAL MATCH — Transport available, no cold storage found.")
            sep("·")
            print(f"  ✓  Transporters available near your district.")
            print(f"  ❌  No cold storage registered within range of {farmer['district']}.")
            print()
            print("  What you can do:")
            print("  1. Sell directly at the mandi — transport is ready.")
            print("  2. Ask a nearby cold storage operator to register on KrishiSetu.")
            print("  3. Check if a neighbouring district has storage (extend the search).")

        else:
            print()
            print("  ❌  No storage or transport found near your district.")
            sep("·")
            print(f"  ❌  No cold storage registered near {farmer['district']}.")
            print(f"  ❌  No transporter registered near {farmer['district']}.")
            print()
            print("  What you can do:")
            print("  1. Register local cold storage and transport operators on KrishiSetu.")
            print("  2. Consider selling directly at the nearest mandi.")
            print("  3. Check back after more resources register in your area.")

    # ── Current harvest date check ────────────────────────────────────────
    print()
    current_day = next((d for d in outlook if d["date"] == harvest_date), None)
    if current_day:
        print(f"  📅  YOUR CURRENT PLAN  ({harvest_date.strftime('%A, %d %b')})")
        sep("·")
        if current_day["storage_count"] == 0 and current_day["transport_count"] == 0:
            print("  ❌  No storage OR transport available on this date!")
            print("  ⚠   Strongly recommend changing your harvest date.")
        elif current_day["storage_count"] == 0:
            print("  ❌  No cold storage available on your current harvest date.")
        elif current_day["transport_count"] == 0:
            print("  ❌  No transport available on your current harvest date.")
        else:
            print(f"  ✓   Storage   : {current_day['storage_count']} option(s), {current_day['total_free_mt']:.0f} MT free")
            cap = current_day["total_truck_cap"]
            print(f"  ✓   Transport : {current_day['transport_count']} truck(s), {cap:.1f} MT total capacity")
            if cap < qty:
                gap = qty - cap
                trips = math.ceil(qty / cap)
                print(f"  ⚠   CAPACITY GAP on your plan date:")
                print(f"      Truck capacity {cap:.1f} MT vs your crop {qty} MT — shortfall {gap:.1f} MT")
                print(f"      → Need {trips} trips, or find {math.ceil(gap/max(cap,1))} more truck(s)")
        if current_day["competing_mt"] > 0:
            print(f"  ⚠   Competing : {current_day['competing_mt']} MT from other farmers in your area")

    # ── 14-day table ──────────────────────────────────────────────────────
    print()
    print(f"  📊  14-DAY OUTLOOK — {crop.upper()}, {farmer['district'].upper()}")
    sep("·")
    print(f"  {'Date':<14} {'Storage':^10} {'Transport':^11} {'Competing':^10} {'Verdict':>8}")
    sep("·")

    for d in outlook:
        is_harvest = (d["date"] == harvest_date)
        is_best    = best_days and d["date"] == best_days[0]["date"]

        storage_str   = f"{d['total_free_mt']:.0f}MT" if d["storage_count"] > 0 else "NONE ❌"
        transport_str = f"{d['total_truck_cap']:.0f}MT" if d["transport_count"] > 0 else "NONE ❌"
        compete_str   = f"{d['competing_mt']:.0f}MT" if d["competing_mt"] > 0 else "Low ✓"
        is_viable = d["storage_count"] > 0 and d["transport_count"] > 0
        score_str = (
            "BEST ⭐"  if is_best and is_viable else
            "AVOID ❌" if not is_viable else
            "OK ✓"    if d["score"] > 0 else
            "Tight ⚠"
        )

        marker = " ◀ YOUR PLAN" if is_harvest else ""
        date_str = d["date"].strftime("%a %d %b")
        print(f"  {date_str:<14} {storage_str:^10} {transport_str:^11} {compete_str:^10} {score_str:>8}{marker}")

    sep("·")

    # ── Days to avoid ─────────────────────────────────────────────────────
    if avoid_days:
        print()
        print(f"  ❌  AVOID THESE DATES")
        sep("·")
        for d in avoid_days:
            reasons = [f for f in d["flags"] if "NO" in f or "competition" in f.lower()]
            reason_str = ", ".join(reasons) if reasons else "poor conditions"
            print(f"  {d['date'].strftime('%a %d %b')}  —  {reason_str}")

    # ── Cost estimate ─────────────────────────────────────────────────────
    if best_days and best_days[0]["storage_options"]:
        print()
        print(f"  💰  STORAGE COST ESTIMATE  ({qty} MT)")
        sep("·")
        storage = best_days[0]["storage_options"][0]
        rate    = storage["rate"]
        for duration in [7, 14, 30]:
            cost = rate * qty * duration
            print(f"  {duration:>3} days  →  ₹{rate}/MT/day × {qty} MT = ₹{cost:,.0f}")

    # ── Recommendation ────────────────────────────────────────────────────
    print()
    sep("·")
    if best_days:
        best = best_days[0]
        if best["date"] != harvest_date:
            delta = (best["date"] - harvest_date).days
            direction = f"{abs(delta)} days later" if delta > 0 else f"{abs(delta)} days earlier"
            # Only suggest shifting if the best day is meaningfully better
            current_viable = any(
                d["date"] == harvest_date and d["storage_count"] > 0 and d["transport_count"] > 0
                for d in outlook
            )
            if current_viable:
                best_score    = best["score"]
                current_score = next((d["score"] for d in outlook if d["date"] == harvest_date), 0)
                best_cap      = best["total_truck_cap"]
                current_cap   = next((d["total_truck_cap"] for d in outlook if d["date"] == harvest_date), 0)
                # Only recommend shift if: meaningfully better score AND better transport capacity
                if best_score > current_score + 1 and best_cap >= current_cap:
                    print(f"  💡  Recommendation: Shift harvest to {best['date'].strftime('%A %d %b')} ({direction})")
                    reasons = []
                    if best_cap > current_cap:
                        reasons.append(f"more transport capacity ({best_cap:.0f} MT vs {current_cap:.0f} MT)")
                    if best["competing_mt"] < next((d["competing_mt"] for d in outlook if d["date"] == harvest_date), 0):
                        reasons.append("less competing supply")
                    if reasons:
                        print(f"      Reason: {', '.join(reasons)}.")
                else:
                    print(f"  💡  Your current plan ({harvest_date.strftime('%d %b')}) is good. ✓")
                    if current_cap < qty:
                        gap = qty - current_cap
                        print(f"      ⚠  But you still need {gap:.1f} MT more transport capacity.")
                        print(f"         Register more trucks or book multiple trips.")
            else:
                print(f"  💡  Recommendation: Shift harvest to {best['date'].strftime('%A %d %b')} ({direction})")
                print(f"      Reason: Storage + transport both available on that date.")
        else:
            print(f"  💡  Your current plan ({harvest_date.strftime('%d %b')}) is already the best window. ✓")
    else:
        print("  💡  No viable window found. Register more transporters or storage near your district.")

    sep("═")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def run_advisor(farmer_id=None):
    """
    If farmer_id given → show advisory for that farmer only.
    If None → show for ALL registered farmers.
    """
    farmers      = load(FARMERS_FILE)
    storages     = load(STORAGES_FILE)
    transporters = load(TRANSPORTERS_FILE)
    bookings     = load(BOOKINGS_FILE)

    active_farmers = [f for f in farmers if f.get("status") != "matched"]

    if not active_farmers:
        print("\n  No active farmers to advise. Register farmers first (option 1).")
        return

    if farmer_id:
        targets = [f for f in active_farmers if f["id"] == farmer_id]
        if not targets:
            print(f"\n  ✗ Farmer '{farmer_id}' not found or already matched.")
            return
    else:
        # Ask which farmer or all
        print(f"\n  {len(active_farmers)} active farmer(s):")
        for i, f in enumerate(active_farmers, 1):
            days_left = (date.fromisoformat(str(f["harvest_date"])) - date.today()).days
            print(f"  {i}. {f['farmer_name']}  ({f['crop']}, {f['district']}, harvest in {days_left}d)")
        print(f"  A. All farmers")
        choice = input("\n  Show advisory for (number or A): ").strip().upper()

        if choice == "A":
            targets = active_farmers
        else:
            try:
                idx = int(choice) - 1
                targets = [active_farmers[idx]]
            except (ValueError, IndexError):
                print("  Invalid choice.")
                return

    for farmer in targets:
        outlook = build_outlook(farmer, storages, transporters, bookings, farmers)
        print_advisor_report(farmer, outlook, storages, transporters, bookings)
        if len(targets) > 1:
            input("  Press Enter for next farmer ...")
            print()


def main():
    run_advisor()


if __name__ == "__main__":
    main()