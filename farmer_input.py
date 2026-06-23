"""
KrishiSetu - Farmer Input
Collects crop, quantity, and harvest readiness info from a farmer.
Saves to data/farmers.json
"""

import json
import os
import uuid
from datetime import datetime, date, timedelta
from districts import prompt_district

DATA_DIR = "data"
FARMERS_FILE = os.path.join(DATA_DIR, "farmers.json")

CROPS = [
    "Tomato", "Onion", "Potato", "Mango", "Banana",
    "Cabbage", "Cauliflower", "Carrot", "Beans", "Grapes"
]


def load_existing():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(FARMERS_FILE):
        with open(FARMERS_FILE, "r") as f:
            raw = f.read().strip()
            return json.loads(raw) if raw else []
    return []


def save(records):
    with open(FARMERS_FILE, "w") as f:
        json.dump(records, f, indent=2, default=str)


def get_input(prompt, validator=None, options=None):
    while True:
        value = input(prompt).strip()
        if not value:
            print("  ✗ This field cannot be empty.")
            continue
        if options and value not in options:
            print(f"  ✗ Please enter one of: {', '.join(options)}")
            continue
        if validator:
            result = validator(value)
            if result is not True:
                print(f"  ✗ {result}")
                continue
        return value


def validate_quantity(val):
    try:
        q = float(val)
        if q <= 0:
            return "Quantity must be greater than 0."
        if q > 10000:
            return "Quantity seems too high (max 10,000 MT). Please re-enter."
        return True
    except ValueError:
        return "Please enter a valid number (e.g. 5 or 2.5)."


def validate_days(val):
    try:
        d = int(val)
        if d < 0:
            return "Days cannot be negative."
        if d > 180:
            return "More than 180 days away — please confirm this is correct (max 180)."
        return True
    except ValueError:
        return "Please enter a whole number of days (e.g. 7)."



def main():
    print("\n" + "=" * 50)
    print("       KrishiSetu — Farmer Registration")
    print("=" * 50)
    print("This helps match your harvest with cold storage")
    print("and transport at the right time.\n")

    # Basic details
    farmer_name = get_input("Your name: ")
    phone = get_input("Phone number: ")
    district_key, district = prompt_district("District (e.g. Kolar, Tumkur): ")
    village = get_input("Village/Taluk: ")

    # Crop details
    print("\n--- Crop Details ---")
    print("Available crops:")
    for i, crop in enumerate(CROPS, 1):
        print(f"  {i}. {crop}")
    print("  (Type the crop name exactly, or enter your own)")

    crop = get_input("Crop name: ")
    quantity_raw = get_input("Expected harvest quantity (in metric tonnes, e.g. 5): ",
                              validator=validate_quantity)
    quantity = float(quantity_raw)

    days_raw = get_input("Days until harvest is ready (e.g. 7 means one week from today): ",
                          validator=validate_days)
    days_until_ready = int(days_raw)
    harvest_date = date.today() + timedelta(days=days_until_ready)

    # Optional: preferred handling
    print("\n--- Preferences (optional, press Enter to skip) ---")
    preferred_storage = input("Preferred cold storage location/area (or press Enter): ").strip()
    notes = input("Any notes (quality, variety, special requirements): ").strip()

    # Build record
    record = {
        "id": str(uuid.uuid4())[:8],
        "registered_at": datetime.now().isoformat(),
        "farmer_name": farmer_name,
        "phone": phone,
        "district": district,        "village": village,
        "crop": crop,
        "quantity_mt": quantity,
        "days_until_ready": days_until_ready,
        "harvest_date": str(harvest_date),
        "preferred_storage_area": preferred_storage or None,
        "notes": notes or None,
        "status": "unmatched"
    }

    # Confirm
    print("\n--- Confirm Your Details ---")
    print(f"  Farmer     : {farmer_name} ({phone})")
    print(f"  Location   : {village}, {district}")
    print(f"  Crop       : {crop}")
    print(f"  Quantity   : {quantity} MT")
    print(f"  Ready on   : {harvest_date} ({days_until_ready} days from today)")
    if preferred_storage:
        print(f"  Preference : {preferred_storage}")
    if notes:
        print(f"  Notes      : {notes}")

    confirm = input("\nSave this? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("\nNot saved. Exiting.")
        return

    records = load_existing()
    records.append(record)
    save(records)

    print(f"\n✓ Saved! Your registration ID is: {record['id']}")
    print(f"  Run matcher.py to check for available cold storage and transport.\n")


if __name__ == "__main__":
    main()