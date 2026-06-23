"""
KrishiSetu - Transporter Input
Collects vehicle capacity and availability from transporters.
Saves to data/transporters.json
"""

import json
import os
import uuid
from datetime import datetime, date, timedelta
from districts import prompt_district

DATA_DIR = "data"
TRANSPORTERS_FILE = os.path.join(DATA_DIR, "transporters.json")

VEHICLE_TYPES = {
    "1": ("Mini Truck / Tata Ace", 1.5),
    "2": ("Medium Truck (407)", 3.5),
    "3": ("Large Truck (14-wheeler)", 10.0),
    "4": ("Refrigerated Van", 5.0),
    "5": ("Refrigerated Truck", 15.0),
    "6": ("Custom / Other", None),
}


def load_existing():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(TRANSPORTERS_FILE):
        with open(TRANSPORTERS_FILE, "r") as f:
            raw = f.read().strip()
            return json.loads(raw) if raw else []
    return []


def save(records):
    with open(TRANSPORTERS_FILE, "w") as f:
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
        if c > 500:
            return "Capacity seems very high (max 500 MT). Please re-enter."
        return True
    except ValueError:
        return "Please enter a valid number (e.g. 5 or 10.5)."


def validate_days(val):
    try:
        d = int(val)
        if d < 0:
            return "Cannot be negative."
        if d > 90:
            return "Max 90 days ahead."
        return True
    except ValueError:
        return "Please enter a whole number (e.g. 0 for today)."


def validate_rate(val):
    try:
        r = float(val)
        if r < 0:
            return "Rate cannot be negative."
        return True
    except ValueError:
        return "Please enter a valid number."


def validate_distance(val):
    try:
        d = float(val)
        if d <= 0:
            return "Distance must be greater than 0."
        if d > 2000:
            return "Max range is 2000 km."
        return True
    except ValueError:
        return "Please enter a number in km (e.g. 200)."


def pick_vehicle():
    print("\nVehicle type:")
    for key, (name, capacity) in VEHICLE_TYPES.items():
        cap_str = f"{capacity} MT typical" if capacity else "custom capacity"
        print(f"  {key}. {name} — {cap_str}")

    while True:
        choice = input("Select vehicle type (1-6): ").strip()
        if choice not in VEHICLE_TYPES:
            print("  ✗ Please enter a number between 1 and 6.")
            continue
        name, default_capacity = VEHICLE_TYPES[choice]
        return name, default_capacity


def get_operating_districts():
    print("\nWhich districts do you operate in? (comma-separated)")
    print("Example: Kolar, Tumkur, Bengaluru Rural")
    print("Tip: Enter 'All Karnataka' to indicate statewide operation")
    while True:
        raw = input("Districts: ").strip()
        if not raw:
            print("  ✗ Please enter at least one district.")
            continue
        districts = [d.strip().title() for d in raw.split(",")]
        return districts


def main():
    print("\n" + "=" * 50)
    print("     KrishiSetu — Transporter Registration")
    print("=" * 50)
    print("Register your vehicle availability so farmers")
    print("can be connected to storage at the right time.\n")

    # Basic details
    transporter_name = get_input("Your name / company name: ")
    driver_name = input("Driver name (or press Enter if same): ").strip() or transporter_name
    phone = get_input("Phone number: ")
    district_key, base_district = prompt_district("Your base district (where vehicle is located): ")

    # Vehicle
    vehicle_name, default_capacity = pick_vehicle()

    if default_capacity:
        print(f"\nDefault capacity for {vehicle_name}: {default_capacity} MT")
        override = input(f"Your actual capacity in MT (press Enter to use {default_capacity}): ").strip()
        if override:
            while True:
                result = validate_capacity(override)
                if result is True:
                    capacity = float(override)
                    break
                print(f"  ✗ {result}")
                override = input("Capacity (MT): ").strip()
        else:
            capacity = default_capacity
    else:
        capacity_raw = get_input("Enter your vehicle capacity (MT): ", validator=validate_capacity)
        capacity = float(capacity_raw)

    refrigerated_input = input("Is this vehicle refrigerated? (yes/no): ").strip().lower()
    is_refrigerated = refrigerated_input in ("yes", "y")

    # Availability
    print("\n--- Availability ---")
    days_raw = get_input(
        "Days from today you're available (0 = today, 2 = day after tomorrow): ",
        validator=validate_days
    )
    available_from = date.today() + timedelta(days=int(days_raw))

    def validate_active_days(val):
        try:
            d = int(val)
            if d < 1:
                return "Must be at least 1 day."
            if d > 90:
                return "Max 90 days."
            return True
        except ValueError:
            return "Please enter a whole number (e.g. 7)."

    days_active_raw = get_input(
        "How many days will you be available for bookings? (e.g. 7): ",
        validator=validate_active_days
    )
    available_until = available_from + timedelta(days=int(days_active_raw))

    # Operating area
    operating_districts = get_operating_districts()

    max_distance_raw = get_input(
        "Maximum distance you'll travel per trip (km): ",
        validator=validate_distance
    )

    # Rate
    print("\n--- Rate ---")
    rate_raw = get_input(
        "Rate per MT per km (₹, enter 0 if negotiable): ",
        validator=validate_rate
    )

    # Optional
    print("\n--- Optional ---")
    notes = input("Any notes (vehicle number, multi-trip capacity, etc.): ").strip()

    # Build record
    record = {
        "id": str(uuid.uuid4())[:8],
        "registered_at": datetime.now().isoformat(),
        "transporter_name": transporter_name,
        "driver_name": driver_name,
        "phone": phone,
        "base_district": base_district,
        "vehicle_type": vehicle_name,
        "capacity_mt": capacity,
        "is_refrigerated": is_refrigerated,
        "available_from": str(available_from),
        "available_until": str(available_until),
        "operating_districts": operating_districts,
        "max_distance_km": float(max_distance_raw),
        "rate_per_mt_per_km": float(rate_raw),
        "notes": notes or None,
        "status": "available"
    }

    # Confirm
    print("\n--- Confirm Your Details ---")
    print(f"  Transporter : {transporter_name} ({phone})")
    print(f"  Base        : {base_district}")
    print(f"  Vehicle     : {vehicle_name} — {capacity} MT {'(Refrigerated)' if is_refrigerated else ''}")
    print(f"  Available   : {available_from} to {available_until}")
    print(f"  Area        : {', '.join(operating_districts)}")
    print(f"  Max distance: {max_distance_raw} km")
    print(f"  Rate        : ₹{rate_raw}/MT/km")
    if notes:
        print(f"  Notes       : {notes}")

    confirm = input("\nSave this? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("\nNot saved. Exiting.")
        return

    records = load_existing()
    records.append(record)
    save(records)

    print(f"\n✓ Saved! Your transport ID is: {record['id']}")
    print(f"  Run matcher.py to see matching opportunities in your area.\n")


if __name__ == "__main__":
    main()