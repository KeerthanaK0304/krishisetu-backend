"""
trade_signal.py — KrishiSetu Trade Signal Engine

For a farmer with a confirmed booking, computes:
  - Net gain from holding N more days in cold storage
  - Compares today's mandi price vs forecast
  - Emits a signal: SELL_NOW | HOLD_7 | HOLD_14 | HOLD_21

Also updates the farmer's entry in status_overlay.json with:
  trade_signal, last_price_qt, signal_updated_at
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta
from price_forecast import forecast_price
from market_feed import get_latest_price, refresh_prices

# Weight coefficients — tune these as you collect real data
W_PRICE     = 0.45   # how much forecast price gain matters
W_SUPPLY    = 0.30   # how much low competition matters
W_STORAGE   = 0.25   # cost of holding (negative weight)

HOLD_OPTIONS = [0, 7, 14, 21]   # days to evaluate


def storage_cost_for_farmer(farmer, bookings, hold_days):
    """
    Total extra storage cost if farmer holds produce hold_days more days.
    Looks up confirmed booking to get rate_per_mt_per_day.
    """
    booking = next(
        (b for b in bookings
         if b.get('farmer_id') == farmer['id']
         and b.get('status') == 'confirmed'),
        None
    )
    if not booking:
        return 0.0
    rate = booking.get('storage_rate_per_mt_per_day', 0)
    qty  = farmer.get('quantity_mt', 0)
    return rate * qty * hold_days


def compute_signal(farmer, all_farmers, bookings, target_mandi=None):
    """
    Main function. Returns a signal dict for a single farmer.

    signal dict:
        signal          — 'SELL_NOW' | 'HOLD_7' | 'HOLD_14' | 'HOLD_21'
        today_price_qt  — current modal price at target_mandi
        best_price_qt   — forecast price at signal day
        net_gain_rs     — estimated net gain vs selling today (Rs total)
        confidence      — 'high' | 'medium' | 'low'
        reason          — human-readable explanation (one line)
        mandi           — which mandi was used
    """
    crop     = farmer.get('crop', '')
    district = farmer.get('district', '')
    qty      = farmer.get('quantity_mt', 1)

    # Determine target mandi — use provided, or pick first in TARGET_MANDIS
    from market_feed import TARGET_MANDIS
    if not target_mandi:
        mandis_for_crop = TARGET_MANDIS.get(crop, [])
        target_mandi    = mandis_for_crop[0] if mandis_for_crop else district

    # Refresh prices if stale (today not in cache)
    latest = get_latest_price(crop, target_mandi)
    if not latest or latest['date'] < str(date.today()):
        refresh_prices(use_mock=True)   # swap use_mock=False once API connected
        latest = get_latest_price(crop, target_mandi)

    if not latest:
        return {
            'signal':         'SELL_NOW',
            'today_price_qt': None,
            'best_price_qt':  None,
            'net_gain_rs':    0,
            'confidence':     'low',
            'reason':         'No price data available — sell at current mandi price.',
            'mandi':          target_mandi,
        }

    today_price = latest['modal_price']
    best_hold   = 0
    best_net    = 0.0
    best_fc     = today_price

    for hold_days in HOLD_OPTIONS[1:]:   # skip 0 (sell today)
        fc = forecast_price(crop, target_mandi, hold_days,
                            all_farmers=all_farmers, farmer_district=district)
        if fc['forecast_price_qt'] is None:
            continue

        forecast_p   = fc['forecast_price_qt']
        cost         = storage_cost_for_farmer(farmer, bookings, hold_days)
        # Net gain = (forecast - today) × qty × 10 (1 qt = 100 kg, 1 MT = 10 qt)
        price_gain   = (forecast_p - today_price) * qty * 10
        net_gain     = price_gain - cost

        if net_gain > best_net:
            best_net  = net_gain
            best_hold = hold_days
            best_fc   = forecast_p

    if best_hold == 0 or best_net <= 0:
        signal = 'SELL_NOW'
        reason = f"Today's price (Rs.{today_price}/qt) is best. No holding benefit."
    else:
        signal = f'HOLD_{best_hold}'
        gain_per_qt = best_fc - today_price
        reason = (f"Hold {best_hold} days → forecast Rs.{best_fc}/qt "
                  f"(+Rs.{gain_per_qt}/qt). Net gain after storage: "
                  f"Rs.{best_net:,.0f}")

    # Re-run forecast for confidence
    fc_check = forecast_price(crop, target_mandi, best_hold or 7,
                              all_farmers=all_farmers, farmer_district=district)

    return {
        'signal':         signal,
        'today_price_qt': today_price,
        'best_price_qt':  best_fc,
        'net_gain_rs':    round(best_net),
        'confidence':     fc_check.get('confidence', 'medium'),
        'reason':         reason,
        'mandi':          target_mandi,
    }


def run_signals_for_all_farmers(all_farmers, all_traders, bookings):
    """
    Compute trade signal for every farmer with a confirmed booking.
    Updates status_overlay.json for each.
    Returns list of (farmer, signal_dict) for farmers whose sell_date has
    arrived (storage period ended) AND signal is SELL_NOW.

    Bug 6 fix: only trigger SELL_NOW for a farmer once their sell_date
    (harvest_date + storage_days) has been reached — not before.
    Traders are matched only for that specific sell date (availability check
    happens in match_sell_now_lots via lot_qualifies).
    """
    from overlay import set_overlay, load_overlay
    from datetime import datetime

    overlay      = load_overlay()
    sell_now_list = []
    today        = date.today()

    for farmer in all_farmers:
        # Only run signals for booked farmers (they have storage)
        if farmer.get('status') != 'booked':
            continue

        # Bug 6: respect the planned sell_date — skip if storage period not over yet
        farmer_ov = overlay.get(farmer['id'], {})
        sell_date_str = farmer_ov.get('sell_date', '')
        if sell_date_str:
            try:
                sell_date = date.fromisoformat(sell_date_str)
                if today < sell_date:
                    # Storage period not over yet — do not alert traders
                    continue
            except ValueError:
                pass

        sig = compute_signal(farmer, all_farmers, bookings)

        set_overlay(farmer['id'],
            entity_type       = 'farmer',
            trade_signal      = sig['signal'],
            last_price_qt     = sig['today_price_qt'],
            signal_updated_at = str(date.today()),
        )

        if sig['signal'] == 'SELL_NOW':
            # Attach sell_date so lot_matcher can filter traders available that day
            farmer_with_sell = dict(farmer)
            farmer_with_sell['sell_date'] = sell_date_str or str(today)
            sell_now_list.append((farmer_with_sell, sig))
            print(f"[trade_signal] SELL_NOW: {farmer['farmer_name']} "
                  f"{farmer['crop']} {farmer['quantity_mt']}MT @ "
                  f"Rs.{sig['today_price_qt']}/qt ({farmer['district']}) "
                  f"sell_date={sell_date_str or today}")

    return sell_now_list