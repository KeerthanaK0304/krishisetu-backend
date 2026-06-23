"""
KrishiSetu - Karnataka Districts
Shared lookup table of district coordinates and validation.
Imported by all input scripts and the matcher.
"""

# Karnataka district centroids (lat, lng)
DISTRICT_COORDS = {
    "bagalkot":         (16.1691, 75.6963),
    "ballari":          (15.1394, 76.9214),
    "belagavi":         (15.8497, 74.4977),
    "bengaluru rural":  (13.0827, 77.5700),
    "bengaluru urban":  (12.9716, 77.5946),
    "bidar":            (17.9104, 77.5199),
    "chamarajanagar":   (11.9261, 76.9437),
    "chikkaballapur":   (13.4355, 77.7315),
    "chikkamagaluru":   (13.3153, 75.7754),
    "chitradurga":      (14.2251, 76.3980),
    "dakshina kannada": (12.8438, 75.2479),
    "davanagere":       (14.4644, 75.9218),
    "dharwad":          (15.4589, 75.0078),
    "gadag":            (15.4166, 75.6271),
    "hassan":           (13.0068, 76.1004),
    "haveri":           (14.7939, 75.3996),
    "kalaburagi":       (17.3297, 76.8343),
    "kodagu":           (12.4244, 75.7382),
    "kolar":            (13.1357, 78.1294),
    "koppal":           (15.3508, 76.1547),
    "mandya":           (12.5218, 76.8951),
    "mysuru":           (12.2958, 76.6394),
    "raichur":          (16.2120, 77.3566),
    "ramanagara":       (12.7157, 77.2816),
    "shivamogga":       (13.9299, 75.5681),
    "tumkur":           (13.3379, 77.1173),
    "udupi":            (13.3409, 74.7421),
    "uttara kannada":   (14.8600, 74.6800),
    "vijayapura":       (16.8302, 75.7100),   # FIX: was aliased to non-existent "bijapur"
    "yadgir":           (16.7720, 77.1383),
}

# Alternate spellings → canonical name
# FIX: removed circular alias vijayapura→bijapur (bijapur not in DISTRICT_COORDS)
# FIX: added chamrajnagar → chamarajanagar
ALIASES = {
    "tumkuru":           "tumkur",
    "bangalore":         "bengaluru urban",
    "bangalore urban":   "bengaluru urban",
    "bangalore rural":   "bengaluru rural",
    "bengaluru":         "bengaluru urban",
    "mysore":            "mysuru",
    "shimoga":           "shivamogga",
    "bellary":           "ballari",
    "belgaum":           "belagavi",
    "gulbarga":          "kalaburagi",
    "bijapur":           "vijayapura",        # bijapur → vijayapura (correct direction)
    "hubli":             "dharwad",
    "hubli-dharwad":     "dharwad",
    "mangalore":         "dakshina kannada",
    "mangaluru":         "dakshina kannada",
    "coorg":             "kodagu",
    "chamrajnagar":      "chamarajanagar",    # FIX: added missing alias
    "chamarajnagar":     "chamarajanagar",    # FIX: added alternate spelling
}

# Display list — canonical names, title-cased, sorted
DISTRICT_LIST = sorted(k.title() for k in DISTRICT_COORDS.keys())


def canonical(name):
    """Return the canonical key for a district name, or None if not found."""
    key = name.strip().lower()
    if key in DISTRICT_COORDS:
        return key
    if key in ALIASES:
        return ALIASES[key]
    return None


def validate_district(name):
    """
    Validate a district name entered by the user.
    Returns (canonical_key, display_name, suggestion_or_None).
    """
    key = canonical(name)
    if key:
        return key, key.title(), None

    low = name.strip().lower()
    candidates = list(DISTRICT_COORDS.keys()) + list(ALIASES.keys())

    substr_matches = [c for c in candidates if low in c or c in low]
    if substr_matches:
        best = min(substr_matches, key=len)
        resolved = canonical(best)
        return None, None, resolved.title() if resolved else best.title()

    def overlap(a, b):
        return sum(1 for c in a if c in b)

    scored = sorted(candidates, key=lambda c: overlap(low, c), reverse=True)
    best = scored[0]
    resolved = canonical(best)
    suggestion = resolved.title() if resolved else best.title()
    return None, None, suggestion


def prompt_district(prompt_text="District: "):
    """
    Interactive prompt that keeps asking until a valid Karnataka district
    is entered. Returns (canonical_key, display_name).
    """
    print(f"\n  Known districts: {', '.join(DISTRICT_LIST)}\n")
    while True:
        raw = input(prompt_text).strip()
        if not raw:
            print("  ✗ Please enter a district name.")
            continue

        key, display, suggestion = validate_district(raw)
        if key:
            print(f"  ✓ Matched: {display}")
            return key, display

        if suggestion:
            confirm = input(
                f"  '{raw}' not recognised. Did you mean '{suggestion}'? (yes/no): "
            ).strip().lower()
            if confirm in ("yes", "y"):
                k2, d2, _ = validate_district(suggestion)
                if k2:
                    return k2, d2
        print("  ✗ District not found. Please type a district from the list above.")