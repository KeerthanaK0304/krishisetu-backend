# Start of bot code

# Horticulture
# KrishiSetu Bridge Bot — FarmerFlow, ColdStorageInput, TransportInput
# Auto re-matches unmatched farmers when new storage/transport registers.
# Appends a compact harvest advisory to every farmer registration whisper.

import time
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import math
from datetime import datetime, date, timedelta
import uuid
from threading import Thread
import queue as Queue
import sys
import os
import time as _time
import os

# ── KrishiSetu imports ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matcher  import match_farmer, distance_between, rematch_affected_farmers
from districts import canonical
from advisor  import build_outlook   # for compact advisory


# ── Bridge credentials ────────────────────────────────────────────────────────
Sessionid    = ''
username     = ''
MobileNumber = ''
forumID      = 'd733e328-8fc4-4601-ac4f-691530131cc2'
TemplateID   = ''   # set after login from Admin.txt

app = Flask(__name__)
CORS(app)

# ── Data paths ────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR        = os.path.join(BASE_DIR, 'data')
DATA_FILE = os.path.join(DATA_DIR, "data.json")
MATCHES_FILE    = os.path.join(DATA_DIR, 'matches.json')
BOOKINGS_FILE   = os.path.join(DATA_DIR, 'bookings.json')
STORAGES_FILE   = os.path.join(DATA_DIR, 'cold_storages.json')
TRANSPORTS_FILE = os.path.join(DATA_DIR, 'transporters.json')
TRADERS_FILE    = os.path.join(DATA_DIR, 'traders.json')
STATUS_FILE     = os.path.join(DATA_DIR, 'status_overlay.json')   # booking/block state only
ADMIN_FILE      = os.path.join(BASE_DIR, 'Horticulture_FarmerInput_Admin.txt')

os.makedirs(DATA_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────────────────────────────────────

def load(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        raw = f.read().strip()
        return json.loads(raw) if raw else []

def save(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "users": {},
            "profiles": {},
            "activity": {},
            "bizdata": {},
            "crops": {}
        }

    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def b64decode(val):
    try:
        return base64.b64decode(val.encode()).decode('utf-8', errors='ignore').strip()
    except Exception:
        return str(val).strip()

def b64encode(text):
    return base64.b64encode(str(text).encode('utf-8')).decode('utf-8')

# ─────────────────────────────────────────────────────────────────────────────
# Status overlay — only persists booking/block state for Bridge-sourced records
# Keys are record IDs; values: {status, blocked_dates}
# ─────────────────────────────────────────────────────────────────────────────

def load_overlay():
    """Return the full status overlay dict {id: {status, blocked_dates, ...}}."""
    if not os.path.exists(STATUS_FILE):
        return {}
    with open(STATUS_FILE, 'r') as f:
        raw = f.read().strip()
        return json.loads(raw) if raw else {}

def save_overlay(overlay):
    with open(STATUS_FILE, 'w') as f:
        json.dump(overlay, f, indent=2, default=str)

def set_overlay(record_id, **kwargs):
    """Update one record's overlay fields (status, blocked_dates, etc.)."""
    overlay = load_overlay()
    entry   = overlay.get(record_id, {})
    entry.update(kwargs)
    overlay[record_id] = entry
    save_overlay(overlay)

def apply_overlay(records):
    """Merge status overlay into a list of records (in-place, returns list)."""
    overlay = load_overlay()
    for rec in records:
        if rec['id'] in overlay:
            ov = overlay[rec['id']]
            rec['status']        = ov.get('status',        rec.get('status', 'available'))
            rec['blocked_dates'] = ov.get('blocked_dates', rec.get('blocked_dates', []))
            # Capacity may have been reduced by bookings
            if 'available_capacity_mt' in ov:
                rec['available_capacity_mt'] = ov['available_capacity_mt']
    return records

def get_overlay_by_type(entity_type):
    """Return list of (id, overlay_dict) for a given entity_type."""
    overlay = load_overlay()
    return [
        (rid, data) for rid, data in overlay.items()
        if data.get('entity_type') == entity_type
    ]

def get_field(flow_payload, index):
    for key, val in flow_payload.items():
        if key.endswith(f'_{index}'):
            return b64decode(val)
    return ''

# ─────────────────────────────────────────────────────────────────────────────
# Compact harvest advisory (Bridge-friendly, no tables/box-drawing)
# ─────────────────────────────────────────────────────────────────────────────

def build_compact_advisory(farmer):
    """
    Storage/transport window advisory only.
    Market signal + trader demand is already shown in build_trader_demand_section above.
    This section answers: IF farmer chooses STORE, what's available and what does it cost?
    """
    try:
        storages     = load_from_bridge('storages')
        transporters = load_from_bridge('transporters')
        bookings     = load(BOOKINGS_FILE)
        all_farmers  = load_from_bridge('farmers')

        outlook = build_outlook(farmer, storages, transporters, bookings, all_farmers)
        if not outlook:
            return ''

        harvest_date = date.fromisoformat(str(farmer['harvest_date']))
        lines = ['', '--- If You Choose STORE ---']

        current_day = next((d for d in outlook if d['date'] == harvest_date), None)
        if current_day:
            s_ok = current_day['storage_count'] > 0
            t_ok = current_day['transport_count'] > 0
            cap  = current_day['total_truck_cap']
            qty  = farmer['quantity_mt']

            status = '✓' if s_ok else '✗'
            lines.append(f"Storage on harvest date  : {status} {'available' if s_ok else 'none found'}")
            status = '✓' if t_ok else '✗'
            lines.append(f"Transport on harvest date: {status} {'available' if t_ok else 'none found'}")
            if t_ok and cap < qty:
                lines.append(f"  ⚠ Truck capacity {cap:.0f} MT < your {qty:.0f} MT. May need extra trips.")
            if current_day['competing_mt'] > 0:
                lines.append(f"  ⚠ {current_day['competing_mt']:.0f} MT competing {farmer['crop']} supply same day.")

        # Best storage cost estimate
        viable = [d for d in outlook if d['storage_count'] > 0 and d['storage_options']]
        if viable:
            cheapest_day = min(viable, key=lambda d: min(s['rate'] for s in d['storage_options']))
            cheapest     = min(cheapest_day['storage_options'], key=lambda s: s['rate'])
            rate = cheapest['rate']
            qty  = farmer['quantity_mt']
            if rate > 0:
                lines.append(f"Cheapest storage         : {cheapest['name']} @ Rs.{rate}/MT/day")
                lines.append(f"  7d=Rs.{rate*qty*7:,.0f}  14d=Rs.{rate*qty*14:,.0f}  30d=Rs.{rate*qty*30:,.0f}")

        return '\n'.join(lines)
    except Exception as e:
        print('Advisory error:', e)
        return ''


# ─────────────────────────────────────────────────────────────────────────────
# Re-match unmatched farmers (called after new storage/transport registers)
# ─────────────────────────────────────────────────────────────────────────────

def rematch_unmatched_farmers(new_resource_type=None, new_resource_id=None):
    """
    After a new storage or transporter registers, loop all unmatched/partial
    farmers and try to find them a match. Updates matches.json and farmer status.

    new_resource_type: 'storage' | 'transporter' | None
    new_resource_id:   the ID of the newly registered resource (e.g. 'dc798812')

    A farmer is counted as 'helped by your registration' ONLY if:
      - Their new match uses the specific new_resource_id, AND
      - They didn't have that type of resource matched before.

    This prevents crediting the new registration for matches made via pre-existing
    resources that happened to run during the same rematch sweep.

    Returns count of farmers specifically helped by this new resource.
    """
    farmers      = load_from_bridge('farmers')
    storages     = [s for s in load_from_bridge('storages')   if s.get('status') != 'full']
    transporters = [t for t in load_from_bridge('transporters') if t.get('status') != 'booked']
    matches      = load(MATCHES_FILE)

    # Include 'unmatched' AND farmers with partial matches (they may benefit from new resource)
    candidates = [f for f in farmers if f.get('status') not in ('booked',)]
    newly_helped = 0
    any_changed = False

    for farmer in candidates:
        # Find prior match record for this farmer
        existing_idx = next(
            (i for i, m in enumerate(matches) if m.get('farmer_id') == farmer['id']),
            None
        )
        prior_match = matches[existing_idx] if existing_idx is not None else None
        prior_had_storage     = bool(prior_match and prior_match.get('storage_id'))
        prior_had_transporter = bool(prior_match and prior_match.get('transporter_id'))

        storage, sd, ss, transporter, td, ts, _ = match_farmer(farmer, storages, transporters)
        new_quality = ('full' if storage and transporter else
                       'partial' if storage or transporter else 'none')

        # Skip if still no match at all
        if new_quality == 'none':
            # Update existing record to reflect still-unmatched (keep status unmatched)
            if prior_match:
                prior_match['matched_at']    = datetime.now().isoformat()
                prior_match['match_quality'] = 'none'
                prior_match['source']        = 'bridge_rematch'
                any_changed = True
            continue

        match_record = {
            'matched_at':          datetime.now().isoformat(),
            'farmer_id':           farmer['id'],
            'farmer_name':         farmer['farmer_name'],
            'crop':                farmer['crop'],
            'quantity_mt':         farmer['quantity_mt'],
            'harvest_date':        farmer['harvest_date'],
            'storage_id':          storage['id']            if storage     else None,
            'storage_name':        storage['facility_name'] if storage     else None,
            'storage_dist_km':     ('Same district' if ss else round(sd, 1)) if sd is not None else None,
            'transporter_id':      transporter['id']               if transporter else None,
            'transporter_name':    transporter['transporter_name'] if transporter else None,
            'transporter_dist_km': ('Same district' if ts else round(td, 1)) if td is not None else None,
            'match_quality':       new_quality,
            'source':              'bridge_rematch',
        }
        if existing_idx is not None:
            matches[existing_idx] = match_record
        else:
            matches.append(match_record)

        # Update farmer status in overlay
        set_overlay(farmer['id'], status='matched')
        any_changed = True

        # Count any farmer whose best match now uses the newly registered resource,
        # regardless of whether they had a different match before.
        if new_resource_type == 'storage' and new_resource_id:
            if storage and storage['id'] == new_resource_id:
                newly_helped += 1
        elif new_resource_type == 'transporter' and new_resource_id:
            if transporter and transporter['id'] == new_resource_id:
                newly_helped += 1
        elif new_resource_type == 'storage':
            if storage and not prior_had_storage:
                newly_helped += 1
        elif new_resource_type == 'transporter':
            if transporter and not prior_had_transporter:
                newly_helped += 1
        else:
            # Generic call — count any farmer who went from no-match to some-match
            if not prior_had_storage and not prior_had_transporter:
                newly_helped += 1

    if any_changed:
        save(MATCHES_FILE, matches)
        print(f'Re-match: {newly_helped} farmer(s) newly helped by this resource registration.')

    return newly_helped

# ─────────────────────────────────────────────────────────────────────────────
# ── FARMER FLOW ──────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def save_farmer_and_match(farmer_rec):
    # Farmer record lives in Bridge — persist status + absolute harvest_date
    set_overlay(farmer_rec['id'], status='unmatched', harvest_date=farmer_rec['harvest_date'])

    storages     = [s for s in load_from_bridge('storages')   if s.get('status') != 'full']
    transporters = [t for t in load_from_bridge('transporters') if t.get('status') != 'booked']

    storage, sd, ss, transporter, td, ts, warnings = match_farmer(farmer_rec, storages, transporters)

    matches = load(MATCHES_FILE)
    matches.append({
        'matched_at':          datetime.now().isoformat(),
        'farmer_id':           farmer_rec['id'],
        'farmer_name':         farmer_rec['farmer_name'],
        'crop':                farmer_rec['crop'],
        'quantity_mt':         farmer_rec['quantity_mt'],
        'harvest_date':        farmer_rec['harvest_date'],
        'storage_id':          storage['id']            if storage     else None,
        'storage_name':        storage['facility_name'] if storage     else None,
        'storage_dist_km':     ('Same district' if ss else round(sd, 1)) if sd is not None else None,
        'transporter_id':      transporter['id']               if transporter else None,
        'transporter_name':    transporter['transporter_name'] if transporter else None,
        'transporter_dist_km': ('Same district' if ts else round(td, 1)) if td is not None else None,
        'match_quality':       ('full'    if storage and transporter else
                                'partial' if storage or  transporter else 'none'),
        'source': 'bridge',
    })
    save(MATCHES_FILE, matches)
    return storage, sd, ss, transporter, td, ts, warnings

def fmt_dist(d, same):
    if same:       return 'Same district'
    if d is None:  return 'dist unknown'
    return f'{d:.0f} km'

def build_trader_demand_section(farmer):
    """
    Returns a combined market + trader demand section.
    Shows: current price, signal, AND whether live traders are ready to buy.
    The two together form the real recommendation.
    """
    try:
        from lot_matcher  import crop_matches, district_matches
        from trade_signal import compute_signal
        from market_feed  import TARGET_MANDIS, refresh_prices

        crop     = farmer.get('crop', '')
        district = farmer.get('district', '')
        qty      = farmer.get('quantity_mt', 0)

        # ── Trader demand ─────────────────────────────────────────────────
        traders = load_from_bridge('traders')
        matching_traders = [
            t for t in (traders or [])
            if t.get('status') == 'active'
            and crop_matches(crop, t.get('crops', []))
            and district_matches(district, t.get('buy_districts', []))
        ]

        # ── Market signal ─────────────────────────────────────────────────
        refresh_prices(use_mock=True)
        mandis_for_crop = TARGET_MANDIS.get(crop, [])
        target_mandi    = mandis_for_crop[0] if mandis_for_crop else district
        all_farmers     = load_from_bridge('farmers')
        bookings        = load(BOOKINGS_FILE)
        sig             = compute_signal(farmer, all_farmers, bookings, target_mandi=target_mandi)

        today_price = sig.get('today_price_qt')
        signal      = sig.get('signal', '')
        best_price  = sig.get('best_price_qt')
        confidence  = sig.get('confidence', 'low')

        lines = ['', '--- Market & Trader Demand ---']

        # Price line
        if today_price:
            lines.append(f"Mandi ({target_mandi}) price now : Rs.{today_price}/qt  [{confidence} confidence]")
            if best_price and signal != 'SELL_NOW':
                hold_days = signal.split('_')[1] if '_' in signal else '?'
                lines.append(f"Forecast in {hold_days} days       : Rs.{best_price}/qt")
        else:
            lines.append(f"No mandi price data for {crop} yet (mock data may not cover this crop).")

        # Trader demand line
        if matching_traders:
            names = ', '.join(t['company_name'] for t in matching_traders[:3])
            if len(matching_traders) > 3:
                names += f" +{len(matching_traders)-3} more"
            lines.append(f"Traders ready to buy  : {len(matching_traders)} active  ({names})")
        else:
            lines.append(f"Traders ready to buy  : None registered yet for {crop} in {district}")

        # For HOLD signal, filter traders available on the projected sell date
        hold_sell_traders = matching_traders  # default: all (used for SELL_NOW)
        if signal and signal.startswith('HOLD'):
            hold_days_n = int(signal.split('_')[1]) if '_' in signal else 0
            try:
                from datetime import date as _date, timedelta as _td
                _harvest_date_str = str(farmer.get('harvest_date', ''))
                _sell_date = _date.fromisoformat(_harvest_date_str) + _td(days=hold_days_n)
                def _is_trader_free(t, on_date):
                    for blk in t.get('blocked_dates', []):
                        try:
                            if _date.fromisoformat(blk['from']) <= on_date <= _date.fromisoformat(blk['until']):
                                return False
                        except Exception:
                            pass
                    return True
                hold_sell_traders = [
                    t for t in matching_traders
                    if _is_trader_free(t, _sell_date)
                ]
            except Exception:
                hold_sell_traders = matching_traders

        # ── Combined recommendation ───────────────────────────────────────
        lines.append('')
        if signal == 'SELL_NOW' and matching_traders:
            lines.append(f"✅ SELL NOW — Price is good (Rs.{today_price}/qt) AND {len(matching_traders)} trader(s) are ready.")
            lines.append(f"   Use the Booking flow → choose SELL to alert them immediately.")
        elif signal == 'SELL_NOW' and not matching_traders:
            lines.append(f"📈 Price is good (Rs.{today_price}/qt) but no traders registered yet.")
            lines.append(f"   You can still sell at mandi directly, or wait for traders to register.")
        elif signal and signal.startswith('HOLD') and hold_sell_traders:
            hold_days = signal.split('_')[1]
            gain = (best_price - today_price) * qty * 10 if best_price and today_price else 0
            lines.append(f"⏳ HOLD {hold_days} days — price likely rising to Rs.{best_price}/qt.")
            if gain > 0:
                lines.append(f"   Potential gain by waiting: Rs.{gain:,.0f} (before storage cost).")
            lines.append(f"   {len(hold_sell_traders)} trader(s) available on sell date will be alerted when storage period ends.")
            lines.append(f"   Use the Booking flow → choose STORE.")
        elif signal and signal.startswith('HOLD') and not hold_sell_traders:
            hold_days = signal.split('_')[1]
            lines.append(f"⏳ HOLD {hold_days} days — price likely rising. No traders available on sell date yet, but book storage now.")
            lines.append(f"   Use the Booking flow → choose STORE.")
        else:
            lines.append(f"ℹ No strong signal yet. Check back closer to harvest.")

        return '\n'.join(lines)
    except Exception as e:
        print('build_trader_demand_section error:', e)
        return ''

def build_farmer_whisper(farmer, storage, sd, ss, transporter, td, ts):
    lines = [
        '✅ Farmer Registered Successfully!',
        f"ID: {farmer['id']}",
        f"Name: {farmer['farmer_name']}  |  Phone: {farmer['phone']}",
        f"Location: {farmer['village']}, {farmer['district']}",
        f"Crop: {farmer['crop']}  |  Qty: {farmer['quantity_mt']} MT",
        f"Harvest date: {farmer['harvest_date']}  ({farmer['days_until_ready']} days away)",
        '',
    ]
    if storage:
        rate = storage['rate_per_mt_per_day']
        qty  = farmer['quantity_mt']
        est  = rate * qty * 30 if rate > 0 else 0
        cap  = storage['available_capacity_mt']
        lines += [
            f"COLD STORAGE MATCH ({fmt_dist(sd, ss)})",
            f"  Facility : {storage['facility_name']}",
            f"  Address  : {storage['address']}, {storage['district']}",
            f"  Contact  : {storage['operator_name']}  {storage['phone']}",
            f"  Available: {cap} MT  [{'OK — enough for your lot' if cap >= qty else f'Partial fit — only {cap} MT free for your {qty} MT'}]",
            f"  Rate     : Rs.{rate}/MT/day" + (f"  (~Rs.{est:,.0f} for 30 days)" if est > 0 else "  (Negotiable)"),
            f"  Period   : {storage['available_from']} to {storage['available_until']}",
            '',
        ]
    else:
        lines += ['No cold storage found nearby for this crop and dates.', '']

    if transporter:
        lines += [
            f"TRANSPORT MATCH ({fmt_dist(td, ts)} from farm)",
            f"  Name     : {transporter['transporter_name']}  ({transporter['driver_name']})",
            f"  Phone    : {transporter['phone']}",
            f"  Vehicle  : {transporter['vehicle_type']}  |  {transporter['capacity_mt']} MT" +
            ('  [Refrigerated]' if transporter['is_refrigerated'] else ''),
            f"  Base     : {transporter['base_district']}",
            f"  Rate     : Rs.{transporter['rate_per_mt_per_km']}/MT/km",
            '',
        ]
    else:
        lines += ['No transporter found for this area and dates.', '']

    if farmer.get('preferred_storage_area'):
        lines.append(f"Preferred area noted: {farmer['preferred_storage_area']}")
    if farmer.get('notes'):
        lines.append(f"Notes: {farmer['notes']}")
    lines.append(f"Save your Farmer ID: {farmer['id']}  (needed to confirm booking)")

    # Append trader demand info
    trader_section = build_trader_demand_section(farmer)
    if trader_section:
        lines.append(trader_section)

    # Append compact advisory
    advisory = build_compact_advisory(farmer)
    if advisory:
        lines.append(advisory)

    return '\n'.join(lines)

@app.route("/saveUserData", methods=["POST"])
def save_user_data():

    body = request.get_json(force=True)

    print("BODY RECEIVED =", body)

    mobile = body.get("mobile")
    incoming_kind = body.get("kind")
    value = body.get("value")

    if not mobile:
        return jsonify({
            "error": "mobile missing",
            "body": body
        }), 400

    # React sends "profile" but data.json uses "profiles"
    kind_map = {
        "profile": "profiles",
        "activity": "activity",
        "crops": "crops",
        "bizdata": "bizdata"
    }

    kind = kind_map.get(incoming_kind)

    if not kind:
        return jsonify({
            "error": f"invalid kind: {incoming_kind}"
        }), 400

    data = load_data()

    print("KIND =", kind)
    print("MOBILE =", mobile)

    if kind not in data:
        data[kind] = {}
    print("BEFORE SAVE =", data.get(kind))
    data[kind][mobile] = value
    print("AFTER SAVE =", data.get(kind))
    print("KIND =", kind)
    print("MOBILE =", mobile)
    print("VALUE =", value)
    save_data(data)
    print("AFTER SAVE =", data.get(kind))
    return jsonify({
        "success": True
    })

@app.route("/loadUserData/<mobile>")
def load_user_data(mobile):

    data = load_data()

    if "storageBookings" not in data:
        data["storageBookings"] = {}

    return jsonify({
        "crops": data.get("crops", {}).get(mobile, []),
        "activity": data.get("activity", {}).get(mobile, []),
        "profile": data.get("profiles", {}).get(mobile, {}),
        "bizData": data.get("bizdata", {}).get(mobile, {}),
        "storageBookings": data.get("storageBookings", {}).get(mobile, [])
    })

@app.route("/saveUsers", methods=["POST"])
def save_users():

    users = request.json

    data = load_data()
    data["users"] = users

    save_data(data)

    return jsonify({"success": True})


@app.route("/loadUsers")
def load_users():

    data = load_data()

    return jsonify(data["users"])
    
@app.route("/saveTransportBookings", methods=["POST"])
def save_transport_bookings():

    bookings = request.json

    data = load_data()

    data["transportBookings"] = bookings

    save_data(data)

    return jsonify({"success": True})


@app.route("/loadTransportBookings")
def load_transport_bookings():

    data = load_data()

    return jsonify(
        data.get("transportBookings", [])
    )

def process_account_input_flow(flow_payload, current_bridge_id=''):
    def f(i): return get_field(flow_payload, i)        # decoded — for text fields
    def f_raw(i):                                       # raw base64 — for passHash
        for key, val in flow_payload.items():
            if key.endswith(f'_{i}'):
                return val
        return ''

    mobile       = f(7).strip()
    pass_hash    = f_raw(8)
    name         = f(9).strip()
    district     = f(10).strip()
    role         = f(11).strip()
    active_roles = f(12).strip()

    if not mobile or not pass_hash:
        return "Account registration failed: mobile or password missing."

    data = load_data()
    if "users" not in data:
        data["users"] = {}

    data["users"][mobile] = {
        "passHash": pass_hash,
        "name": name,
        "district": district,
        "role": role,
        "activeRoles": active_roles,
        "registeredAt": datetime.now().isoformat()
    }
    save_data(data)
    return f"✅ Account registered for {name} ({mobile})"

def process_farmer_flow(flow_payload, current_bridge_id=''):
    def f(i): return get_field(flow_payload, i)

    confirm_val = f(25).strip().lower()
    if confirm_val in ('cancel', 'no', 'n'):
        return f"Registration cancelled for {f(11) or 'Farmer'}. Nothing was saved."

    name     = f(11).strip()
    phone    = f(12).strip()
    district = f(13).strip()
    village  = f(22).strip()
    crop     = f(15).strip()
    qty_s    = f(16).strip()
    days_s   = f(17).strip()

    errors = []
    if not name:   errors.append('Name is required.')
    if not phone or not phone.isdigit() or len(phone) < 10:
        errors.append('Phone number must be at least 10 digits.')
    if not district: errors.append('District is required.')
    elif canonical(district) is None:
        errors.append(f"District '{district}' not recognised. Please check spelling.")
    if not village: errors.append('Village/Taluk is required.')
    if not crop:    errors.append('Crop name is required.')

    qty, days = None, None
    if not qty_s: errors.append('Harvest Quantity is required.')
    else:
        try:
            qty = float(qty_s)
            if qty <= 0:      errors.append('Harvest Quantity must be > 0.')
            elif qty > 10000: errors.append('Harvest Quantity max is 10,000 MT.')
        except ValueError:    errors.append('Harvest Quantity must be a number.')

    if not days_s: errors.append('Days till harvest is required.')
    else:
        try:
            days = int(days_s)
            if days < 0:    errors.append('Days till harvest cannot be negative.')
            elif days > 180: errors.append('Days till harvest max is 180.')
        except ValueError:  errors.append('Days till harvest must be a whole number.')

    if errors:
        return 'Please fix the following before submitting:\n\n' + '\n'.join(f'- {e}' for e in errors)

    harvest_date = date.today() + timedelta(days=days)
    # Use BridgeID as farmer ID so it matches what parse_farmer_rows reads back
    farmer_id = current_bridge_id[:8] if current_bridge_id else str(uuid.uuid4())[:8]
    farmer_rec = {
        'id':                    farmer_id,
        'registered_at':         datetime.now().isoformat(),
        'farmer_name':           name,
        'phone':                 phone,
        'district':              district,
        'village':               village,
        'crop':                  crop,
        'quantity_mt':           qty,
        'days_until_ready':      days,
        'harvest_date':          str(harvest_date),
        'preferred_storage_area': f(23) or None,
        'notes':                 f(24) or None,
        'status':                'unmatched',
        'source':                'bridge',
    }

    invalidate_bridge_cache('farmers')
    storage, sd, ss, transporter, td, ts, _ = save_farmer_and_match(farmer_rec)

    if storage or transporter:
        set_overlay(farmer_rec['id'], entity_type='farmer', status='matched', harvest_date=farmer_rec['harvest_date'])
        farmer_rec['status'] = 'matched'

    whisper = build_farmer_whisper(farmer_rec, storage, sd, ss, transporter, td, ts)

    # Bug 7: Notify matching traders that a new farmer has registered and will
    # be ready to sell — traders should know supply is coming so they can plan.
    try:
        from lot_matcher import crop_matches, district_matches, build_trader_alert
        from trade_signal import compute_signal
        all_traders_now = load_from_bridge('traders')
        all_farmers_now = load_from_bridge('farmers')
        bookings_now    = load(BOOKINGS_FILE)
        sig_now         = compute_signal(farmer_rec, all_farmers_now, bookings_now)

        crop_     = farmer_rec.get('crop', '')
        district_ = farmer_rec.get('district', '')

        matching_now = [
            t for t in (all_traders_now or [])
            if t.get('status') == 'active'
            and crop_matches(crop_, t.get('crops', []))
            and district_matches(district_, t.get('buy_districts', []))
        ]

        # Estimate sell-available date: harvest + signal hold days (or just harvest if SELL_NOW)
        signal_str   = sig_now.get('signal', '')
        hold_days    = int(signal_str.split('_')[1]) if signal_str.startswith('HOLD') else 0
        harvest_dt   = date.fromisoformat(str(farmer_rec['harvest_date']))
        avail_date   = harvest_dt + timedelta(days=hold_days)
        avail_label  = (f"{avail_date}  (harvest {farmer_rec['harvest_date']} + {hold_days}d storage)"
                        if hold_days else f"{farmer_rec['harvest_date']}  (available at harvest)")

        reg_alert_lines = [
            '🌱 KrishiSetu — Incoming Supply Alert',
            '',
            f"Crop          : {farmer_rec['crop']}",
            f"Quantity      : {farmer_rec['quantity_mt']} MT",
            f"Available from: {avail_label}",
            f"Location      : {farmer_rec.get('village','')}, {farmer_rec['district']}",
            f"Farmer        : {farmer_rec['farmer_name']}",
            f"Phone         : {farmer_rec['phone']}",
        ]
        if sig_now.get('today_price_qt'):
            reg_alert_lines.append(f"Mandi price now: Rs.{sig_now['today_price_qt']}/qt  ({sig_now.get('mandi','')})")
        reg_alert_lines += [
            '',
            'Contact the farmer directly on the number above.',
            'They will also be matched to you automatically when they confirm booking.',
        ]
        reg_alert = '\n'.join(reg_alert_lines)

        for trader in matching_now:
            try:
                _send_trader_whisper(trader, reg_alert)
                print(f"[reg] ✓ Trader {trader['company_name']} notified of new farmer {farmer_rec['farmer_name']}")
            except Exception as te:
                print(f"[reg] ✗ Trader notification failed for {trader['company_name']}: {te}")
    except Exception as e:
        print(f'[reg] Trader registration alert error: {e}')

    return whisper


def alert_matching_traders_now(farmer_rec, signal):
    """
    Called immediately at farmer registration when signal is SELL_NOW.
    Finds matching traders and sends them a whisper right away — don't wait
    for the 6-hour background loop.
    """
    try:
        from lot_matcher import match_sell_now_lots, build_trader_alert
        traders = load_from_bridge('traders')
        if not traders:
            return

        sell_now_list = [(farmer_rec, signal)]
        matched = match_sell_now_lots(sell_now_list, traders)

        for farmer, sig, matching_traders in matched:
            for trader in matching_traders:
                alert = build_trader_alert(farmer, sig, trader)
                print(f"[alert_now] Sending to {trader['company_name']} ({trader['phone']})")
                try:
                    _send_trader_whisper(trader, alert)
                    print(f"[alert_now] ✓ Alert sent to {trader['company_name']}")
                except Exception as e:
                    print(f"[alert_now] ✗ Failed for {trader['company_name']}: {e}")
    except Exception as e:
        print(f'[alert_now] Error: {e}')

# ─────────────────────────────────────────────────────────────────────────────
# ── COLD STORAGE FLOW ────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def process_cold_storage_flow(flow_payload, current_bridge_id=''):
    def f(i): return get_field(flow_payload, i)

    confirm_val = f(26).strip().lower()
    if confirm_val in ('cancel', 'no', 'n'):
        return f"Registration cancelled for {f(14) or 'facility'}. Nothing was saved."

    facility = f(14).strip()
    operator = f(15).strip()
    phone    = f(16).strip()
    district = f(17).strip()
    address  = f(18).strip()
    cap_s    = f(19).strip()
    from_s   = f(20).strip()
    dur_s    = f(21).strip()
    crops_s  = f(22).strip()
    rate_s   = f(23).strip()
    minq_s   = f(24).strip()
    notes    = f(25).strip()

    errors = []
    if not facility: errors.append('Facility name is required.')
    if not operator: errors.append('Operator name is required.')
    if not phone or not phone.isdigit() or len(phone) < 10:
        errors.append('Phone number must be at least 10 digits.')
    if not district: errors.append('District is required.')
    elif canonical(district) is None:
        errors.append(f"District '{district}' not recognised.")
    if not address:  errors.append('Address is required.')
    if not crops_s:  errors.append('Supported crops is required (or type All).')

    cap, from_days, duration, rate, min_qty = None, None, None, None, None

    if not cap_s: errors.append('Available capacity is required.')
    else:
        try:
            cap = float(cap_s)
            if cap <= 0:      errors.append('Capacity must be > 0.')
            elif cap > 50000: errors.append('Capacity max is 50,000 MT.')
        except ValueError:    errors.append('Capacity must be a number.')

    if not from_s: errors.append('Available from (days) is required.')
    else:
        try:
            from_days = int(from_s)
            if from_days < 0:    errors.append('Available from cannot be negative.')
            elif from_days > 365: errors.append('Available from max is 365 days.')
        except ValueError:       errors.append('Available from must be a whole number.')

    if not dur_s: errors.append('Storage duration is required.')
    else:
        try:
            duration = int(dur_s)
            if duration <= 0:    errors.append('Duration must be at least 1 day.')
            elif duration > 365: errors.append('Duration max is 365 days.')
        except ValueError:       errors.append('Duration must be a whole number.')

    if not rate_s: errors.append('Rate is required (enter 0 if negotiable).')
    else:
        try:
            rate = float(rate_s)
            if rate < 0: errors.append('Rate cannot be negative.')
        except ValueError: errors.append('Rate must be a number.')

    if minq_s:
        try:
            min_qty = float(minq_s)
            if min_qty < 0: errors.append('Min quantity cannot be negative.')
        except ValueError:  errors.append('Min quantity must be a number.')

    if errors:
        return 'Please fix the following before submitting:\n\n' + '\n'.join(f'- {e}' for e in errors)

    supported_crops = ['All'] if crops_s.strip().lower() == 'all' else \
                      [c.strip().title() for c in crops_s.split(',')]
    available_from  = date.today() + timedelta(days=from_days)
    available_until = available_from + timedelta(days=duration)

    storage_id = current_bridge_id[:8] if current_bridge_id else str(uuid.uuid4())[:8]
    record = {
        'id':                    storage_id,
        'registered_at':         datetime.now().isoformat(),
        'facility_name':         facility,
        'operator_name':         operator,
        'phone':                 phone,
        'district':              district,
        'address':               address,
        'available_capacity_mt': cap,
        'available_from':        str(available_from),
        'available_until':       str(available_until),
        'supported_crops':       supported_crops,
        'rate_per_mt_per_day':   rate,
        'minimum_quantity_mt':   min_qty,
        'notes':                 notes or None,
        'status':                'available',
        'source':                'bridge',
    }
    # Storage record lives in Bridge — persist initial status overlay WITH capacity
    set_overlay(record['id'],
        entity_type           = 'storage',
        status                = 'available',
        available_capacity_mt = cap,
    )

    # Re-match farmers who lacked storage — pass resource type+ID for accurate count
    newly_matched = rematch_unmatched_farmers(new_resource_type='storage', new_resource_id=record['id'])

    est = rate * cap * 30 if rate > 0 else 0
    lines = [
        '✅ Cold Storage Registered Successfully!',
        f"ID: {record['id']}",
        f"Facility : {facility}  ({operator}, {phone})",
        f"Location : {address}, {district}",
        f"Capacity : {cap} MT",
        f"Available: {available_from} to {available_until}",
        f"Crops    : {', '.join(supported_crops)}",
        f"Rate     : Rs.{rate}/MT/day" + (f"  (~Rs.{est:,.0f} for full slot, 30d)" if est > 0 else "  (Negotiable)"),
    ]
    if min_qty:
        lines.append(f"Min booking: {min_qty} MT")
    if notes:
        lines.append(f"Notes    : {notes}")
    lines.append(f"\nSave your Storage ID: {record['id']}")
    if newly_matched:
        lines.append(f"\n✓ Your registration helped match {newly_matched} waiting farmer(s)!")
    return '\n'.join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# ── TRANSPORT FLOW ───────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def process_transport_flow(flow_payload, current_bridge_id=''):
    def f(i): return get_field(flow_payload, i)

    confirm_val = f(28).strip().lower()
    if confirm_val in ('cancel', 'no', 'n'):
        return f"Registration cancelled for {f(15) or 'transporter'}. Nothing was saved."

    name      = f(15).strip()
    driver    = f(16).strip()
    phone     = f(17).strip()
    district  = f(18).strip()
    vehicle   = f(19).strip()
    cap_s     = f(20).strip()
    refrig_s  = f(21).strip().lower()
    from_s    = f(22).strip()
    avdays_s  = f(23).strip()
    maxdist_s = f(24).strip()
    rate_s    = f(25).strip()
    op_dists  = f(26).strip()
    notes     = f(27).strip()

    errors = []
    if not name:  errors.append('Name/Company is required.')
    if not phone or not phone.isdigit() or len(phone) < 10:
        errors.append('Phone number must be at least 10 digits.')
    if not district: errors.append('Base district is required.')
    elif canonical(district) is None:
        errors.append(f"District '{district}' not recognised.")
    if not vehicle:  errors.append('Vehicle type is required.')
    if not op_dists: errors.append('Operating districts is required (or type All Karnataka).')

    cap, from_days, av_days, max_dist, rate = None, None, None, None, None

    if not cap_s: errors.append('Capacity (MT) is required.')
    else:
        try:
            cap = float(cap_s)
            if cap <= 0:    errors.append('Capacity must be > 0.')
            elif cap > 500: errors.append('Capacity max is 500 MT.')
        except ValueError:  errors.append('Capacity must be a number.')

    if not from_s: errors.append('Available from (days) is required.')
    else:
        try:
            from_days = int(from_s)
            if from_days < 0:   errors.append('Available from cannot be negative.')
            elif from_days > 90: errors.append('Available from max is 90 days.')
        except ValueError:      errors.append('Available from must be a whole number.')

    if not avdays_s: errors.append('Available days is required.')
    else:
        try:
            av_days = int(avdays_s)
            if av_days < 1:   errors.append('Available days must be at least 1.')
            elif av_days > 90: errors.append('Available days max is 90.')
        except ValueError:    errors.append('Available days must be a whole number.')

    if not maxdist_s: errors.append('Maximum distance is required.')
    else:
        try:
            max_dist = float(maxdist_s)
            if max_dist <= 0:     errors.append('Max distance must be > 0.')
            elif max_dist > 2000: errors.append('Max distance max is 2000 km.')
        except ValueError:        errors.append('Max distance must be a number.')

    if not rate_s: errors.append('Rate is required (enter 0 if negotiable).')
    else:
        try:
            rate = float(rate_s)
            if rate < 0: errors.append('Rate cannot be negative.')
        except ValueError: errors.append('Rate must be a number.')

    if errors:
        return 'Please fix the following before submitting:\n\n' + '\n'.join(f'- {e}' for e in errors)

    is_refrigerated   = refrig_s in ('yes', 'y')
    available_from    = date.today() + timedelta(days=from_days)
    available_until   = available_from + timedelta(days=av_days)
    op_districts_list = [d.strip().title() for d in op_dists.split(',')]

    transport_id = current_bridge_id[:8] if current_bridge_id else str(uuid.uuid4())[:8]
    record = {
        'id':                  transport_id,
        'registered_at':       datetime.now().isoformat(),
        'transporter_name':    name,
        'driver_name':         driver or name,
        'phone':               phone,
        'base_district':       district,
        'vehicle_type':        vehicle,
        'capacity_mt':         cap,
        'is_refrigerated':     is_refrigerated,
        'available_from':      str(available_from),
        'available_until':     str(available_until),
        'operating_districts': op_districts_list,
        'max_distance_km':     max_dist,
        'rate_per_mt_per_km':  rate,
        'notes':               notes or None,
        'status':              'available',
        'source':              'bridge',
    }
    # Transporter record lives in Bridge — persist initial status overlay
    set_overlay(record['id'], entity_type='transporter', status='available')
    
    # Re-match farmers who lacked a transporter — pass resource type+ID for accurate count
    newly_matched = rematch_unmatched_farmers(new_resource_type='transporter', new_resource_id=record['id'])

    lines = [
        '✅ Transporter Registered Successfully!',
        f"ID: {record['id']}",
        f"Name    : {name}" + (f"  (Driver: {driver})" if driver and driver != name else ''),
        f"Phone   : {phone}",
        f"Base    : {district}",
        f"Vehicle : {vehicle}  |  {cap} MT" + ('  [Refrigerated]' if is_refrigerated else ''),
        f"Available: {available_from} to {available_until}",
        f"Area    : {', '.join(op_districts_list)}",
        f"Max dist: {max_dist} km",
        f"Rate    : Rs.{rate}/MT/km" if rate > 0 else "Rate    : Negotiable",
    ]
    if notes:
        lines.append(f"Notes   : {notes}")
    lines.append(f"\nSave your Transport ID: {record['id']}")
    if newly_matched:
        lines.append(f"\n✓ Your registration helped match {newly_matched} waiting farmer(s)!")
    return '\n'.join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# ── TRADER FLOW ──────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def process_trader_flow(flow_payload, current_bridge_id=''):
    def f(i): return get_field(flow_payload, i)

    confirm_val = f(12).strip().lower()
    if confirm_val in ('cancel', 'no', 'n'):
        return f"Registration cancelled for {f(7) or 'trader'}. Nothing was saved."

    company  = f(7).strip()
    phone    = f(8).strip()
    district = f(9).strip()
    crops_s  = f(10).strip()
    dists_s  = f(11).strip()

    errors = []
    if not company:
        errors.append('Trader / company name is required.')
    if not phone or not phone.isdigit() or len(phone) < 10:
        errors.append('Phone number must be at least 10 digits.')
    if not district:
        errors.append('Base district is required.')
    elif canonical(district) is None:
        errors.append(f"District '{district}' not recognised. Please check spelling.")
    if not crops_s:
        errors.append('Crops you trade is required (or type All).')
    if not dists_s:
        errors.append('Districts you buy from is required (or type All Karnataka).')

    if errors:
        return 'Please fix the following:\n\n' + '\n'.join(f'- {e}' for e in errors)

    crops_list = ['All'] if crops_s.strip().lower() == 'all' else \
                 [c.strip().title() for c in crops_s.split(',') if c.strip()]
    dists_list = ['All Karnataka'] if 'all' in dists_s.lower() else \
                 [d.strip().title() for d in dists_s.split(',') if d.strip()]

    trader_id = current_bridge_id[:8] if current_bridge_id else str(uuid.uuid4())[:8]
    record = {
        'id':            trader_id,
        'registered_at': datetime.now().isoformat(),
        'company_name':  company,
        'phone':         phone,
        'base_district': district,
        'crops':         crops_list,
        'buy_districts': dists_list,
        'status':        'active',
        'source':        'bridge',
    }

    set_overlay(trader_id,
        entity_type    = 'trader',
        status         = 'active',
        crops          = crops_list,
        buy_districts  = dists_list,
    )

    lines = [
        '✅ Trader Registered Successfully!',
        f"ID       : {trader_id}",
        f"Company  : {company}  ({phone})",
        f"Base     : {district}",
        f"Crops    : {', '.join(crops_list)}",
        f"Buy from : {', '.join(dists_list)}",
        '',
        f"Save your Trader ID: {trader_id}",
        "You will receive alerts when matching lots are ready to sell.",
    ]
    return '\n'.join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# ── BOOKING FLOW (Bridge) ─────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def process_booking_flow(flow_payload, current_bridge_id=''):
    """
    Booking flow — farmer chooses what to do after seeing the advisory.

    Bridge form fields (FarmerInput_Booking_Main-049205e6-…):
      2  — Farmer ID
      5  — Choice: SELL or STORE
      6  — Storage Days (only needed if STORE)
      8  — Confirm/Cancel

    SELL path: mark farmer as sell-intent, alert matching traders immediately.
    STORE path: proceed with cold storage + transport booking as before.
    """
    def f(i): return get_field(flow_payload, i)

    farmer_id    = f(2).strip()
    choice       = f(5).strip().upper()   # 'SELL' or 'STORE'
    confirm_val  = f(8).strip().lower()

    if confirm_val in ('cancel', 'no', 'n', ''):
        return "Booking cancelled. Nothing was saved."

    if not farmer_id:
        return "✗ Farmer ID is required."

    if choice not in ('SELL', 'STORE'):
        return ("✗ Please enter SELL or STORE in the 'I want to' field.\n"
                "  SELL — connect with traders and sell at harvest.\n"
                "  STORE — book cold storage and wait for better price.")

    # ── Load data ──────────────────────────────────────────────────────────
    farmers      = load_from_bridge('farmers')
    storages     = load_from_bridge('storages')
    transporters = load_from_bridge('transporters')
    matches      = load(MATCHES_FILE)
    bookings     = load(BOOKINGS_FILE)

    farmer = next((f_ for f_ in farmers if f_['id'] == farmer_id), None)
    if not farmer:
        return f"✗ Farmer ID '{farmer_id}' not found. Register first."

    if farmer.get('status') == 'booked':
        return f"✗ {farmer['farmer_name']} already has a confirmed booking."

    # ══════════════════════════════════════════════════════════════════════
    # PATH A — SELL NOW
    # ══════════════════════════════════════════════════════════════════════
    if choice == 'SELL':
        # Mark farmer as sell-intent in overlay
        set_overlay(farmer_id,
            entity_type  = 'farmer',
            status       = 'sell_intent',
            harvest_date = farmer['harvest_date'],
        )

        # Compute signal for alert content
        try:
            from trade_signal import compute_signal
            from market_feed  import TARGET_MANDIS
            from lot_matcher  import match_sell_now_lots, build_trader_alert

            sig = compute_signal(farmer, farmers, bookings)

            # Alert matching traders immediately
            all_traders = load_from_bridge('traders')
            sell_now_list = [(farmer, sig)]
            matched = match_sell_now_lots(sell_now_list, all_traders)

            alert_count = 0
            for _f, _s, traders_list in matched:
                for trader in traders_list:
                    alert = build_trader_alert(_f, _s, trader)
                    try:
                        _send_trader_whisper(trader, alert)
                        alert_count += 1
                        print(f"[booking/sell] ✓ Alert sent to {trader['company_name']}")
                    except Exception as ae:
                        print(f"[booking/sell] ✗ {trader['company_name']}: {ae}")

            today_price = sig.get('today_price_qt')
            mandi       = sig.get('mandi', farmer['district'])

            lines = [
                '✅ Sell Intent Confirmed!',
                f"Farmer  : {farmer['farmer_name']}  ({farmer['phone']})",
                f"Crop    : {farmer['crop']}  |  {farmer['quantity_mt']} MT",
                f"Harvest : {farmer['harvest_date']}",
                '',
            ]
            if today_price:
                lines.append(f"Mandi price ({mandi}): Rs.{today_price}/qt")
            if alert_count:
                lines.append(f"✓ {alert_count} trader(s) have been alerted about your lot.")
                lines.append("  They will contact you directly on your registered phone.")
            else:
                lines.append("⚠ No matching traders found right now.")
                lines.append("  Register more traders or check back after harvest.")
            lines.append('')
            lines.append("If no trader contacts you before harvest, use STORE option to book cold storage.")
            return '\n'.join(lines)

        except Exception as e:
            print(f'[booking/sell] error: {e}')
            return f"✗ Error processing sell intent: {e}"

    # ══════════════════════════════════════════════════════════════════════
    # PATH B — STORE
    # ══════════════════════════════════════════════════════════════════════
    # Compute optimal storage days from trade signal (for pre-fill / recommendation)
    try:
        from trade_signal import compute_signal as _compute_signal
        _sig_tmp         = _compute_signal(farmer, farmers, bookings)
        _signal_str      = _sig_tmp.get('signal', '')
        optimal_days     = int(_signal_str.split('_')[1]) if _signal_str.startswith('HOLD') else 0
    except Exception:
        optimal_days = 0

    days_raw = f(6).strip()
    if not days_raw and optimal_days > 0:
        # User left field blank — auto-fill from signal
        storage_days = optimal_days
    else:
        try:
            storage_days = int(days_raw)
            if storage_days <= 0 or storage_days > 365:
                return "✗ Storage days must be between 1 and 365."
        except ValueError:
            return "✗ Storage days must be a whole number (e.g. 14)."

    # ── Live rematch at booking time ───────────────────────────────────
    active_storages     = [s for s in storages     if s.get('status') != 'full']
    active_transporters = [t for t in transporters if t.get('status') != 'booked']

    storage, sd, ss, transporter, td, ts, _ = match_farmer(farmer, active_storages, active_transporters)

    if not storage and not transporter:
        return "✗ No storage or transport currently available for your crop and date."

    # ── Compute dates ──────────────────────────────────────────────────
    from datetime import timedelta as td_
    import math as _math
    harvest_date  = date.fromisoformat(str(farmer['harvest_date']))
    storage_from  = harvest_date
    storage_until = harvest_date + td_(days=storage_days)

    base_to_farm_km = farm_to_storage_km = storage_to_base_km = 0.0
    if transporter and storage:
        d1, _ = distance_between(transporter['base_district'], farmer['district'])
        d2, _ = distance_between(farmer['district'],           storage['district'])
        d3, _ = distance_between(storage['district'],          transporter['base_district'])
        base_to_farm_km    = d1 or 0.0
        farm_to_storage_km = d2 or 0.0
        storage_to_base_km = d3 or 0.0
    elif transporter:
        d1, _ = distance_between(transporter['base_district'], farmer['district'])
        base_to_farm_km = d1 or 0.0

    total_km    = base_to_farm_km + farm_to_storage_km + storage_to_base_km
    travel_days = max(1, _math.ceil(total_km / 300))
    t_block_start = harvest_date - td_(days=1)
    t_block_end   = harvest_date + td_(days=travel_days + 1)

    # ── Check availability ─────────────────────────────────────────────
    qty = farmer['quantity_mt']
    warnings = []
    storage_ok = transport_ok = True
    free_mt = qty

    if storage:
        # available_capacity_mt is already the live value from overlay (reduced by prior bookings)
        # Do NOT subtract bookings again — that would double-count
        free_mt = storage['available_capacity_mt']
        if free_mt <= 0:
            return (f"✗ Storage '{storage['facility_name']}' is fully booked for those dates.\n"
                    f"Run the booking flow again to try rematching.")
        if free_mt < qty:
            warnings.append(f"Storage only has {free_mt:.1f} MT free (you need {qty} MT). Booking {free_mt:.1f} MT.")

    if transporter:
        for b in bookings:
            if b.get('transporter_id') != transporter['id'] or b.get('status') == 'cancelled':
                continue
            b_start = date.fromisoformat(b['transport_block_start'])
            b_end   = date.fromisoformat(b['transport_block_end'])
            if not (t_block_end < b_start or t_block_start > b_end):
                transport_ok = False
                warnings.append(f"Transporter already booked {t_block_start} → {t_block_end}.")
                break

    if not transport_ok and not storage:
        return "✗ No available resources for your dates. Try again later."

    booked_qty = min(free_mt, qty)

    # ── Save booking ───────────────────────────────────────────────────
    booking_id = 'BK-' + str(uuid.uuid4())[:6].upper()
    rate       = storage['rate_per_mt_per_day'] if storage else 0
    cost_est   = rate * booked_qty * storage_days if storage else 0

    booking = {
        'booking_id':            booking_id,
        'booked_at':             datetime.now().isoformat(),
        'status':                'confirmed',
        'farmer_id':             farmer_id,
        'farmer_name':           farmer['farmer_name'],
        'farmer_phone':          farmer['phone'],
        'crop':                  farmer['crop'],
        'quantity_mt':           booked_qty,
        'harvest_date':          str(harvest_date),
        'storage_id':            storage['id']            if storage     else None,
        'storage_name':          storage['facility_name'] if storage     else None,
        'storage_from':          str(storage_from)        if storage     else None,
        'storage_until':         str(storage_until)       if storage     else None,
        'storage_days':          storage_days             if storage     else None,
        'storage_cost_est':      cost_est                 if storage     else None,
        'transporter_id':        transporter['id']        if transporter else None,
        'transporter_name':      transporter['transporter_name'] if transporter else None,
        'transport_block_start': str(t_block_start)       if transporter else None,
        'transport_block_end':   str(t_block_end)         if transporter else None,
    }
    bookings.append(booking)
    save(BOOKINGS_FILE, bookings)

    set_overlay(farmer_id, status='booked')

    for m in matches:
        if m.get('farmer_id') == farmer_id:
            m['match_quality'] = 'booked'
            m['booking_id']    = booking_id
            m['matched_at']    = datetime.now().isoformat()
    save(MATCHES_FILE, matches)

    if storage:
        new_cap    = round(storage['available_capacity_mt'] - booked_qty, 2)
        new_status = 'full' if new_cap <= 0 else 'available'
        for s in storages:
            if s['id'] == storage['id']:
                s['available_capacity_mt'] = new_cap
                s['status']               = new_status
        save(STORAGES_FILE, storages) if hasattr(storages, '__len__') else None
        # Persist reduced capacity to overlay so next load_from_bridge reflects it
        set_overlay(storage['id'],
            entity_type          = 'storage',
            available_capacity_mt = new_cap,
            status               = new_status,
        )
        invalidate_bridge_cache('storages')

    if transporter and transport_ok:
        for t in transporters:
            if t['id'] == transporter['id']:
                blocks = t.get('blocked_dates', [])
                blocks.append({'booking_id': booking_id, 'from': str(t_block_start), 'until': str(t_block_end)})
                t['blocked_dates'] = blocks

    affected = rematch_affected_farmers(
        booked_storage_id=storage['id']         if storage     else None,
        booked_transporter_id=transporter['id'] if transporter else None,
        farmers=farmers,
        storages=storages,
        transporters=transporters,
    )

    lines = [
        '✅ Storage Booking Confirmed!',
        f"Booking ID  : {booking_id}",
        f"Farmer      : {farmer['farmer_name']}  ({farmer['phone']})",
        f"Crop        : {farmer['crop']}  |  {booked_qty} MT",
        f"Harvest     : {harvest_date}",
    ]
    if storage:
        lines += [
            f"Storage     : {storage['facility_name']}, {storage['district']}",
            f"Stored      : {storage_from} → {storage_until}  ({storage_days} days)",
        ]
        if cost_est > 0:
            lines.append(f"Cost est.   : Rs.{cost_est:,.0f}")
    if transporter and transport_ok:
        lines.append(f"Transport   : {transporter['transporter_name']}  ({transporter['driver_name']})")
        lines.append(f"Blocked     : {t_block_start} → {t_block_end}")
    for w in warnings:
        lines.append(f"⚠ {w}")
    if affected:
        lines.append(f"\nℹ {affected} other farmer(s) re-matched to next available option.")
    lines.append(f"\nSave your Booking ID: {booking_id}")

    sell_date = storage_until  # harvest_date + storage_days
    set_overlay(farmer_id,
        sell_date    = str(sell_date),
        storage_days = storage_days,
        trade_signal = f'HOLD_{storage_days}',
    )

    # Immediate "heads up" whisper to matching traders so they can plan ahead.
    # This is NOT a "crop ready to sell" alert — it tells traders supply is coming
    # on a known date so they can arrange logistics, finance, etc. in advance.
    # The "crop ready to sell" alert still fires from run_signals() on sell_date.
    try:
        from lot_matcher import crop_matches, district_matches

        crop_     = farmer['crop']
        district_ = farmer['district']

        heads_up_traders = [
            t for t in load_from_bridge('traders')
            if t.get('status') == 'active'
            and crop_matches(crop_, t.get('crops', []))
            and district_matches(district_, t.get('buy_districts', []))
        ]

        if heads_up_traders:
            heads_up = '\n'.join([
                '📦 KrishiSetu — Incoming Supply Notice',
                '',
                f"Crop        : {crop_}  |  {booked_qty} MT",
                f"Location    : {farmer.get('village', '')}, {district_}",
                f"Farmer      : {farmer['farmer_name']}  ({farmer['phone']})",
                f"In storage  : {storage_from} → {sell_date}  ({storage_days} days)",
                f"Available to buy: {sell_date}",
                '',
                'Plan ahead — farmer will be ready to sell on the above date.',
                'You will get another alert on the sell date to confirm availability.',
            ])
            hu_count = 0
            for trader in heads_up_traders:
                try:
                    _send_trader_whisper(trader, heads_up)
                    hu_count += 1
                    print(f"[booking/store] ✓ Heads-up sent to {trader['company_name']}")
                except Exception as te:
                    print(f"[booking/store] ✗ {trader['company_name']}: {te}")
            if hu_count:
                lines.append(f"\n✓ {hu_count} trader(s) notified to plan ahead for your sell date ({sell_date}).")
        else:
            lines.append(f"\nNo matching traders found right now. They will be alerted when you register or on sell date.")
    except Exception as e:
        print(f'[booking/store] Trader heads-up error: {e}')
        lines.append(f"\nTraders will be alerted on your sell date ({sell_date}).")

    return '\n'.join(lines)




FLOW_SCHEMAS = {
    'NewFarmerTemplate_FarmerFlow': {
        'payload_key':     'NewFarmerTemplate_FarmerFlow',
        'reply_flow':      'NewFarmerTemplate_FarmerIp',
        'reply_field_key': 'NewFarmerTemplate_FarmerIp_Main-4978f036-65a5-72f2-8470-bffe72a6a1ee_4',
        'processor':       process_farmer_flow,
    },
    'NewFarmerTemplate_ColdStorageInput': {
        'payload_key':     'NewFarmerTemplate_ColdStorageInput',
        'reply_flow':      'NewFarmerTemplate_FarmerIp',
        'reply_field_key': 'NewFarmerTemplate_FarmerIp_Main-4978f036-65a5-72f2-8470-bffe72a6a1ee_4',
        'processor':       process_cold_storage_flow,
    },
    'NewFarmerTemplate_TransportInput': {
        'payload_key':     'NewFarmerTemplate_TransportInput',
        'reply_flow':      'NewFarmerTemplate_FarmerIp',
        'reply_field_key': 'NewFarmerTemplate_FarmerIp_Main-4978f036-65a5-72f2-8470-bffe72a6a1ee_4',
        'processor':       process_transport_flow,
    },
    # Booking flow — farmer confirms slot via Bridge
    'NewFarmerTemplate_Booking': {
        'payload_key':     'NewFarmerTemplate_Booking',
        'reply_flow':      'NewFarmerTemplate_FarmerIp',
        'reply_field_key': 'NewFarmerTemplate_FarmerIp_Main-4978f036-65a5-72f2-8470-bffe72a6a1ee_4',
        'processor':       process_booking_flow,
    },
    'NewFarmerTemplate_TraderInput': {
        'payload_key':     'NewFarmerTemplate_TraderInput',
        'reply_flow':      'NewFarmerTemplate_FarmerIp',
        'reply_field_key': 'NewFarmerTemplate_FarmerIp_Main-4978f036-65a5-72f2-8470-bffe72a6a1ee_4',
        'processor':       process_trader_flow,
    },
    'NewFarmerTemplate_AccountInput': {
        'payload_key':     'NewFarmerTemplate_AccountInput',
        'reply_flow':      'NewFarmerTemplate_FarmerIp',
        'reply_field_key': 'NewFarmerTemplate_FarmerIp_Main-4978f036-65a5-72f2-8470-bffe72a6a1ee_4',
        'processor':       process_account_input_flow,
},
}

# ─────────────────────────────────────────────────────────────────────────────
# Bridge API
# ─────────────────────────────────────────────────────────────────────────────

def go():
    try:
        login()
        # Bootstrap: fetch all data once at startup so cache is warm
        print('[go] Bootstrapping cache from Bridge...')
        for _dt in ('farmers', 'storages', 'transporters', 'traders'):
            load_from_bridge(_dt)

        # Run migration only if needed (uses already-cached data, no extra API calls)
        _ov = load_overlay()
        if any('entity_type' not in v for v in _ov.values()):
            migrate_overlay_entity_types()
        else:
            print('migrate_overlay_entity_types: already complete, skipping')

        # Rebuild storage capacity from confirmed bookings so full storages
        # are never shown as available (fixes bookings made before overlay fix)
        rebuild_storage_capacity_overlay()
        # Seed mock market prices into data/market_prices.json on every startup
        from market_feed import refresh_prices
        refresh_prices(use_mock=True)
        print('[go] Mock market prices seeded to data/market_prices.json')
        _last_signal_check = 0
        while True:
            clienntSync()
            # run_signals checks sell dates — only needed once every 5 min, not every 10s
            if _time.time() - _last_signal_check >= 300:
                run_signals()
                _last_signal_check = _time.time()
            time.sleep(10)
    except Exception as e:
        print(e)
        return e

def login():
    try:
        global Sessionid, username, MobileNumber, forumID
        tempJson = {
            'MACAddress': 'Bridge-Web',
            'UserName':   '@uuid08da9a74946d40b8bc599bfe7c762b49',
            'Password':   base64.b64decode('Q29zbWl0dWRlQnJpZGdlRGV2aWNl').decode('UTF-8'),
            'ServerID':   'c9b6722d-5dbf-4b4f-a28e-692b4d26c1cf-7870eb8e-2f45-458a-9a70-d6b2d71ee871'
        }
        headers  = {'Content-Type': 'application/json'}
        response = requests.post('https://ca.cosmitude.com/loginForDevice', data=json.dumps(tempJson), headers=headers, timeout=600)
        print(response)
        print(response.text)
        respJson     = json.loads(response.text)
        Sessionid    = respJson['ErrorMessage']['SessionID']
        countryCode  = respJson['ErrorMessage']['CountryCode']
        MobileNumber = countryCode + respJson['ErrorMessage']['MobileNumber']
        getForumDetails()
        load_report_names()
    except Exception as e:
        print(e)
        return e

def getForumDetails():
    try:
        global TemplateID
        tempJson = {
            'MACAddress': 'Bridge-Web',
            'ForumID':    forumID,
            'SessionID':  Sessionid,
            'ServerID':   'c9b6722d-5dbf-4b4f-a28e-692b4d26c1cf-7870eb8e-2f45-458a-9a70-d6b2d71ee871'
        }
        headers  = {'Content-Type': 'application/json'}
        response = requests.post('https://ca.cosmitude.com/getRequestedForumDetails', data=json.dumps(tempJson), headers=headers, timeout=600)
        if response.status_code == 200:
            respJson = json.loads(response.text)
            if respJson['ErrorCode'] == 1172:
                for singleForum in respJson['ErrorMessage']['ForumDataArray']:
                    details = singleForum[forumID]
                    forum_data = details['NewForumJsonData']

                    # ── Patch missing ReportID for AccountInput ──
                    report_key = 'NewFarmerTemplate_Report_AccountInput_User_0bcf020e-6219-fadc-585f-35cde65acac8'
                    fake_report_id = 'aaf12345-0000-4000-a000-000000000001'

                    for section in ('Report', 'NewReports'):
                        if section in forum_data and report_key in forum_data[section]:
                            if 'ReportID' not in forum_data[section][report_key]:
                                forum_data[section][report_key]['ReportID'] = fake_report_id

                    # ── Patch EnableFlow ──
                    if 'EnableFlow' in forum_data:
                        forum_data['EnableFlow']['NewFarmerTemplate_AccountInput'] = 'True'

                    # ── Patch AccountInput into UserFlow ──
                    if 'UserFlow' in forum_data:
                        if 'NewFarmerTemplate_AccountInput' not in forum_data['UserFlow']:
                            forum_data['UserFlow']['NewFarmerTemplate_AccountInput'] = {
                                'FID': '0bcf020e-6219-fadc-585f-35cde65acac8',
                                'Formats': ['NewFarmerTemplate_AccountInput_Main-0bcf020e-6219-fadc-585f-35cde65acac8'],
                                'flowColour': '#e864a4',
                                'FlowImage': 'Default'
                            }
                    with open(ADMIN_FILE, 'w') as f:
                        json.dump(forum_data, f)
                    TemplateID = forum_data.get('TemplateID', '')
                    load_report_names()
    except Exception as e:
        print(e)
        return e

def clienntSync():
    try:
        clientSyncJson = {
            'SessionID':  Sessionid,
            'MACAddress': 'Bridge-Web',
            'ServerID':   'c9b6722d-5dbf-4b4f-a28e-692b4d26c1cf-7870eb8e-2f45-458a-9a70-d6b2d71ee871',
            'ServerName': 'Bridge'
        }
        headers  = {'Content-Type': 'application/json'}
        response = requests.post('https://ca.cosmitude.com/syncUserData', data=json.dumps(clientSyncJson), headers=headers, timeout=600)
        dataRead = json.loads(response.text)
        print(dataRead['ErrorMessage'])
        syncData = dataRead['ErrorMessage']['Admin']

        if syncData.count:
            for data in syncData:
                if 'Bridge' in data:
                    bridgeData = data['Bridge']
                    flowName   = bridgeData['FlowID']
                    mNumber    = bridgeData['MobileNumber']
                    print('FLOW NAME =', flowName)
                    print('SCHEMA FOUND =', FLOW_SCHEMAS.get(flowName))
                    print('ALL SCHEMA KEYS =', list(FLOW_SCHEMAS.keys()))
                    print('MY NUMBER =', MobileNumber)
                    print('MESSAGE NUMBER =', mNumber)

                    schema = FLOW_SCHEMAS.get(flowName)
                    if schema and MobileNumber != mNumber:
                        print(f'ENTERED {flowName} BLOCK')
                        print(json.dumps(bridgeData, indent=4))

                        # Fetch fresh data for the types this flow needs, right now.
                        # This is the ONLY place we call the Bridge report API —
                        # not on a background timer.
                        _FLOW_FETCH_MAP = {
                            'NewFarmerTemplate_FarmerFlow':      ['farmers', 'storages', 'transporters', 'traders'],
                            'NewFarmerTemplate_ColdStorageInput': ['storages', 'farmers', 'transporters'],
                            'NewFarmerTemplate_TransportInput':  ['transporters', 'farmers', 'storages'],
                            'NewFarmerTemplate_TraderInput':     ['traders', 'farmers'],
                            'NewFarmerTemplate_Booking':         ['farmers', 'storages', 'transporters', 'traders'],
                        }
                        for _dtype in _FLOW_FETCH_MAP.get(flowName, []):
                            invalidate_bridge_cache(_dtype)
                            load_from_bridge(_dtype)   # populates cache with fresh data

                        flow_payload      = bridgeData.get(schema['payload_key'], {})
                        current_bridge_id = bridgeData.get('BridgeID', '')
                        whisper_text      = schema['processor'](flow_payload, current_bridge_id)
                        print('WHISPER REPLY:\n', whisper_text)

                        reply_encoded = b64encode(whisper_text)
                        sendData      = {schema['reply_field_key']: reply_encoded}

                        que1 = Queue.Queue()
                        t1   = Thread(
                            target=lambda q, bd, rf, sd: q.put(sendWhisper(bd, rf, sd)),
                            args=(que1, bridgeData, schema['reply_flow'], sendData)
                        )
                        t1.start()
                        t1.join()

                elif 'UpdatedTemplateJson' in data:
                    templateForAdmin = data['UpdatedTemplateJson']
                    if templateForAdmin.get('ForumID') == forumID:
                        with open(ADMIN_FILE, 'w') as f:
                            json.dump(templateForAdmin, f)

    except Exception as e:
        print(e)

# ─────────────────────────────────────────────────────────────────────────────
# Send Whisper
# ─────────────────────────────────────────────────────────────────────────────

def sendWhisper(bridgeData, replyFlow, replyData):
    try:
        bridgeID           = bridgeData['BridgeID']
        TemplateID         = bridgeData['TemplateID']
        ForumID            = bridgeData['ForumID']
        mobileNumber       = bridgeData['MobileNumber']
        whisperSendingType = True if bridgeData.get('User') == True else False

        with open(ADMIN_FILE, 'r') as f:
            jsonData = json.loads(f.read())
        FID = jsonData['AdminFlow'][replyFlow]['FID']

        tempJson = {
            'ForumID':           ForumID,
            'SessionID':         Sessionid,
            'MACAddress':        'Bridge-Web',
            'Time':              '6516516156161',
            'ScheduledDateTime': 'now',
            'ScheduledBoolean':  0,
            'FlowID':            replyFlow,
            'EnableChat':        1,
            'FlowType':          'Custom',
            'BridgeForward':     0,
            'TemplateID':        TemplateID,
            'TextCount':         1,
            'ImageCount':        1,
            'InvoiceID':         '',
            'DocumentCount':     0,
            'User':              False,
            'VideoCount':        0,
            'ReplyBridgeID':     bridgeID,
            'HiddenFlow':        False,
            'TempBridgeId':      str(uuid.uuid4()),
            replyFlow:           replyData,
            'FID':               FID,
            'ServerID':          'c9b6722d-5dbf-4b4f-a28e-692b4d26c1cf-7870eb8e-2f45-458a-9a70-d6b2d71ee871',
            'WhisperToUser':     whisperSendingType,
            'WhisperReceiver':   mobileNumber,
            'SentTo':            '3'
        }

        variab   = {'Data': json.dumps(tempJson)}
        response = requests.post('https://ca.cosmitude.com/bridgeWhisperSending', files={}, data=variab, timeout=600)
        print(f'[sendWhisper] status={response.status_code} to={mobileNumber} flow={replyFlow}')
        print(f'[sendWhisper] response={response.text[:300]}')
    except Exception as e:
        print(f'[sendWhisper] ERROR to={mobileNumber}: {e}')
        return e

# ─────────────────────────────────────────────────────────────────────────────
# Report fetching — replaces local JSON reads for farmers/storages/transporters
# ─────────────────────────────────────────────────────────────────────────────

# Report name for each flow — the active (EndDate=100) report FID per flow
# Read from Admin.txt at startup so it's always current
REPORT_NAMES = {}

def load_report_names():
    """Read the active report name (EndDate='100') for each flow from Admin.txt."""
    global REPORT_NAMES
    try:
        with open(ADMIN_FILE, 'r') as f:
            admin = json.load(f)
        reports = admin.get('Report', {})
        # For each flow we care about, find the report with EndDate='100' (active)
        flow_map = {
            'NewFarmerTemplate_FarmerFlow':       'farmers',
            'NewFarmerTemplate_ColdStorageInput': 'storages',
            'NewFarmerTemplate_TransportInput':   'transporters',
            'NewFarmerTemplate_TraderInput': 'traders',
        }
        for report_name, r in reports.items():
            flow = r.get('FlowName', '')
            if flow in flow_map and str(r.get('EndDate', '')) == '100':
                REPORT_NAMES[flow_map[flow]] = report_name
        print('Report names loaded:', REPORT_NAMES)
    except Exception as e:
        print('load_report_names error:', e)


def fetchReportData(report_name, from_date, to_date, template_id, fid):
    """
    Call generateReport API to fetch all rows for a given report.
    Returns list of raw row dicts (field values still base64 encoded).
    """
    try:
        # Determine User flag from report name (e.g. ..._User_... vs ..._Admin_...)
        parts = report_name.split('_')
        admin_or_user_str = parts[3] if len(parts) > 3 else 'User'
        is_user = (admin_or_user_str != 'Admin')

        current_time = int(round(time.time()))
        # Fetch all-time records: start from 2 years ago so no registration is missed
        start_time = current_time - (365 * 2 * 24 * 3600)
        temp_json = {
            "SessionID":       Sessionid,
            "MACAddress":      "Bridge-Web",
            "ReportName":      report_name,
            "User":            is_user,
            "ReportSchedule":  "now",
            "ForumID":         forumID,
            "Label":           "",
            "Operator":        "",
            "Input":           "",
            "StartDate":       str(start_time),
            "EndDate":         str(current_time),
            "TimePeriod":      "",
            "TimePeriodInput": "",
            "TempBridgeId":    str(uuid.uuid4()),
            "Time":            str(current_time),
            "SendGroupReport": [],
            "SpecificReport":  [],
            "TemplateID":      template_id,
            "FID":             fid,
            "UserMobileNumber": "All",
            "ServerID":        "c9b6722d-5dbf-4b4f-a28e-692b4d26c1cf-7870eb8e-2f45-458a-9a70-d6b2d71ee871"
        }
        form_data = {"Data": json.dumps(temp_json)}
        response  = requests.post(
            'https://ca.cosmitude.com/generateReport',
            files={}, data=form_data, timeout=600
        )
        raw = response.text.strip()
        print(f'[DEBUG] generateReport {report_name[:50]} | status={response.status_code} | raw_preview={repr(raw[:200])}')
        if not raw:
            return []
        try:
            resp_json = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if resp_json.get('ErrorCode') == 1042:
            rows = resp_json['ErrorMessage'].get(report_name, [])
            print(f'[DEBUG] Got {len(rows)} rows for {report_name[:50]}')
            return rows
        elif resp_json.get('ErrorCode') == 3112:
            print(f'[quota] Bridge quota exceeded (300/day). Will retry in {_QUOTA_RESET_WAIT//3600}h.')
            _QUOTA_EXCEEDED_UNTIL = _time.time() + _QUOTA_RESET_WAIT
            return None   # signal to caller: use stale cache, don't update timestamp
        else:
            print('fetchReportData unexpected ErrorCode:', resp_json.get('ErrorCode'), '| raw:', repr(raw[:300]))
            return []
    except Exception as e:
        print('fetchReportData error:', e)
        return []


def parse_farmer_rows(rows):
    """Convert raw Bridge report rows into farmer record dicts."""
    farmers = []
    seen_ids = set()
    for row in rows:
        def f(i): return b64decode(row.get(
            f'NewFarmerTemplate_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_{i}', ''))

        confirm = f(25).strip().lower()
        if confirm in ('cancel', 'no', 'n'):
            continue

        name     = f(11).strip()
        phone    = f(12).strip()
        district = f(13).strip()
        village  = f(22).strip()
        crop     = f(15).strip()
        qty_s    = f(16).strip()
        days_s   = f(17).strip()

        if not name or not phone or not crop:
            continue
        try:
            qty  = float(qty_s)
            days = int(days_s)
        except ValueError:
            continue

        # Use BridgeID as stable unique ID (short hash)
        bridge_id = row.get('BridgeID', '')[:8]
        if bridge_id in seen_ids:
            continue
        seen_ids.add(bridge_id)

        # registered_at from Bridge Time (unix timestamp)
        ts_ms = int(row.get('Time', 0))
        ts_sec = ts_ms / 1000 if ts_ms > 1e10 else ts_ms  # Bridge uses ms
        registered_at = datetime.fromtimestamp(ts_sec).isoformat() if ts_sec else datetime.now().isoformat()

        # harvest_date: stored absolute in overlay; fallback compute from reg_date
        reg_date     = datetime.fromtimestamp(ts_sec).date() if ts_sec else date.today()
        bridge_id_for_overlay = row.get('BridgeID', '')[:8]
        overlay      = load_overlay()
        if bridge_id_for_overlay in overlay and 'harvest_date' in overlay[bridge_id_for_overlay]:
            harvest_date = date.fromisoformat(overlay[bridge_id_for_overlay]['harvest_date'])
        else:
            harvest_date = reg_date + timedelta(days=days)

        farmers.append({
            'id':                    bridge_id,
            'registered_at':         registered_at,
            'farmer_name':           name,
            'phone':                 phone,
            'district':              district,
            'village':               village,
            'crop':                  crop,
            'quantity_mt':           qty,
            'days_until_ready':      days,
            'harvest_date':          str(harvest_date),
            'preferred_storage_area': f(23) or None,
            'notes':                 f(24) or None,
            'status':                'unmatched',
            'source':                'bridge_report',
        })
    return farmers


def parse_storage_rows(rows):
    """Convert raw Bridge report rows into cold storage record dicts."""
    storages = []
    seen_ids = set()
    for row in rows:
        def f(i): return b64decode(row.get(
            f'NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_{i}', ''))

        confirm = f(26).strip().lower()
        if confirm in ('cancel', 'no', 'n'):
            continue

        facility = f(14).strip()
        operator = f(15).strip()
        phone    = f(16).strip()
        district = f(17).strip()
        address  = f(18).strip()
        crops_s  = f(22).strip()

        if not facility or not district:
            continue
        try:
            cap       = float(f(19).strip() or 0)
            from_days = int(f(20).strip() or 0)
            duration  = int(f(21).strip() or 30)
            rate      = float(f(23).strip() or 0)
            min_qty_s = f(24).strip()
            min_qty   = float(min_qty_s) if min_qty_s and min_qty_s not in ('-', '') else None
        except ValueError:
            continue

        bridge_id = row.get('BridgeID', '')[:8]
        if bridge_id in seen_ids:
            continue
        seen_ids.add(bridge_id)

        ts_ms        = int(row.get('Time', 0))
        ts           = ts_ms / 1000 if ts_ms > 1e10 else ts_ms
        reg_date     = datetime.fromtimestamp(ts).date() if ts else date.today()
        avail_from   = reg_date + timedelta(days=from_days)
        avail_until  = avail_from + timedelta(days=duration)
        supported    = ['All'] if crops_s.lower() == 'all' else \
                       [c.strip().title() for c in crops_s.split(',') if c.strip()]

        storages.append({
            'id':                    bridge_id,
            'registered_at':         datetime.fromtimestamp(ts).isoformat() if ts else datetime.now().isoformat(),
            'facility_name':         facility,
            'operator_name':         operator,
            'phone':                 phone,
            'district':              district,
            'address':               address,
            'available_capacity_mt': cap,
            'available_from':        str(avail_from),
            'available_until':       str(avail_until),
            'supported_crops':       supported,
            'rate_per_mt_per_day':   rate,
            'minimum_quantity_mt':   min_qty,
            'notes':                 f(25) or None,
            'status':                'available',
            'source':                'bridge_report',
        })
    return storages


def parse_transport_rows(rows):
    """Convert raw Bridge report rows into transporter record dicts."""
    transporters = []
    seen_ids = set()
    for row in rows:
        def f(i): return b64decode(row.get(
            f'NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_{i}', ''))

        confirm = f(28).strip().lower()
        if confirm in ('cancel', 'no', 'n'):
            continue

        name     = f(15).strip()
        phone    = f(17).strip()
        district = f(18).strip()
        vehicle  = f(19).strip()
        op_dists = f(26).strip()

        if not name or not district:
            continue
        try:
            cap       = float(f(20).strip() or 0)
            from_days = int(f(22).strip() or 0)
            av_days   = int(f(23).strip() or 7)
            max_dist  = float(f(24).strip() or 0)
            rate      = float(f(25).strip() or 0)
        except ValueError:
            continue

        bridge_id = row.get('BridgeID', '')[:8]
        if bridge_id in seen_ids:
            continue
        seen_ids.add(bridge_id)

        ts_ms       = int(row.get('Time', 0))
        ts          = ts_ms / 1000 if ts_ms > 1e10 else ts_ms
        reg_date    = datetime.fromtimestamp(ts).date() if ts else date.today()
        avail_from  = reg_date + timedelta(days=from_days)
        avail_until = avail_from + timedelta(days=av_days)
        refrig      = f(21).strip().lower() in ('yes', 'y')
        op_list     = [d.strip().title() for d in op_dists.split(',') if d.strip()]
        driver      = f(16).strip() or name

        transporters.append({
            'id':                  bridge_id,
            'registered_at':       datetime.fromtimestamp(ts).isoformat() if ts else datetime.now().isoformat(),
            'transporter_name':    name,
            'driver_name':         driver,
            'phone':               phone,
            'base_district':       district,
            'vehicle_type':        vehicle,
            'capacity_mt':         cap,
            'is_refrigerated':     refrig,
            'available_from':      str(avail_from),
            'available_until':     str(avail_until),
            'operating_districts': op_list,
            'max_distance_km':     max_dist,
            'rate_per_mt_per_km':  rate,
            'notes':               f(27) or None,
            'status':              'available',
            'source':              'bridge_report',
        })
    return transporters

def parse_trader_rows(rows):
    """Convert raw Bridge report rows into trader record dicts."""
    traders  = []
    seen_ids = set()
    # UUID confirmed from live Bridge payload: FarmerInput_TraderInput_Main-5de6720a-...
    _TRADER_UUID = '5de6720a-8239-caa3-6372-3cdb5eadeeea'
    for row in rows:
        def f(i, _u=_TRADER_UUID): return b64decode(row.get(
            f'NewFarmerTemplate_TraderInput_Main-{_u}_{i}', ''))

        # Fields match process_trader_flow: 7=company, 8=phone, 9=district,
        # 10=crops, 11=buy_districts, 12=confirm
        confirm = f(12).strip().lower()
        if confirm in ('cancel', 'no', 'n'):
            continue

        company  = f(7).strip()
        phone    = f(8).strip()
        district = f(9).strip()
        if not company or not district:
            continue

        bridge_id = row.get('BridgeID', '')[:8]
        if bridge_id in seen_ids:
            continue
        seen_ids.add(bridge_id)

        crops_s = f(10).strip()
        dists_s = f(11).strip()

        traders.append({
            'id':             bridge_id,
            'registered_at':  datetime.fromtimestamp(
                                int(row.get('Time', 0))).isoformat(),
            'company_name':   company,
            'phone':          phone,
            'bridge_mobile':  row.get('MobileNumber', ''),  # full Bridge-format number for whispers
            'base_district':  district,
            'crops':          ['All'] if crops_s.lower() == 'all' else
                              [c.strip().title() for c in crops_s.split(',') if c.strip()],
            'buy_districts':  ['All Karnataka'] if 'all' in dists_s.lower() else
                              [d.strip().title() for d in dists_s.split(',') if d.strip()],
            'min_lot_mt':     0,
            'max_lot_mt':     None,
            'has_transport':  False,
            'price_floor_qt': 0,
            'status':         'active',
            'source':         'bridge_report',
        })
    return traders

# Cache for Bridge report data — avoids burning API quota on every 10s sync
_BRIDGE_CACHE        = {}     # data_type -> list of records
_BRIDGE_CACHE_TIME   = {}     # data_type -> last fetch timestamp
_BRIDGE_CACHE_TTL    = 3600   # seconds between re-fetches (1 hour) — quota is 300/day
_QUOTA_EXCEEDED_UNTIL = 0     # epoch time until which we skip all API calls (quota reset)
_QUOTA_RESET_WAIT    = 3600   # wait 1 hour before retrying after quota hit

def invalidate_bridge_cache(data_type=None):
    """Evict one or all data types so the next call forces a fresh API fetch."""
    if data_type:
        _BRIDGE_CACHE.pop(data_type, None)
    else:
        _BRIDGE_CACHE.clear()

def load_from_bridge(data_type, force=False):
    """
    Return Bridge report data for data_type.

    Fetch policy (event-driven, not time-driven):
      - Returns cache immediately if data is present AND force=False.
      - force=True (or cache empty) triggers one real API call.
      - Call invalidate_bridge_cache(data_type) before the call that needs
        fresh data (i.e. right when a registration flow arrives).
      - Never called on a background timer — only from flow handlers and startup.

    This keeps Bridge API usage to ~4 calls at boot + ~4 per registration event
    instead of hundreds per day from polling.
    """
    global _QUOTA_EXCEEDED_UNTIL

    # Serve cache if available and not forced
    if not force and data_type in _BRIDGE_CACHE:
        return list(_BRIDGE_CACHE[data_type])

    # Quota guard — don't hammer a wall
    now = _time.time()
    if now < _QUOTA_EXCEEDED_UNTIL:
        print(f'[quota] Skipping API call for {data_type} — retry after {int((_QUOTA_EXCEEDED_UNTIL - now)/60)} min')
        return list(_BRIDGE_CACHE.get(data_type, []))

    report_name = REPORT_NAMES.get(data_type)
    if not report_name:
        print(f'No report name found for {data_type} — Bridge reports not yet loaded.')
        return []

    try:
        with open(ADMIN_FILE, 'r') as f:
            admin = json.load(f)

        report      = admin['Report'][report_name]
        template_id = admin.get('TemplateID', '')
        fid         = report['FID']

        rows = fetchReportData(report_name, None, None, template_id, fid)
        if rows is None:
            return list(_BRIDGE_CACHE.get(data_type, []))  # quota hit — serve stale

        if data_type == 'farmers':
            records = parse_farmer_rows(rows)
        elif data_type == 'storages':
            records = parse_storage_rows(rows)
        elif data_type == 'traders':
            records = parse_trader_rows(rows)
        else:
            records = parse_transport_rows(rows)

        apply_overlay(records)
        _BRIDGE_CACHE[data_type] = records
        print(f'load_from_bridge: {len(records)} {data_type} from Bridge')
        return list(records)

    except Exception as e:
        print(f'load_from_bridge error for {data_type}:', e)
        return list(_BRIDGE_CACHE.get(data_type, []))

def migrate_overlay_entity_types():
    """
    One-time migration: infer entity_type for existing overlay records
    by checking which Bridge report they appear in.
    Safe to run repeatedly — skips records that already have entity_type.
    """
    overlay = load_overlay()
    changed = False

    farmers      = load_from_bridge('farmers')
    storages     = load_from_bridge('storages')
    transporters = load_from_bridge('transporters')

    farmer_ids      = {f['id'] for f in farmers}
    storage_ids     = {s['id'] for s in storages}
    transporter_ids = {t['id'] for t in transporters}

    for rid, data in overlay.items():
        if 'entity_type' in data:
            continue
        if rid in farmer_ids:
            data['entity_type'] = 'farmer'
        elif rid in storage_ids:
            data['entity_type'] = 'storage'
        elif rid in transporter_ids:
            data['entity_type'] = 'transporter'
        changed = True

    if changed:
        save_overlay(overlay)
        print('migrate_overlay_entity_types: migration complete')

def _send_trader_whisper(trader, alert):
    """Helper to whisper an alert message to a trader via Bridge."""
    # Use bridge_mobile (full Bridge-format number) if available, else fall back to plain phone.
    # Plain phone (e.g. '9356826301') causes ErrorCode 1074 'User Not Found' — Bridge needs
    # the prefixed format it stores internally (e.g. '2743431080988311569568241').
    mobile = trader.get('bridge_mobile') or trader['phone']
    trader_bridge_data = {
        'BridgeID':     trader['id'],
        'TemplateID':   TemplateID,
        'ForumID':      forumID,
        'MobileNumber': mobile,
        'User':         True,
    }
    reply_encoded = b64encode(alert)
    reply_data    = {'NewFarmerTemplate_FarmerIp_Main-4978f036-65a5-72f2-8470-bffe72a6a1ee_4': reply_encoded}
    sendWhisper(trader_bridge_data, 'NewFarmerTemplate_FarmerIp', reply_data)


def rebuild_storage_capacity_overlay():
    """
    On startup, ensure every storage has available_capacity_mt in the overlay.
    - If overlay already has it → leave it alone (it was tracked correctly by bookings).
    - If overlay is missing it → seed from original Bridge capacity minus confirmed bookings.
    This is a one-time repair for storages registered before the capacity-tracking fix.
    """
    report_name = REPORT_NAMES.get('storages')
    if not report_name:
        return
    try:
        with open(ADMIN_FILE, 'r') as f:
            admin = json.load(f)
        report = admin['Report'][report_name]
        rows   = fetchReportData(report_name, None, None, admin.get('TemplateID', ''), report['FID'])
        if not rows:
            return
        raw_storages = parse_storage_rows(rows)  # original capacities, no overlay applied
    except Exception as e:
        print(f'[startup] rebuild error: {e}')
        return

    bookings  = load(BOOKINGS_FILE)
    overlay   = load_overlay()
    confirmed = [b for b in bookings if b.get('status') != 'cancelled']

    for storage in raw_storages:
        sid      = storage['id']
        ov_entry = overlay.get(sid, {})

        # Already tracked correctly — leave it
        if 'available_capacity_mt' in ov_entry:
            print(f'[startup] Storage "{storage["facility_name"]}": {ov_entry["available_capacity_mt"]} MT free [{ov_entry.get("status")}]')
            continue

        # Missing — seed from original capacity minus bookings
        orig_cap = storage['available_capacity_mt']
        used     = sum(b.get('quantity_mt', 0) for b in confirmed if b.get('storage_id') == sid)
        new_cap  = round(max(orig_cap - used, 0), 2)
        status   = 'full' if new_cap <= 0 else 'available'
        set_overlay(sid, entity_type='storage', available_capacity_mt=new_cap, status=status)
        print(f'[startup] Storage "{storage["facility_name"]}": seeded {orig_cap} - {used} = {new_cap} MT [{status}]')

    invalidate_bridge_cache('storages')
    print('[startup] Storage capacity overlay ready.')


def run_signals():
    """
    Runs every 5 minutes. Two independent checks:

    1. SELL_DATE CHECK — if today >= sell_date for a booked farmer, alert
       matching traders immediately regardless of market signal. This is the
       primary notification path for STORE bookings.

    2. MARKET SIGNAL CHECK — if the market signal flips to SELL_NOW for any
       booked farmer (even before sell_date), alert traders early.

    Uses cached data — does NOT trigger an API call.
    Tracks already-alerted farmers in overlay to avoid duplicate whispers.
    """
    try:
        from market_feed  import refresh_prices
        from trade_signal import run_signals_for_all_farmers
        from lot_matcher  import match_sell_now_lots, build_trader_alert, crop_matches, district_matches

        refresh_prices(use_mock=True)

        all_farmers = load_from_bridge('farmers')
        booked = [f for f in all_farmers if f.get('status') == 'booked']
        if not booked:
            return

        all_traders = load_from_bridge('traders')
        bookings    = load(BOOKINGS_FILE)
        overlay     = load_overlay()
        today       = date.today()
        alert_count = 0

        # ── 1. SELL_DATE CHECK ────────────────────────────────────────────
        for farmer in booked:
            fid      = farmer['id']
            ov       = overlay.get(fid, {})
            sell_date_str = ov.get('sell_date')
            if not sell_date_str:
                continue
            try:
                sell_date = date.fromisoformat(sell_date_str)
            except ValueError:
                continue

            # Only fire on or after sell_date, and only once
            if today < sell_date:
                continue
            if ov.get('sell_alert_sent'):
                continue

            # Find matching traders
            crop_    = farmer.get('crop', '')
            district_= farmer.get('district', '')
            matching = [
                t for t in all_traders
                if t.get('status') == 'active'
                and crop_matches(crop_, t.get('crops', []))
                and district_matches(district_, t.get('buy_districts', []))
            ]
            if not matching:
                print(f"[signals/sell_date] No traders for {farmer['farmer_name']} ({crop_}, {district_})")
                set_overlay(fid, sell_alert_sent=True)
                continue

            storage_days = ov.get('storage_days', '?')
            alert_lines = [
                '🌾 KrishiSetu — Crop Ready to Sell!',
                '',
                f"Farmer   : {farmer['farmer_name']}  ({farmer.get('phone','')})",
                f"Crop     : {crop_}  |  {farmer.get('quantity_mt', '?')} MT",
                f"District : {district_}  ({farmer.get('village','')})",
                f"Stored   : {storage_days} days — storage period ended {sell_date}",
                f"Available: NOW — farmer is ready to sell",
                '',
                'Contact the farmer directly on their registered number.',
                'Or wait — they will reach out via the KrishiSetu booking flow.',
            ]
            alert = '\n'.join(alert_lines)

            for trader in matching:
                try:
                    _send_trader_whisper(trader, alert)
                    print(f"[signals/sell_date] ✓ {trader['company_name']} alerted for {farmer['farmer_name']}")
                    alert_count += 1
                except Exception as e:
                    print(f"[signals/sell_date] ✗ {trader['company_name']}: {e}")

            # Mark as alerted so we don't re-send every 5 min
            set_overlay(fid, sell_alert_sent=True)

        # ── 2. MARKET SIGNAL CHECK ────────────────────────────────────────
        sell_now = run_signals_for_all_farmers(all_farmers, all_traders, bookings)
        matched  = match_sell_now_lots(sell_now, all_traders)

        for farmer, signal, traders in matched:
            fid = farmer['id']
            if overlay.get(fid, {}).get('sell_alert_sent'):
                continue   # already alerted via sell_date check above
            for trader in traders:
                alert = build_trader_alert(farmer, signal, trader)
                try:
                    _send_trader_whisper(trader, alert)
                    print(f"[signals/market] ✓ {trader['company_name']} alerted for {farmer['farmer_name']}")
                    alert_count += 1
                except Exception as e:
                    print(f"[signals/market] ✗ {trader['company_name']}: {e}")

        if alert_count:
            print(f'[signals] {alert_count} trader alert(s) sent this cycle.')

    except Exception as e:
        print(f'[signals] Error: {e}')



from threading import Thread

import os

if __name__ == "__main__":
    Thread(
        target=go,
        daemon=True
    ).start()

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )
# End of bot code