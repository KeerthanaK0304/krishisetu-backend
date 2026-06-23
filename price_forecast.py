"""
price_forecast.py — KrishiSetu Price Forecaster
Given historical price data for a crop+mandi, estimate prices
for the next N days. Used by trade_signal.py.
"""

from datetime import date, timedelta
from market_feed import get_prices_for_crop


def moving_average(values, window):
    if len(values) < window:
        return sum(values) / len(values) if values else 0
    return sum(values[-window:]) / window


def trend_slope(values):
    """
    Simple linear regression slope over a list of values.
    Positive = rising, negative = falling.
    Returns slope per day (in same units as values).
    """
    n = len(values)
    if n < 2:
        return 0
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    num    = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    den    = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den != 0 else 0


def supply_pressure(crop, district, target_date, all_farmers):
    """
    How much of the same crop is competing for the same mandi near this date?
    Returns a 0–1 pressure index (0 = no competition, 1 = very high).
    Re-uses the logic pattern from advisor.py's competing_mt_on().
    """
    from matcher import haversine_km, get_coords
    MAX_COMPETE_KM = 150

    farmer_coords = get_coords(district)
    total_competing = 0.0
    for f in all_farmers:
        if f.get('crop','').lower() != crop.lower():
            continue
        try:
            h = date.fromisoformat(str(f['harvest_date']))
        except (KeyError, ValueError):
            continue
        if abs((h - target_date).days) > 3:
            continue
        if farmer_coords:
            fc = get_coords(f.get('district',''))
            if fc:
                km = haversine_km(farmer_coords[0], farmer_coords[1], fc[0], fc[1])
                if km > MAX_COMPETE_KM:
                    continue
        total_competing += f.get('quantity_mt', 0)

    # Pressure index: every 100 MT of competing supply = 0.1 pressure
    return min(1.0, total_competing / 1000)


def forecast_price(crop, mandi, days_ahead, all_farmers=None, farmer_district=None):
    """
    Forecast modal price for crop at mandi, N days from today.

    Returns dict:
        forecast_price_qt   — estimated modal price (₹/qt)
        confidence          — 'high' / 'medium' / 'low'
        trend               — 'rising' / 'falling' / 'flat'
        data_points         — how many historical days were used
        supply_pressure     — 0–1 competition index
    """
    history = get_prices_for_crop(crop, mandi=mandi, days=45)
    if not history:
        return {
            'forecast_price_qt': None,
            'confidence':        'low',
            'trend':             'unknown',
            'data_points':       0,
            'supply_pressure':   0.0,
        }

    prices = [r['modal_price'] for r in history]
    today_price = prices[-1]

    # Moving averages
    ma7  = moving_average(prices, 7)
    ma14 = moving_average(prices, 14)

    # Trend direction from slope over last 10 days
    recent = prices[-10:]
    slope  = trend_slope(recent)

    if slope > 30:      trend = 'rising'
    elif slope < -30:   trend = 'falling'
    else:               trend = 'flat'

    # Project forward: apply slope × days, damped toward MA14 (mean reversion)
    projected  = today_price + (slope * days_ahead)
    mean_rev   = ma14
    damp       = min(1.0, days_ahead / 14)   # more reversion for longer horizons
    forecast   = projected * (1 - damp * 0.3) + mean_rev * (damp * 0.3)

    # Supply pressure adjustment — high supply pushes price down
    press = 0.0
    if all_farmers and farmer_district:
        target_date = date.today() + timedelta(days=days_ahead)
        press       = supply_pressure(crop, farmer_district, target_date, all_farmers)
        forecast    = forecast * (1 - press * 0.15)   # up to 15% downward pressure

    # Confidence based on data quality
    if len(history) >= 20 and days_ahead <= 7:   conf = 'high'
    elif len(history) >= 10 and days_ahead <= 14: conf = 'medium'
    else:                                          conf = 'low'

    return {
        'forecast_price_qt': round(forecast),
        'confidence':        conf,
        'trend':             trend,
        'data_points':       len(history),
        'supply_pressure':   round(press, 2),
    }