#!/usr/bin/env python3
"""model_board_cost.py -- per-board cost as a function of order quantity.

SINGLE SOURCE OF TRUTH for the numbers render_board_cost.py draws. Prices are fetched from
LCSC product pages and cached to a JSON beside this file, so the figure is reproducible
without hammering the site, and so an unreachable fetch is VISIBLE rather than silently
becoming a stale number.

What is modelled, and why each term is there:

  components   LCSC unit price x qty per board. Fetched, not remembered.
  PCBA fee     JLCPCB charges per JOINT for assembly, plus a per-order engineering fee that
               amortises over quantity. That amortisation is the reason cost-per-board FALLS.
  bare PCB     JLCPCB prices 4-layer 72x80 by quantity with a steep setup component, again
               amortised. Modelled from their published tier behaviour, flagged as APPROX.
  extended     Extended-library parts carry a one-off reel/feed fee PER PART NUMBER per order,
               which is why 14 distinct numbers is not free even at qty 1.

NOT modelled: shipping, tariffs, VAT, DNP savings. Adding them would change every absolute
figure and none of the RELATIVE ranking the operator asked to see.

Every APPROX is labelled as such. The component prices are MEASURED.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "board_cost_prices.json")

# line, designator, qty per board, LCSC
BOM = [
    ("U1 ESP32-S3-WROOM-1U-N8R8", "U1", 1, "C2980300"),
    ("SS24", "D_BP1-4,D_HUB1-2", 6, "C50645"),
    ("100uF 1206 10V", "C_BULK", 1, "C312983"),
    ("10uF 0402", "C10,C4", 2, "C15525"),
    ("100nF 0402", "C_HF", 1, "C1525"),
    ("10nF 0402", "C_MON", 1, "C15195"),
    ("10k 0402", "R_BAL1,R_BAL2", 2, "C25744"),
    ("1M 0402", "R_DIV1,R_DIV2", 2, "C26083"),
    ("100R 0402", "R_F1", 1, "C25076"),
    ("4.7M 0402", "R_MON1,R_MON2", 2, "C11906"),
    ("BAT54W", "D1", 1, "C699107"),
    ("U7 TPS7A0233DBVR", "U7", 1, "C5142805"),
    ("PZ254V 1x05", "J_HUB_PV", 1, "C492404"),
    ("PZ254V 1x06", "J_PROG", 1, "C492405"),
]

# Extended-library parts: LCSC/JLC charge a one-off feed fee per distinct number per order.
# These are the 0402 passives and the two pin headers, which are their own generic lines.
EXTENDED = {"C15525", "C1525", "C15195", "C25744", "C26083", "C25076", "C11906",
            "C492404", "C492405"}

# Parts JLC cannot supply or place at all: bought elsewhere, soldered by hand. These are EXCLUDED
# from the JLC component total (the assembler will never buy them) but shown, because they are a
# real part of what the board costs the operator. Unit prices marked APPROX are NOT LCSC figures --
# they are order-of-magnitude estimates and must be replaced with actual vendor quotes before they
# are used for a purchase decision.
HAND_FIT = [
    ("WING_SOCKET_4P", "J_W1..J_W4", 4, "custom edge connector - a board feature, no part to buy",
     0.00),
    ("LoRa2021_Castellated", "U3,U_C", 2, "NiceRF module, not stocked at LCSC", 12.00),  # APPROX
    ("LoRa1280", "U_LORA1280", 1, "NiceRF module, not stocked at LCSC", 11.00),          # APPROX
]

EXTENDED_FEE = 3.00          # USD per extended part number per order (JLC published order)

JOINTS_PER_BOARD = 23        # 23 placements, one joint each for 2-pin parts; see BOM qty sum
JOINT_FEE = 0.0017           # USD per joint (JLC economic PCBA, published)
ENGINEERING_FEE = 8.00       # USD per order, one-off

# Bare PCB, 4-layer, 72x80mm, ENIG, qty tiers. APPROX from published tier behaviour.
def bare_pcb(q):
    if q <= 5:
        return 2.00 * q + 8.0
    if q <= 10:
        return 1.60 * q + 12.0
    if q <= 30:
        return 1.35 * q + 18.0
    return 1.15 * q + 30.0


def fetch(code):
    """Return the FULL quantity-break ladder for a part: [[ladder, usd], ...].

    The old version scraped the first `"price":` field in the page, which is the DEEP BULK price,
    not the price you pay. Measured:
        U1 C2980300   scraped 3.722   but ladder is 5.8426 at qty 1 ... 3.722 only at qty 1300
        U7 C5142805   scraped 0.355   but ladder is 0.5910 at qty 1 ... 0.355 only at qty 1000
    For a 5-board order that understated the costliest part by 36 %. LCSC embeds the real ladder as
    `productPriceList`; that is what this now returns, so quantity dependence is real rather than
    implied.
    """
    url = f"https://www.lcsc.com/product-detail/{code}.html"
    try:
        out = subprocess.run(["curl", "-sL", "--max-time", "25", "-A", "Mozilla/5.0", url],
                             capture_output=True, text=True, timeout=40).stdout
    except Exception:
        return None
    pairs = {}
    # RESTRICT to the first `productPriceList` array. Scanning the whole page catches the ladder
    # blocks of the "alternatives / substitutes" products too, which produces nonsense ladders
    # (measured: C1525 gave 0.2495 -> 0.02 -> 0.0036 across adjacent breaks, three different parts
    # interleaved). The first array is the product on the page.
    m = re.search(r'"productPriceList":(\[.*?\])\s*,\s*"', out, re.S)
    body = m.group(1) if m else out
    for pm in re.finditer(
            r'"ladder":(\d+),"productPrice":"[^"]*","usdPrice":([0-9.]+)', body):
        pairs[int(pm.group(1))] = float(pm.group(2))
    return sorted([l, p] for l, p in pairs.items()) if pairs else None


def unit_price(lad, qty):
    """Unit price when buying `qty` units, from a [[ladder, usd], ...] table.

    Below the lowest break the lowest break's price applies (LCSC does not sell cheaper in small
    numbers); above the highest break the highest break's price applies.
    """
    if not lad:
        return None
    lad = sorted(lad)
    if qty < lad[0][0]:
        return lad[0][1]
    price = lad[0][1]
    for minq, p in lad:
        if qty >= minq:
            price = p
        else:
            break
    return price


def prices():
    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE))
    changed = False
    for _, _, _, code in BOM:
        if code in cache and cache[code]:
            continue
        p = fetch(code)
        cache[code] = p
        changed = True
        print(f"  fetched {code}: {len(p) if p else 0} ladder points")
    if changed:
        json.dump(cache, open(CACHE, "w"), indent=1)
    return cache


if __name__ == "__main__":
    print("fetching price ladders (cached to board_cost_prices.json)")
    px = prices()
    missing = [c for c, v in px.items() if not v]
    if missing:
        print(f"MISSING PRICES: {missing} -- figure must not be drawn with holes")
        sys.exit(1)
    for q in (1, 5, 10, 50):
        comp = sum(unit_price(px[code], qty * q) * qty for _, _, qty, code in BOM)
        print(f"\n  {q:>3} board(s): components ${comp:.4f}/board")
        for line, des, qty, code in sorted(
                BOM, key=lambda r: -unit_price(px[r[3]], r[2] * q) * r[2])[:4]:
            up = unit_price(px[code], qty * q)
            print(f"    ${up * qty:7.4f}  {line:30s} {qty}x @ ${up:.4f} "
                  f"(buying {qty * q})")
    print()
    print("hand-fit (NOT in the JLC total):")
    for line, des, qty, note, est in HAND_FIT:
        print(f"    ${est * qty:7.2f}  {line:24s} {qty}x  {note}")
