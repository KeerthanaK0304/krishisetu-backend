"""
run.py — KrishiSetu Terminal Mode
No database, no bridge, no server. Just run from terminal.

Usage:
    python run.py
"""

import os, sys

def menu():
    print("\n" + "=" * 52)
    print("         KrishiSetu — Main Menu")
    print("=" * 52)
    print("  1. Register a Farmer")
    print("  2. Register a Cold Storage")
    print("  3. Register a Transporter")
    print("  4. Run Matcher  (find best matches)")
    print("  5. View saved matches")
    print("  6. Book a Slot  (farmer confirms booking)")
    print("  7. View all bookings")
    print("  8. Harvest Advisory  (14-day outlook for a farmer)")
    print("  9. Refresh market prices")
    print("  T. Run trade signals + lot matcher")
    print("  0. Exit")
    print("=" * 52)
    return input("  Choose: ").strip()


def view_matches():
    import json
    path = os.path.join("data", "matches.json")
    if not os.path.exists(path):
        print("\n  No matches yet. Run option 4 first.")
        return
    with open(path) as f:
        matches = json.load(f)
    if not matches:
        print("\n  No matches found.")
        return
    print(f"\n  {len(matches)} match(es):\n")
    for m in matches:
        print(f"  [{m.get('match_quality','?').upper()}]  {m.get('farmer_name')}  (ID: {m.get('farmer_id')})")
        print(f"    Crop      : {m.get('crop')}  |  {m.get('quantity_mt')} MT  |  Harvest: {m.get('harvest_date')}")
        print(f"    Storage   : {m.get('storage_name') or 'None'}  ({m.get('storage_dist_km','?')} km)")
        print(f"    Transport : {m.get('transporter_name') or 'None'}")
        print()


def view_bookings():
    import json
    path = os.path.join("data", "bookings.json")
    if not os.path.exists(path):
        print("\n  No bookings yet.")
        return
    with open(path) as f:
        bookings = json.load(f)
    if not bookings:
        print("\n  No bookings yet.")
        return
    print(f"\n  {len(bookings)} booking(s):\n")
    for b in bookings:
        print(f"  Booking ID : {b['booking_id']}  [{b.get('status','?').upper()}]")
        print(f"  Farmer     : {b['farmer_name']}  ({b['farmer_phone']})")
        print(f"  Crop       : {b['crop']}  |  {b['quantity_mt']} MT  |  Harvest: {b['harvest_date']}")
        if b.get("storage_name"):
            print(f"  Storage    : {b['storage_name']}  ({b['storage_from']} → {b['storage_until']}, {b['storage_days']} days)")
            print(f"  Cost est.  : ₹{b.get('storage_cost_est', 0):,.0f}")
        if b.get("transporter_name"):
            print(f"  Transport  : {b['transporter_name']}  (blocked {b['transport_block_start']} → {b['transport_block_end']})")
        print(f"  Booked at  : {b.get('booked_at','')[:16]}")
        print()


def main():
    print("\n" + "=" * 52)
    print("       KrishiSetu — Starting up")
    print("=" * 52)
    print("  No database. No bridge. Just your terminal.")

    while True:
        choice = menu()
        if choice == "1":
            import farmer_input;      farmer_input.main()
        elif choice == "2":
            import cold_storage_input; cold_storage_input.main()
        elif choice == "3":
            import transporter_input;  transporter_input.main()
        elif choice == "4":
            import matcher;            matcher.main()
        elif choice == "5":
            view_matches()
        elif choice == "6":
            import booking;            booking.main()
        elif choice == "7":
            view_bookings()
        elif choice == "8":
            import advisor; advisor.main()
            
        elif choice == '9':
            from market_feed import refresh_prices
            refresh_prices(use_mock=True)
            print('\n  Market prices refreshed (mock data).')
        elif choice == "0":
            print("\n  Goodbye!\n")
            sys.exit(0)

        elif choice == 'T':
            from trade_signal import run_signals_for_all_farmers
            from lot_matcher  import match_sell_now_lots, build_trader_alert
            import json
            farmers  = json.load(open('data/farmers.json'))  if os.path.exists('data/farmers.json')  else []
            traders  = json.load(open('data/traders.json'))  if os.path.exists('data/traders.json')  else []
            bookings = json.load(open('data/bookings.json')) if os.path.exists('data/bookings.json') else []
            sell_now = run_signals_for_all_farmers(farmers, traders, bookings)
            matched  = match_sell_now_lots(sell_now, traders)
            for farmer, sig, tlist in matched:
                for t in tlist:
                    print(build_trader_alert(farmer, sig, t))
                    print() 
        else:
            print("  Invalid option, try again.")

if __name__ == "__main__":
    main()


