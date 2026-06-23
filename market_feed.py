"""
market_feed.py — KrishiSetu Market Price Feed
Fetches modal prices from Agmarknet for Karnataka mandis.
Stores rolling 60-day history in data/market_prices.json.
Also posts records to Bridge market_data report (future).

Run standalone: python market_feed.py
Or called from: trade_signal.py, price_forecast.py
"""

import json, os, requests
from datetime import date, timedelta
from pathlib import Path

DATA_DIR    = os.path.join(os.path.dirname(__file__), 'data')
PRICES_FILE = os.path.join(DATA_DIR, 'market_prices.json')
KEEP_DAYS   = 90    # rolling history window — enough for 60d history + 21d hold forecast

# Mandis relevant to Karnataka horticulture
TARGET_MANDIS = {
    # Defined in advisor.py HORIZON_BY_CROP
    'Tomato':       ['Kolar', 'Chikkaballapur', 'Bengaluru'],
    'Onion':        ['Belgaum', 'Hubli', 'Davanagere'],
    'Mango':        ['Kolar', 'Tumkur', 'Ramanagara'],
    'Banana':       ['Davangere', 'Shivamogga', 'Hassan'],
    'Grapes':       ['Vijayapura', 'Bagalkot'],
    'Pomegranate':  ['Vijayapura', 'Solapur'],
    'Pineapple':    ['Kodagu', 'Chikkamagaluru'],
    # Supported by cold_storage_input.py SUPPORTED_CROPS
    'Potato':       ['Bengaluru', 'Hassan', 'Chikkaballapur'],
    'Carrot':       ['Chikkaballapur', 'Kolar'],
    'Cabbage':      ['Chikkaballapur', 'Bengaluru'],
    'Cauliflower':  ['Chikkaballapur', 'Bengaluru'],
    'Beans':        ['Chikkaballapur', 'Mysuru'],
    # Common Karnataka crops not yet in above lists
    'Watermelon':   ['Vijayapura', 'Bagalkot'],
    'Papaya':       ['Tumkur', 'Chitradurga'],
    'Guava':        ['Kolar', 'Tumkur'],
}


def load_prices():
    if not os.path.exists(PRICES_FILE):
        return []
    with open(PRICES_FILE) as f:
        raw = f.read().strip()
        return json.loads(raw) if raw else []


def save_prices(records):
    os.makedirs(DATA_DIR, exist_ok=True)
    # Keep only last KEEP_DAYS
    cutoff = str(date.today() - timedelta(days=KEEP_DAYS))
    records = [r for r in records if r['date'] >= cutoff]
    with open(PRICES_FILE, 'w') as f:
        json.dump(records, f, indent=2)


def get_prices_for_crop(crop, mandi=None, days=30):
    """
    Return list of price records for a crop, optionally filtered by mandi,
    for the last N days. Sorted oldest → newest.
    """
    all_prices = load_prices()
    cutoff = str(date.today() - timedelta(days=days))
    result = [
        p for p in all_prices
        if p['crop'].lower() == crop.lower()
        and p['date'] >= cutoff
        and (mandi is None or p['mandi'].lower() == mandi.lower())
    ]
    return sorted(result, key=lambda x: x['date'])


def get_latest_price(crop, mandi):
    """Return the most recent price record for a crop+mandi pair, or None."""
    records = get_prices_for_crop(crop, mandi=mandi, days=14)
    return records[-1] if records else None


def fetch_from_agmarknet(crop, state='Karnataka', days_back=7):
    """
    Fetch recent prices from Agmarknet.
    Returns list of dicts: {crop, mandi, date, min_price, max_price,
                             modal_price, arrivals_qt}

    NOTE: Replace the URL and params below with the actual Agmarknet
    endpoint for your state. This is a template — fill in once you have
    API access or use the CSV download approach.
    """
    # Placeholder — swap with real API call
    # Example using eNAM or agmarknet scrape:
    # response = requests.get(
    #     'https://api.enam.gov.in/web/api/trade-data',
    #     params={'commodity': crop, 'state': state},
    #     timeout=10
    # )
    # return parse_response(response.json())

    print(f'[market_feed] fetch_from_agmarknet: not yet connected — using cache only')
    return []


def fetch_mock_prices(crop, mandi, days_back=60):
    """
    Returns synthetic prices for testing before API is connected.
    Generates a realistic trending price curve.
    60 days back gives price_forecast.py enough history for high-confidence forecasts.
    Remove this once real API is working.
    """
    import random
    random.seed(hash(crop + mandi))
    base_prices = {
        'Tomato': 1600, 'Onion': 2200, 'Mango': 3500,
        'Banana': 1800, 'Grapes': 4500, 'Pomegranate': 5000, 'Pineapple': 2800,
        'Potato': 1400, 'Carrot': 1800, 'Cabbage': 900, 'Cauliflower': 1200,
        'Beans': 2000, 'Watermelon': 800, 'Papaya': 1500, 'Guava': 2000,
    }
    base   = base_prices.get(crop, 2000)
    today  = date.today()
    records = []
    price  = base
    for i in range(days_back, -1, -1):
        d     = today - timedelta(days=i)
        delta = random.uniform(-0.04, 0.05)   # ±4% daily swing
        price = max(800, price * (1 + delta))
        arrivals = random.uniform(200, 800)
        records.append({
            'crop':        crop,
            'mandi':       mandi,
            'date':        str(d),
            'min_price':   round(price * 0.88),
            'max_price':   round(price * 1.12),
            'modal_price': round(price),
            'arrivals_qt': round(arrivals),
        })
    return records


def refresh_prices(use_mock=True):
    """
    Main entry point. Called periodically (every 6h) from farmbot.
    Fetches latest prices for all crop+mandi combinations and appends
    to local cache. Set use_mock=False once API is connected.
    """
    existing   = load_prices()
    existing_keys = {(r['crop'], r['mandi'], r['date']) for r in existing}
    new_records   = []

    for crop, mandis in TARGET_MANDIS.items():
        for mandi in mandis:
            if use_mock:
                fetched = fetch_mock_prices(crop, mandi, days_back=60)
            else:
                fetched = fetch_from_agmarknet(crop)

            for rec in fetched:
                key = (rec['crop'], rec['mandi'], rec['date'])
                if key not in existing_keys:
                    new_records.append(rec)
                    existing_keys.add(key)

    if new_records:
        save_prices(existing + new_records)
        print(f'[market_feed] Added {len(new_records)} new price records')
    else:
        print('[market_feed] No new records')


if __name__ == '__main__':
    refresh_prices(use_mock=True)
    prices = get_prices_for_crop('Tomato', mandi='Kolar', days=7)
    for p in prices[-3:]:
        print(p)