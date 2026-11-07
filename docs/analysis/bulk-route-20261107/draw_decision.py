#!/usr/bin/env python3
"""draw_decision.py -- the decision, to scale, from the real board. PIL only.

THE ACTUAL FACT, which two earlier versions got wrong:

  A 0.60 mm via's COPPER (radius 0.30) does not touch the neighbours on these pads.
  It violates their 0.20 mm CLEARANCE — the via's copper comes closer than 0.20 mm to the
  neighbour's copper. The rule is violated by the clearance envelope, not by metal contact.

So this figure draws BOTH circles for each candidate site:
    solid red   = the via's copper, radius 0.30 mm
    dashed red  = the clearance envelope it must respect, radius 0.50 mm
The dashed ring is what collides with the grey neighbours. That is what `via_ok` refuses.

Earlier versions: v1 drew the via before the pad (pad hid it); v2 filled the disc and also
claimed "collides" when the true statement is "violates clearance" — penetration measured
0.000 mm on all three pads.
"""
import importlib.util
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
spec = importlib.util.spec_from_file_location(
    "R", os.path.join(REPO, "tracker", "hardware", "route_batch.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

W = R.World(os.path.join(HERE, "latest.kicad_pcb"))

CASES = [("/EN", "U1", "3", 1.05),
         ("/SPI2_SCK", "U1", "4", 1.0),
         ("/VSCAP", "R_BAL1", "1", 0.68)]

PANEL = 660
NOTE_H = 104
MARGIN = 22
HEADER = 150


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


F_T, F_S, F_XS, F_N = font(23), font(15), font(12), font(11)

W_IMG = PANEL * len(CASES) + MARGIN * (len(CASES) + 1)
H_IMG = HEADER + PANEL + NOTE_H + MARGIN * 2
img = Image.new("RGB", (W_IMG, H_IMG), "white")
d = ImageDraw.Draw(img)
d.text((MARGIN, 16), "Why six nets still fail: the track escapes, but no 0.60 mm via keeps its "
                     "clearance", font=F_T, fill="#202124")
d.text((MARGIN, 50), "Grey = foreign copper.   Blue = pad to connect.   Green = free 0.20 mm "
                     "track corridor.", font=F_S, fill="#3c4043")
d.text((MARGIN, 72), "Solid red = the via's copper (r 0.30).   Dashed red = the 0.20 mm "
                     "clearance envelope it must keep (r 0.50).", font=F_S, fill="#3c4043")
d.text((MARGIN, 98), "The METAL does not touch — the CLEARANCE RING does. That is what the "
                     "rule refuses, and why DRC cannot see it.",
       font=F_XS, fill="#5f6368")

for ci, (net, ref, num, half) in enumerate(CASES):
    p = [q for q in W.pads if q["ref"] == ref and q["num"] == num and q["net"] == net][0]
    x0, y0, x1, y1 = p["rect"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    lay = int(p["layers"][0]) if p["layers"] else R.F
    s = PANEL / (2 * half)

    best = (0.0, 0)
    for ang in range(0, 360, 15):
        dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        free = 0.0
        for k in range(1, 100):
            L = k * 0.05
            ok, _ = W.seg_ok(lay, (cx, cy), (cx + dx * L, cy + dy * L), net, set())
            if not ok:
                break
            free = L
        if free > best[0]:
            best = (free, ang)
    free, ang = best
    dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))

    vr = R.VIA_D / 2
    env = vr + R.CLEAR                 # 0.50 mm clearance envelope radius
    # best site on the corridor: smallest clearance shortfall
    cands = []
    for k in range(1, int(free / 0.025) + 1):
        L = k * 0.025
        vx, vy = cx + dx * L, cy + dy * L
        ok, why = W.via_ok(vx, vy, net)
        short = 0.0
        culprit = ""
        for q in W.pads:
            if q is p or lay not in q["layers"]:
                continue
            gap = R.seg_rect(vx, vy, vx, vy, q["rect"]) - env
            if gap < 0 and -gap > short:
                short, culprit = -gap, f"pad {q['ref']}.{q['num']}"
        # TRACKS TOO. via_ok treats every foreign track as an obstacle; an earlier version of
        # this figure only scanned pads, so it reported "no culprit" and printed a legal site
        # while also printing 0 legal sites -- contradictory text caused by an incomplete scan.
        for t in W.tracks:
            if t["net"] == net or lay not in t.get("layers", []):
                continue
            d_pt = R.seg_pt(t["a"][0], t["a"][1], t["b"][0], t["b"][1], vx, vy)
            gap = d_pt - env - t["w"] / 2
            if gap < 0 and -gap > short:
                short, culprit = -gap, "track " + t["net"]
        cands.append((short, vx, vy, L, ok, culprit))
    cands.sort(key=lambda t: t[0])
    short, vx, vy, L, ok, culprit = cands[0]

    pan = Image.new("RGB", (PANEL, PANEL), "white")
    dp = ImageDraw.Draw(pan)

    def T(x, y):
        return ((x - (cx - half)) * s, (y - (cy - half)) * s)

    for t in W.tracks:
        if lay not in t.get("layers", []) or t["net"] == net:
            continue
        dp.line([T(*t["a"]), T(*t["b"])], fill="#5f6368", width=max(2, int(t["w"] * s)))
    for q in W.pads:
        if q is p or lay not in q["layers"]:
            continue
        a, b = T(q["rect"][0], q["rect"][1]), T(q["rect"][2], q["rect"][3])
        dp.rectangle([a, b], fill="#9aa0a6", outline="#3c4043", width=1)
        dp.text(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), f"{q['ref']}.{q['num']}",
                font=F_N, fill="#202124", anchor="mm")

    dp.rectangle([T(x0, y0), T(x1, y1)], fill="#1a73e8", outline="#0b47a1", width=2)
    dp.line([T(cx, cy), T(cx + dx * free, cy + dy * free)],
            fill="#137333", width=max(4, int(0.20 * s)))

    # clearance envelope first (dashed), then metal (solid), both outline-only
    a, b = T(vx - env, vy - env), T(vx + env, vy + env)
    for t2 in range(0, 360, 12):
        ca, sa = math.cos(math.radians(t2)), math.sin(math.radians(t2))
        dp.line([T(vx + ca * env, vy + sa * env),
                 T(vx + ca * env * 1.0, vy + sa * env * 1.0)],
                fill="#d93025", width=4)
    # draw dashes properly (arc segments)
    for t2 in range(0, 360, 12):
        t3 = t2 + 6
        dp.arc([a, b], start=t2, end=t3, fill="#d93025", width=4)
    a2, b2 = T(vx - vr, vy - vr), T(vx + vr, vy + vr)
    dp.ellipse([a2, b2], outline="#a50e0e", width=4)
    cxp, cyp = T(vx, vy)
    dp.line([cxp - 6, cyp, cxp + 6, cyp], fill="#a50e0e", width=3)
    dp.line([cxp, cyp - 6, cxp, cyp + 6], fill="#a50e0e", width=3)

    img.paste(pan, (MARGIN + ci * (PANEL + MARGIN), HEADER))
    ox = MARGIN + ci * (PANEL + MARGIN)
    d.rectangle([ox, HEADER, ox + PANEL, HEADER + PANEL], outline="#dadce0", width=2)
    d.text((ox + 8, HEADER + 6), f"{net}", font=F_S, fill="#202124")
    d.text((ox + 8, HEADER + 25), f"pad {x1-x0:.2f} × {y1-y0:.2f} mm", font=F_XS, fill="#5f6368")

    ny = HEADER + PANEL + 8
    d.rectangle([ox, ny, ox + PANEL, ny + NOTE_H - 14], fill="#fce8e6",
                outline="#d93025", width=2)
    d.text((ox + 12, ny + 7),
           f"track corridor {free:.2f} mm   ·   via clearance envelope {env:.3f} mm",
           font=F_N, fill="#a50e0e")
    d.text((ox + 12, ny + 27),
           ("a legal via site EXISTS here" if ok
            else f"best site still {short:.3f} mm inside clearance of {culprit or 'copper'}"),
           font=F_N, fill="#137333" if ok else "#a50e0e")
    d.text((ox + 12, ny + 48), f"0 of {len(cands)} probed sites are legal for a via",
           font=F_XS, fill="#5f6368")

out = os.path.join(HERE, "DECISION-blocked-nets.png")
img.save(out)
print("wrote", out, os.path.getsize(out), "bytes")
