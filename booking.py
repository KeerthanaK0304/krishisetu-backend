"""
booking.py — Terminal booking flow for KrishiSetu
Farmer enters their ID, sees their match, sets storage duration,
confirms → slot capacity subtracted, transport blocked by date.
"""

import json
import os
import uuid
import math
from datetime import datetime, date, timedelta

DATA_DIR         = "data"
FARMERS_FILE     = os.path.join(DATA_DIR, "farmers.json")
STORAGES_FILE    = os.path.join(DATA_DIR, "cold_storages.json")
TRANSPORTERS_FILE= os.path.join(DATA_DIR, "transporters.json")
MATCHES_FILE     = os.path.join(DATA_DIR, "matches.json")
BOOKINGS_FILE    = os.path.join(DATA_DIR, "bookings.json")


# ── Loaders / savers ──────────────────────────────────────────────────────────

def load(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        raw = f.read().strip()
        return json.loads(raw) if raw else []

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

def find_by_id(records, rid):
    return next((r for r in records if r["id"] == rid), None)


# ── Transport block dates ─────────────────────────────────────────────────────

def calc_transport_block(harvest_date_str, farm_to_storage_km, base_to_farm_km=0, storage_to_base_km=0):
    """
    Block transport for the full round trip:
      base → farm → storage → base

    travel_days = ceil(total_km / 300) — ~300 km/day for a loaded truck.
    Block starts 1 day before harvest (travel to farm day).
    Block ends travel_days after harvest + 1 buffer day.
    Minimum block = 3 days.
    """
    harvest    = date.fromisoformat(str(harvest_date_str))
    total_km   = (base_to_farm_km or 0) + (farm_to_storage_km or 0) + (storage_to_base_km or 0)
    travel_days = max(1, math.ceil(total_km / 300))
    block_start = harvest - timedelta(days=1)
    block_end   = harvest + timedelta(days=travel_days + 1)
    return block_start, block_end


def is_transport_blocked(transporter, start: date, end: date) -> bool:
    """Check if transporter has any existing booking overlapping this window."""
    bookings = load(BOOKINGS_FILE)
    for b in bookings:
        if b.get("transporter_id") != transporter["id"]:
            continue
        if b.get("status") == "cancelled":
            continue
        b_start = date.fromisoformat(b["transport_block_start"])
        b_end   = date.fromisoformat(b["transport_block_end"])
        # Overlap check
        if not (end < b_start or start > b_end):
            return True
    return False


def is_storage_available(storage, quantity_mt, store_from: date, store_until: date) -> bool:
    """
    Check if storage has enough capacity for the requested window,
    considering already-booked capacity for overlapping bookings.
    """
    bookings = load(BOOKINGS_FILE)
    used_mt = 0.0
    for b in bookings:
        if b.get("storage_id") != storage["id"]:
            continue
        if b.get("status") == "cancelled":
            continue
        b_start = date.fromisoformat(b["storage_from"])
        b_end   = date.fromisoformat(b["storage_until"])
        if not (store_until < b_start or store_from > b_end):
            used_mt += b.get("quantity_mt", 0)
    free_mt = storage["available_capacity_mt"] - used_mt
    return free_mt >= quantity_mt, free_mt


# ── Printer helpers ───────────────────────────────────────────────────────────

def sep(c="─", w=52): print(c * w)

def print_match_summary(farmer, storage, transporter, match):
    sep("═")
    print(f"  Match found for: {farmer['farmer_name']}")
    sep()
    print(f"  Crop      : {farmer['crop']}  |  {farmer['quantity_mt']} MT")
    print(f"  Harvest   : {farmer['harvest_date']}")
    print()
    if storage:
        dist = match.get("storage_dist_km", "?")
        print(f"  STORAGE   : {storage['facility_name']}")
        print(f"  Location  : {storage['address']}, {storage['district']}  ({dist} km)")
        print(f"  Capacity  : {storage['available_capacity_mt']} MT total")
        print(f"  Rate      : ₹{storage['rate_per_mt_per_day']}/MT/day")
    else:
        print("  STORAGE   : No match found")
    print()
    if transporter:
        dist = match.get("transporter_dist_km", "?")
        print(f"  TRANSPORT : {transporter['transporter_name']}  ({transporter['driver_name']})")
        print(f"  Vehicle   : {transporter['vehicle_type']}  |  {transporter['capacity_mt']} MT cap")
        print(f"  Base      : {transporter['base_district']}  ({dist} km from farm)")
        print(f"  Rate      : ₹{transporter['rate_per_mt_per_km']}/MT/km")
    else:
        print("  TRANSPORT : No match found")
    sep("═")


# ── Advisory preview inside booking ──────────────────────────────────────────

def _show_advisory_preview(farmer, storage, transporter):
    """
    Before showing the booking form, give the farmer a quick look
    at whether TODAY is actually a good day to harvest.
    Calls advisor without printing the full report — just the key warning.
    """
    try:
        from advisor import build_outlook
        from datetime import date
        bookings = load(BOOKINGS_FILE)
        storages = load(STORAGES_FILE) if storage else []
        transporters = load(TRANSPORTERS_FILE) if transporter else []
        all_farmers = load(FARMERS_FILE)

        outlook = build_outlook(farmer, storages, transporters, bookings, all_farmers, horizon_days=14)
        harvest_dt = date.fromisoformat(str(farmer["harvest_date"]))

        # Find the best day
        best_days = sorted([d for d in outlook if d["score"] > 0],
                           key=lambda x: x["score"], reverse=True)

        current = next((d for d in outlook if d["date"] == harvest_dt), None)

        print()
        print("  ── Harvest Window Check ─" + "─" * 28)
        if current:
            if current["score"] < 0:
                print(f"  ⚠  Your harvest date ({harvest_dt}) has issues:")
                for flag in current["flags"]:
                    if "NO" in flag or "competition" in flag.lower():
                        print(f"     • {flag}")
                if best_days and best_days[0]["date"] != harvest_dt:
                    best = best_days[0]
                    delta = (best["date"] - harvest_dt).days
                    direction = f"{abs(delta)}d later" if delta > 0 else f"{abs(delta)}d earlier"
                    print(f"  💡 Better window: {best['date'].strftime('%A %d %b')} ({direction})")
                    print(f"     Storage: {best['storage_count']} option(s)  |  Transport: {best['transport_count']} truck(s)")
            else:
                print(f"  ✓  Your harvest date ({harvest_dt}) looks good.")
                for flag in current["flags"]:
                    print(f"     • {flag}")
        print("  " + "─" * 50)
        print("  Run option 8 for a full 14-day advisory.")
        print()
    except Exception:
        pass   # advisory preview is non-fatal


# ── Main booking flow ─────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 52)
    print("       KrishiSetu — Farmer Booking")
    print("=" * 52)

    # ── Step 1: Farmer ID ─────────────────────────────────────────────────
    farmer_id = input("\n  Enter your Farmer ID: ").strip()
    if not farmer_id:
        print("  No ID entered. Exiting.")
        return

    farmers = load(FARMERS_FILE)
    farmer  = find_by_id(farmers, farmer_id)
    if not farmer:
        print(f"\n  ✗ Farmer ID '{farmer_id}' not found.")
        print("  Run option 1 to register, then option 4 to find matches first.")
        return

    if farmer.get("status") == "matched":
        print(f"\n  ✗ {farmer['farmer_name']} already has a confirmed booking.")
        print("  Use option 5 to view your booking details.")
        return

    # ── Step 2: Always re-run matcher live — never trust stale matches.json ──
    # matches.json can be outdated if another farmer just booked a resource.
    storages     = load(STORAGES_FILE)
    transporters = load(TRANSPORTERS_FILE)
    active_storages     = [s for s in storages     if s.get("status") != "full"]
    active_transporters = [t for t in transporters if t.get("status") != "booked"]

    from matcher import match_farmer, fmt_dist
    (storage, s_dist, s_same,
     transporter, t_dist, t_same,
     match_warnings) = match_farmer(farmer, active_storages, active_transporters)

    # Persist fresh match back to matches.json so view_matches() stays accurate
    matches = load(MATCHES_FILE)
    found_in_matches = False
    for m in matches:
        if m["farmer_id"] == farmer_id:
            found_in_matches = True
            m["matched_at"]          = datetime.now().isoformat()
            m["storage_id"]          = storage["id"]            if storage     else None
            m["storage_name"]        = storage["facility_name"] if storage     else None
            m["storage_dist_km"]     = ("Same district" if s_same else round(s_dist, 1)) if s_dist is not None else None
            m["transporter_id"]      = transporter["id"]                 if transporter else None
            m["transporter_name"]    = transporter["transporter_name"]   if transporter else None
            m["transporter_dist_km"] = ("Same district" if t_same else round(t_dist, 1)) if t_dist is not None else None
            m["match_quality"]       = (
                "full"    if storage and transporter else
                "partial" if storage or  transporter else
                "none"
            )
            m["rematch_reason"] = "live re-matched at booking time"
    if not found_in_matches:
        # No prior match record — create one
        matches.append({
            "matched_at":          datetime.now().isoformat(),
            "farmer_id":           farmer_id,
            "farmer_name":         farmer["farmer_name"],
            "crop":                farmer["crop"],
            "quantity_mt":         farmer["quantity_mt"],
            "harvest_date":        farmer["harvest_date"],
            "storage_id":          storage["id"]            if storage     else None,
            "storage_name":        storage["facility_name"] if storage     else None,
            "storage_dist_km":     ("Same district" if s_same else round(s_dist, 1)) if s_dist is not None else None,
            "transporter_id":      transporter["id"]                 if transporter else None,
            "transporter_name":    transporter["transporter_name"]   if transporter else None,
            "transporter_dist_km": ("Same district" if t_same else round(t_dist, 1)) if t_dist is not None else None,
            "match_quality":       (
                "full"    if storage and transporter else
                "partial" if storage or  transporter else
                "none"
            ),
        })
    save_json(MATCHES_FILE, matches)

    if not storage and not transporter:
        print(f"\n  ✗ No storage or transport currently available for your crop and date.")
        print("  All matched resources may be booked. Try again later.")
        return

    # Build match dict for display (shape expected by print_match_summary)
    match = {
        "storage_dist_km":     ("Same district" if s_same else round(s_dist, 1)) if s_dist is not None else None,
        "transporter_dist_km": ("Same district" if t_same else round(t_dist, 1)) if t_dist is not None else None,
    }

    # ── Step 3: Show advisory preview then match ─────────────────────────
    print()
    _show_advisory_preview(farmer, storage, transporter)
    print_match_summary(farmer, storage, transporter, match)

    if not storage and not transporter:
        print("\n  No bookable resources found. Exiting.")
        return

    # ── Step 4: Ask storage duration ─────────────────────────────────────
    print()
    while True:
        days_raw = input("  How many days do you need storage? (e.g. 30): ").strip()
        try:
            storage_days = int(days_raw)
            if storage_days <= 0:
                print("  ✗ Must be at least 1 day.")
                continue
            if storage_days > 365:
                print("  ✗ Max 365 days.")
                continue
            break
        except ValueError:
            print("  ✗ Please enter a whole number.")

    harvest_date  = date.fromisoformat(str(farmer["harvest_date"]))
    storage_from  = harvest_date
    storage_until = harvest_date + timedelta(days=storage_days)

    # Transport block — full round trip: base→farm→storage→base
    from matcher import distance_between
    base_to_farm_km    = 0.0
    farm_to_storage_km = 0.0
    storage_to_base_km = 0.0
    if transporter and storage:
        d1, _ = distance_between(transporter["base_district"], farmer["district"])
        d2, _ = distance_between(farmer["district"],           storage["district"])
        d3, _ = distance_between(storage["district"],          transporter["base_district"])
        base_to_farm_km    = d1 or 0.0
        farm_to_storage_km = d2 or 0.0
        storage_to_base_km = d3 or 0.0
    elif transporter:
        d1, _ = distance_between(transporter["base_district"], farmer["district"])
        base_to_farm_km = d1 or 0.0

    transport_block_start, transport_block_end = calc_transport_block(
        harvest_date,
        farm_to_storage_km=farm_to_storage_km,
        base_to_farm_km=base_to_farm_km,
        storage_to_base_km=storage_to_base_km,
    )

    # Cost estimate
    qty      = farmer["quantity_mt"]
    rate     = storage["rate_per_mt_per_day"] if storage else 0
    cost_est = rate * qty * storage_days if storage else 0

    # ── Step 5: Check availability ────────────────────────────────────────
    print()
    sep()
    print("  Checking availability ...")

    storage_ok  = True
    free_mt     = 0
    transport_ok = True
    warnings     = []

    partial_storage = False
    if storage:
        storage_ok, free_mt = is_storage_available(storage, qty, storage_from, storage_until)
        if not storage_ok:
            if free_mt > 0:
                # Partial — enough space for some of the crop, not all
                partial_storage = True
                storage_ok = True   # allow booking to proceed
                warnings.append(
                    f"Storage only has {free_mt:.1f} MT free (you need {qty} MT). "
                    f"Booking {free_mt:.1f} MT — arrange separate storage for remaining {qty - free_mt:.1f} MT."
                )
            else:
                warnings.append(f"Storage is fully booked for those dates (0 MT free). Choose different dates.")

    if transporter:
        transport_ok = not is_transport_blocked(transporter, transport_block_start, transport_block_end)
        if not transport_ok:
            warnings.append(f"Transporter is already booked between {transport_block_start} and {transport_block_end}.")

    # ── Step 6: Show booking summary ──────────────────────────────────────
    print()
    sep("═")
    print("  BOOKING SUMMARY")
    sep()
    print(f"  Farmer    : {farmer['farmer_name']}  ({farmer['phone']})")
    print(f"  Crop      : {farmer['crop']}  |  {qty} MT")
    print(f"  Harvest   : {harvest_date}")
    print()
    if storage:
        status_str = "✓ Available" if storage_ok else "✗ NOT available"
        print(f"  Storage   : {storage['facility_name']}, {storage['district']}")
        print(f"  Stored    : {storage_from}  →  {storage_until}  ({storage_days} days)")
        print(f"  Status    : {status_str}")
        if cost_est > 0:
            print(f"  Cost est. : ₹{rate}/MT/day × {qty} MT × {storage_days} days = ₹{cost_est:,.0f}")
    if transporter:
        status_str = "✓ Available" if transport_ok else "✗ NOT available"
        print(f"\n  Transport : {transporter['transporter_name']}  ({transporter['driver_name']})")
        print(f"  Blocked   : {transport_block_start}  →  {transport_block_end}")
        print(f"  Status    : {status_str}")
    if warnings:
        print()
        for w in warnings:
            print(f"  ⚠  {w}")
    sep("═")

    hard_fail = any(
        "fully booked" in w or "already booked between" in w
        for w in warnings
    )
    if hard_fail:
        print("\n  ✗ Cannot confirm — resources not available for requested dates.")
        print("  Run matcher again or try different dates.\n")
        return

    # Actual quantity being booked (may be less than full qty if partial storage)
    booked_qty = free_mt if partial_storage else qty

    # ── Step 7: Confirm ───────────────────────────────────────────────────
    print()
    confirm = input("  Confirm this booking? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("\n  Booking cancelled. Nothing was saved.\n")
        return

    # ── Step 8: Save booking ──────────────────────────────────────────────
    booking_id = "BK-" + str(uuid.uuid4())[:6].upper()
    booking = {
        "booking_id":           booking_id,
        "booked_at":            datetime.now().isoformat(),
        "status":               "confirmed",
        "farmer_id":            farmer_id,
        "farmer_name":          farmer["farmer_name"],
        "farmer_phone":         farmer["phone"],
        "crop":                 farmer["crop"],
        "quantity_mt":          booked_qty,
        "harvest_date":         str(harvest_date),
        "storage_id":           storage["id"]               if storage     else None,
        "storage_name":         storage["facility_name"]    if storage     else None,
        "storage_from":         str(storage_from)           if storage     else None,
        "storage_until":        str(storage_until)          if storage     else None,
        "storage_days":         storage_days                if storage     else None,
        "storage_cost_est":     cost_est                    if storage     else None,
        "transporter_id":       transporter["id"]           if transporter else None,
        "transporter_name":     transporter["transporter_name"] if transporter else None,
        "transport_block_start": str(transport_block_start) if transporter else None,
        "transport_block_end":   str(transport_block_end)   if transporter else None,
    }

    # Save booking
    bookings = load(BOOKINGS_FILE)
    bookings.append(booking)
    save_json(BOOKINGS_FILE, bookings)

    # Update farmer status → booked
    for f in farmers:
        if f["id"] == farmer_id:
            f["status"] = "booked"
    save_json(FARMERS_FILE, farmers)

    # Subtract storage capacity (use actual free_mt if partial booking)
    if storage:
        for s in storages:
            if s["id"] == storage["id"]:
                s["available_capacity_mt"] = round(s["available_capacity_mt"] - booked_qty, 2)
                if s["available_capacity_mt"] <= 0:
                    s["status"] = "full"
        save_json(STORAGES_FILE, storages)

    # Block transporter FIRST — so rematch sees the block
    if transporter:
        for t in transporters:
            if t["id"] == transporter["id"]:
                blocks = t.get("blocked_dates", [])
                blocks.append({
                    "booking_id": booking_id,
                    "from": str(transport_block_start),
                    "until": str(transport_block_end),
                })
                t["blocked_dates"] = blocks
        save_json(TRANSPORTERS_FILE, transporters)

    # NOW rematch — files are fully updated so next farmer gets correct options
    from matcher import rematch_affected_farmers
    affected_count = rematch_affected_farmers(
        booked_storage_id=storage["id"]         if storage     else None,
        booked_transporter_id=transporter["id"] if transporter else None,
    )
    if affected_count:
        print()
        print(f"  ℹ  {affected_count} other farmer(s) re-matched to next available option.")

    # ── Done ──────────────────────────────────────────────────────────────
    print()
    sep("═")
    print(f"  ✅ Booking Confirmed!")
    print(f"  Booking ID : {booking_id}")
    print(f"  Storage    : {storage['facility_name'] if storage else 'N/A'}  ({storage_from} → {storage_until})")
    print(f"  Transport  : {transporter['transporter_name'] if transporter else 'N/A'}  (blocked {transport_block_start} → {transport_block_end})")
    if cost_est > 0:
        print(f"  Cost est.  : ₹{cost_est:,.0f}")
    print(f"\n  Save your Booking ID: {booking_id}")
    sep("═")
    print()