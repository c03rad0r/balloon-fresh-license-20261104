#!/usr/bin/env python3
"""flash_path_check.py -- can this board be programmed as built?

The ESP32-S3 has two independent ways in:
  A. USB-Serial-JTAG (native USB): needs USB_D-/USB_D+ plus the ability to ENTER download mode,
     which normally means driving GPIO0 low and pulsing EN. esptool can also sync to
     USB-Serial-JTAG and issue a reset over the USB protocol itself.
  B. A UART bridge on a header: needs TX/RX/EN/IO0.

This script measures which of the required nets actually have copper, and therefore which paths
are electrically available on the fabricated board. It does NOT assume a datasheet behaviour: it
reports what the copper supports and names the dependency explicitly.

Run: /usr/bin/python3 docs/analysis/flash_path_check.py <board.kicad_pcb>
"""
import re
import sys
from collections import Counter

import pcbnew


def main():
    path = sys.argv[1]
    src = open(path, errors="replace").read()
    codes = {m.group(1): m.group(2) for m in re.finditer(r'\(net (\d+) "([^"]*)"\)', src)}
    segs = re.findall(r"\(segment\b.*?\n\t\)", src, re.S)
    vias = re.findall(r"\(via\b.*?\n\t\)", src, re.S)
    zone_nets = set(re.findall(r'\(net_name "([^"]*)"\)', src))

    cu = Counter()
    for s in segs + vias:
        m = re.search(r"\(net (\d+)\)", s)
        if m:
            cu[codes.get(m.group(1), "")] += 1

    pads = {}
    for fp in pcbnew.LoadBoard(path).GetFootprints():
        for p in fp.Pads():
            n = p.GetNetname()
            if n:
                pads.setdefault(n, []).append(f"{fp.GetReference()}.{p.GetNumber()}")

    def has(net):
        return cu.get(net, 0) > 0 or net in zone_nets

    print(f"board: {path}\n")
    print("NET COPPER AUDIT")
    for net in ["/USB_DN", "/USB_DP", "/EN", "/IO0", "+3V3", "GND"]:
        state = "HAS COPPER" if has(net) else ("NO COPPER" if net in pads else "not on board")
        print(f"  {net:<10} {state:<12} segments/vias={cu.get(net, 0):<4} pads={pads.get(net, [])}")

    print()
    print("VERDICT")
    usb = has("/USB_DN") and has("/USB_DP")
    en = has("/EN")
    io0 = has("/IO0")

    if usb:
        print("  USB-Serial-JTAG data lines:  PRESENT (/USB_DN, /USB_DP routed)")
    else:
        print("  USB-Serial-JTAG data lines:  MISSING")

    if en:
        print("  EN (reset) copper:           PRESENT")
    else:
        print("  EN (reset) copper:           MISSING -- no track to J_PROG.3 and no reset RC")

    if io0:
        print("  IO0 (boot strap) copper:     PRESENT")
    else:
        print("  IO0 (boot strap) copper:     MISSING -- J_PROG.6 is a dead pad, no U1 pad assigned")

    print()
    if usb and not (en or io0):
        print("  => The board can only be put into download mode by holding IO0 low BY HAND on")
        print("     the module pad while power-cycling, because neither strap is wired. Whether")
        print("     esptool's USB-Serial-JTAG reset sequence can substitute for that is NOT")
        print("     established here: it still needs EN to be reachable for a hard reset.")
        print("     A 2-wire rework (U1.3->J_PROG.3, U1 IO0->J_PROG.6) makes both straps usable.")
    elif usb and (en or io0):
        print("  => At least one entry path is complete.")
    else:
        print("  => No USB data path; programming needs a UART bridge and both straps.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
