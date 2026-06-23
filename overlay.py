"""
overlay.py — standalone status overlay helpers.
Extracted from farmbot.py to avoid circular imports with trade_signal.py.
"""
import os, json

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(BASE_DIR, 'data', 'status_overlay.json')

def load_overlay():
    if not os.path.exists(STATUS_FILE):
        return {}
    with open(STATUS_FILE, 'r') as f:
        raw = f.read().strip()
        return json.loads(raw) if raw else {}

def save_overlay(overlay):
    with open(STATUS_FILE, 'w') as f:
        json.dump(overlay, f, indent=2, default=str)

def set_overlay(record_id, **kwargs):
    overlay = load_overlay()
    entry   = overlay.get(record_id, {})
    entry.update(kwargs)
    overlay[record_id] = entry
    save_overlay(overlay)