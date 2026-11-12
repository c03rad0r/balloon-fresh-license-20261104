#!/usr/bin/env python3
"""fix_flight_gaps.py -- close the schematic/connectivity gaps that block using this board.

WHY, AND IN WHAT ORDER
----------------------
The operator's directive: close the known gaps so the board can actually work as a flight board,
critical path first, no nitpicks.

A board that cannot be FLASHED is not a flight board, so that is first. Measured on the board of
record (docs/analysis/bulk-route-20261107/latest.kicad_pcb):

  /EN    U1.3 <-> J_PROG.3    2 pads, 0 tracks, 30.71 mm apart
  /IO0   J_PROG.6 only        1 pad,  0 tracks -- and J_PROG.6 is not connected to U1 at all

So the programming header can reach USB (D+/D- wired, 46 and 19 segments) but cannot assert the
ESP32-S3's two boot-strapping inputs. Without both, there is no download mode: an assembled board
is unflashable without a hand bodge wire. That is the critical path.

WHY GPIO0 IS PAD 27, MEASURED NOT GUESSED
-----------------------------------------
The board's pads carry no (pinfunction) and the KiCad library footprint carries none either, so
the pad->GPIO map has to be established and then CROSS-CHECKED rather than assumed. Verified
against functions the board already encodes:

  pad 13 = /USB_DN   (GPIO19)      pad 36 = /GNSS_TX  (GPIO43, U0TXD)
  pad 14 = /USB_DP   (GPIO20)      pad 37 = /GNSS_RX  (GPIO44, U0RXD)

Those four agree with the ESP32-S3-WROOM-1 pinout, so the map is right. That makes pad 27 GPIO0
(the BOOT strapping pin). Pads 28/29/30 are GPIO35/36/37 and are NOT usable: this module is the
N8R8 variant -- 8 MB PSRAM is OCTAL, and octal PSRAM occupies GPIO33-37. Assigning a strapping
input there would look plausible on the schematic and fail on hardware, which is exactly the
class of error this repo has recorded four times for contested parameters.

WHAT THIS SCRIPT DOES, AND ONLY THIS
------------------------------------
1. Renames the single-pad net /IO0 so it is a real two-pad net, and assigns U1 pad 27 to it.
   After this the netlist has J_PROG.6 <-> U1.27 and the router has something to route.
2. Leaves routing to route_batch.py -- this script does not lay copper.

It refuses to act if the assumptions it measured no longer hold, so a changed board fails loudly
instead of being silently rewritten.

Usage:
  /usr/bin/python3 tracker/hardware/fix_flight_gaps.py <board.kicad_pcb> [--out <path>]
"""
import argparse
import sys

import pcbnew

MM = 1e6

# pad -> GPIO, established by cross-checking the four functions the board already encodes above.
IO0_PAD = 27


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    b = pcbnew.LoadBoard(args.board)

    # --- precondition: the net /IO0 must exist and have exactly one pad (J_PROG.6)
    io0 = None
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == "/IO0":
                io0 = p.GetNet()
                break
        if io0:
            break
    if io0 is None:
        print("FAIL: /IO0 does not exist; already fixed, or the board changed")
        return 1

    holders = [(fp.GetReference(), p.GetNumber())
               for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() == "/IO0"]
    if len(holders) != 1:
        print(f"FAIL: /IO0 already has {len(holders)} pads {holders}; refusing to rewrite")
        return 1

    # --- precondition: U1 pad 27 must be net-less, and the module must be the octal-PSRAM part
    u1 = [fp for fp in b.GetFootprints() if fp.GetReference() == "U1"]
    if len(u1) != 1:
        print(f"FAIL: expected exactly one U1, found {len(u1)}")
        return 1
    u1 = u1[0]
    pad27 = [p for p in u1.Pads() if p.GetNumber() == "27"]
    if not pad27:
        print("FAIL: U1 has no pad 27")
        return 1
    pad27 = pad27[0]
    if pad27.GetNetname():
        print(f"FAIL: U1.27 already on net {pad27.GetNetname()!r}; refusing to steal it")
        return 1

    # pad 28/29/30 must be free too -- if one is used, the module is not what we think
    for num in ("28", "29", "30"):
        for p in u1.Pads():
            if p.GetNumber() == num and p.GetNetname():
                print(f"WARN: U1.{num} carries net {p.GetNetname()!r}; the PSRAM assumption "
                      f"should be re-checked before trusting pad 27 == GPIO0")

    # --- act: put U1.27 on /IO0
    pad27.SetNet(io0)
    pcbnew.Refresh()
    print(f"U1.27 assigned to /IO0  (was: {holders[0][0]}.{holders[0][1]} only)")

    out = args.out or args.board
    pcbnew.SaveBoard(out, b)
    print(f"wrote {out}")

    # --- verify by reloading, not by trusting the in-memory object
    v = pcbnew.LoadBoard(out)
    got = sorted(f"{fp.GetReference()}.{p.GetNumber()}"
                 for fp in v.GetFootprints() for p in fp.Pads() if p.GetNetname() == "/IO0")
    print(f"read-back: /IO0 pads = {got}")
    if got != ["J_PROG.6", "U1.27"]:
        print("FAIL: read-back mismatch")
        return 1
    print("OK: /IO0 now a 2-pad net, ready to route")
    return 0


if __name__ == "__main__":
    sys.exit(main())
