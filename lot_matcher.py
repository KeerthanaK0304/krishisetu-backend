"""
lot_matcher.py — KrishiSetu Lot Matcher
Matches SELL_NOW farmers to registered traders.
Called after trade_signal.run_signals_for_all_farmers().
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from matcher import haversine_km, get_coords
from districts import canonical

MAX_MATCH_DISTANCE_KM = 200


def crop_matches(farmer_crop, trader_crops):
    if 'All' in trader_crops:
        return True
    return farmer_crop.lower() in [c.lower() for c in trader_crops]


def district_matches(farmer_district, trader_districts):
    if any('all' in d.lower() for d in trader_districts):
        return True
    fc = canonical(farmer_district)
    return any(canonical(d) == fc for d in trader_districts)


def lot_qualifies(farmer, trader):
    """Check if a farmer lot meets a trader's criteria."""
    qty = farmer.get('quantity_mt', 0)

    if not crop_matches(farmer.get('crop',''), trader.get('crops', [])):
        return False, 'crop mismatch'
    if not district_matches(farmer.get('district',''), trader.get('buy_districts', [])):
        return False, 'district mismatch'
    if trader.get('min_lot_mt', 0) > 0 and qty < trader['min_lot_mt']:
        return False, f"lot {qty} MT below min {trader['min_lot_mt']} MT"
    if trader.get('max_lot_mt') and qty > trader['max_lot_mt']:
        return False, f"lot {qty} MT above max {trader['max_lot_mt']} MT"

    return True, 'ok'


def build_trader_alert(farmer, signal, trader):
    """
    Build the whisper text sent to a trader when a matching lot hits SELL_NOW.
    Mirrors the brevity of the farmer whisper — no tables, no box drawing.
    """
    lines = [
        '🔔 KrishiSetu — Lot Available',
        '',
        f"Crop     : {farmer['crop']}  |  {farmer['quantity_mt']} MT",
        f"District : {farmer['district']}  ({farmer.get('village','')})",
        f"Farmer   : {farmer['farmer_name']}  ({farmer['phone']})",
        f"Mandi    : {signal['mandi']}",
        f"Price now: Rs.{signal['today_price_qt']}/qt",
    ]
    if not trader.get('has_transport'):
        lines.append("Delivery : Farmer needs transport — can you arrange?")
    else:
        lines.append("Delivery : Farmer has transport available")

    lines += [
        '',
        'To express interest, reply with your Trader ID.',
        f"Your Trader ID: {trader['id']}",
    ]
    return '\n'.join(lines)


def trader_available_on_date(trader, sell_date_str):
    """Return True if trader has no blocked-date window covering sell_date_str."""
    if not sell_date_str:
        return True
    try:
        from datetime import date as _d
        check = _d.fromisoformat(sell_date_str)
        for blk in trader.get('blocked_dates', []):
            b_start = _d.fromisoformat(blk['from'])
            b_end   = _d.fromisoformat(blk['until'])
            if b_start <= check <= b_end:
                return False
    except Exception:
        pass
    return True


def match_sell_now_lots(sell_now_list, all_traders):
    """
    For each SELL_NOW farmer, find matching traders.
    Bug 6 fix: filters traders by availability on farmer's sell_date so we only
    alert traders who are actually free on that specific day.
    Returns list of (farmer, signal, [matching_traders]).
    """
    results = []
    for farmer, signal in sell_now_list:
        sell_date = farmer.get('sell_date', '')
        matched_traders = []
        for trader in all_traders:
            if trader.get('status') != 'active':
                continue
            ok, reason = lot_qualifies(farmer, trader)
            if not ok:
                continue
            # Price floor check
            today_p = signal.get('today_price_qt', 0)
            if trader.get('price_floor_qt', 0) > 0 and today_p < trader['price_floor_qt']:
                continue
            # Bug 6: only include traders available on the sell date
            if not trader_available_on_date(trader, sell_date):
                print(f"[lot_matcher] Skipping {trader['company_name']} — blocked on {sell_date}")
                continue
            matched_traders.append(trader)

        if matched_traders:
            results.append((farmer, signal, matched_traders))
            print(f"[lot_matcher] {farmer['farmer_name']} {farmer['crop']} "
                  f"→ {len(matched_traders)} trader(s) alerted (sell_date={sell_date})")

    return results