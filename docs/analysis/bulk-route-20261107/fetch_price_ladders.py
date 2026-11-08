"""Extract LCSC's real quantity-break price ladder for each BOM part.

The model's old regex grabbed the FIRST `"price"` field in the page, which is not the ladder price
(U1: 3.722 vs a real 5.8426 at ladder 1). LCSC embeds `productPriceList`: an array of
{ladder, productPrice, usdPrice} giving the price at each quantity break. That is the actual
quantity-dependent cost, so a per-board-vs-quantity model should use it rather than a single number.

Writes board_cost_ladders.json: {code: [[ladder, usd], ...]}
"""
import json
import os
import re
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "board_cost_ladders.json")

CODES = ["C2980300", "C50645", "C15008", "C15525", "C1525", "C15195", "C25744",
         "C26083", "C25076", "C11906", "C699107", "C5142805", "C492404", "C492405"]

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120 Safari/537.36")


def fetch(code):
    return subprocess.run(
        ["curl", "-sL", "--max-time", "30", "-A", UA,
         "https://www.lcsc.com/product-detail/%s.html" % code],
        capture_output=True, text=True).stdout


ladders = {}
for code in CODES:
    h = fetch(code)
    # productPriceList is a JSON array embedded in the page; pull each {ladder, usdPrice} pair.
    m = re.search(r'"productPriceList":(\[.*?\])\s*,\s*"', h, re.S)
    pairs = []
    if m:
        body = m.group(1)
        for pm in re.finditer(
                r'\{"ladder":(\d+),"productPrice":"[^"]*","usdPrice":([0-9.]+)', body):
            pairs.append([int(pm.group(1)), float(pm.group(2))])
    if not pairs:
        # fall back to any ladder/usdPrice pairs anywhere in the page
        for pm in re.finditer(r'"ladder":(\d+),"productPrice":"[^"]*","usdPrice":([0-9.]+)', h):
            pairs.append([int(pm.group(1)), float(pm.group(2))])
    seen = {}
    for lad, usd in pairs:
        seen[lad] = usd
    ladders[code] = sorted([l, p] for l, p in seen.items())
    print("%-9s %s" % (code, ladders[code][:6]))
    time.sleep(0.35)

json.dump(ladders, open(OUT, "w"), indent=1)
print("\nwrote %s (%d parts)" % (OUT, len(ladders)))
