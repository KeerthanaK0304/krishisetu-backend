"""
KrishiSetu - Cold Storage Input
Collects capacity and availability info from cold storage operators.
Saves to data/cold_storages.json
"""

import json
import os
import uuid
from datetime import datetime, date, timedelta
from districts import prompt_district

DATA_DIR = "data"
COLD_STORAGE_FILE = os.path.join(DATA_DIR, "cold_storages.json")

SUPPORTED_CROPS = [
    "Tomato", "Onion", "Potato", "Mango", "Banana",
    "Cabbage", "Cauliflower", "Carrot", "Beans", "Grapes", "All"
]


def load_existing():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(COLD_STORAGE_FILE):
        with open(COLD_STORAGE_FILE, "r") as f:
            raw = f.read().strip()
            return json.loads(raw) if raw else []
    return []


def save(records):
    with open(COLD_STORAGE_FILE, "w") as f:
        json.dump(records, f, indent=2, default=str)


def get_input(prompt, validator=None):
    while True:
        value = input(prompt).strip()
        if not value:
            print("  ✗ This field cannot be empty.")
            continue
        if validator:
            result = validator(value)
            if result is not True:
                print(f"  ✗ {result}")
                continue
        return value


def validate_capacity(val):
    try:
        c = float(val)
        if c <= 0:
            return "Capacity must be greater than 0."
        if c > 50000:
            return "Capacity seems very high (max 50,000 MT). Please re-enter."
        return True
    except ValueError:
        return "Please enter a valid number (e.g. 120 or 50.5)."


def validate_days(val):
    try:
        d = int(val)
        if d < 0:
            return "Cannot be a past date (negative days)."
        if d > 365:
            return "More than a year away — max 365 days."
        return True
    except ValueError:
        return "Please enter a whole number of days (e.g. 0 for today, 3 for 3 days from now)."


def validate_duration(val):
    try:
        d = int(val)
        if d <= 0:
            return "Duration must be at least 1 day."
        if d > 365:
            return "Max duration is 365 days."
        return True
    except ValueError:
        return "Please enter a whole number (e.g. 30)."


def validate_rate(val):
    try:
        r = float(val)
        if r < 0:
            return "Rate cannot be negative."
        return True
    except ValueError:
        return "Please enter a valid number (e.g. 150)."


def get_crop_support():
    print("\nWhich crops do you support? (comma-separated)")
    print("Options:", ", ".join(SUPPORTED_CROPS))
    print("Tip: Type 'All' to accept all crops")
    while True:
        raw = input("Crops supported: ").strip()
        if not raw:
            print("  ✗ Please enter at least one crop.")
            continue
        crops = [c.strip().title() for c in raw.split(",")]
        if "All" in crops:
            return ["All"]
        invalid = [c for c in crops if c not in SUPPORTED_CROPS]
        if invalid:
            print(f"  ✗ Unrecognised: {', '.join(invalid)}. Please use the listed crops or 'All'.")
            continue
        return crops


def main():
    print("\n" + "=" * 50)
    print("    KrishiSetu — Cold Storage Registration")
    print("=" * 50)
    print("List your available slots so farmers can be")
    print("matched to your facility at the right time.\n")

    # Facility details
    facility_name = get_input("Facility/company name: ")
    operator_name = get_input("Operator/contact name: ")
    phone = get_input("Phone number: ")
    district_key, district = prompt_district("District where facility is located: ")
    address = get_input("Address or landmark: ")

    # Capacity details
    print("\n--- Slot Availability ---")
    available_capacity_raw = get_input(
        "Available capacity RIGHT NOW (metric tonnes): ",
        validator=validate_capacity
    )
    available_capacity = float(available_capacity_raw)

    print("\nFrom when is this slot available?")
    days_from_now_raw = get_input(
        "Days from today (0 = available now, 3 = available in 3 days): ",
        validator=validate_days
    )
    days_from_now = int(days_from_now_raw)
    available_from = date.today() + timedelta(days=days_from_now)

    duration_raw = get_input(
        "For how many days can you hold stock (e.g. 30): ",
        validator=validate_duration
    )
    available_until = available_from + timedelta(days=int(duration_raw))

    # Crop support
    supported_crops = get_crop_support()

    # Rate
    print("\n--- Pricing ---")
    rate_raw = get_input(
        "Storage rate per MT per day (₹, enter 0 if not decided): ",
        validator=validate_rate
    )
    rate_per_mt_per_day = float(rate_raw)

    # Optional
    print("\n--- Optional ---")
    min_quantity_raw = input("Minimum quantity per booking (MT, press Enter to skip): ").strip()
    min_quantity = float(min_quantity_raw) if min_quantity_raw else None
    notes = input("Any notes (temperature range, loading facility, etc.): ").strip()

    # Build record
    record = {
        "id": str(uuid.uuid4())[:8],
        "registered_at": datetime.now().isoformat(),
        "facility_name": facility_name,
        "operator_name": operator_name,
        "phone": phone,
        "district": district,
        "address": address,
        "available_capacity_mt": available_capacity,
        "available_from": str(available_from),
        "available_until": str(available_until),
        "supported_crops": supported_crops,
        "rate_per_mt_per_day": rate_per_mt_per_day,
        "minimum_quantity_mt": min_quantity,
        "notes": notes or None,
        "status": "available"
    }

    # Confirm
    print("\n--- Confirm Your Details ---")
    print(f"  Facility   : {facility_name} ({operator_name}, {phone})")
    print(f"  Location   : {address}, {district}")
    print(f"  Capacity   : {available_capacity} MT")
    print(f"  Available  : {available_from} to {available_until}")
    print(f"  Crops      : {', '.join(supported_crops)}")
    print(f"  Rate       : ₹{rate_per_mt_per_day}/MT/day")
    if min_quantity:
        print(f"  Min booking: {min_quantity} MT")
    if notes:
        print(f"  Notes      : {notes}")

    confirm = input("\nSave this? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("\nNot saved. Exiting.")
        return

    records = load_existing()
    records.append(record)
    save(records)

    print(f"\n✓ Saved! Your slot ID is: {record['id']}")
    print(f"  Run matcher.py to see farmers looking for storage in your area.\n")


if __name__ == "__main__":
    main()