"""What does the SOT-23-6 CUT_CHANNEL footprint require, pin by pin?

The BOM says "latched cut driver + cut-sense (part TODO(unverified))". ADR-051 2.5 names a
MOSFET (IRLML2502) plus a firmware one-shot and a hardware series gate. But IRLML2502 is a
3-pin SOT-23 and this footprint is SOT-23-6, so the package alone proves it is NOT a bare
MOSFET -- there are three more pins to account for.

Rather than guess a part, derive the PIN-LEVEL requirement from the board: for each pad of the
footprint, which net is attached, and what that implies the pin must do. Any candidate device
must then satisfy all six pin functions, which turns the part choice from a guess into a match.
"""
import pcbnew as p

UM = 1e6
b = p.LoadBoard("docs/analysis/bulk-route-20261107/latest.kicad_pcb")

for ref in ("U_CUT1", "U_CUT2", "U_CUT3", "U_CUT4", "U_HUB_CVT"):
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        print("%s: not found" % ref)
        continue
    fpos = fp.GetPosition()
    print("=== %s  (%s)  at (%.3f, %.3f) ==="
          % (ref, fp.GetFPID().GetLibItemName(), fpos.x / UM, fpos.y / UM))
    print("    pads: %d" % len(list(fp.Pads())))
    rows = []
    for pad in fp.Pads():
        pos = pad.GetPosition()
        rows.append((pad.GetNumber(), pad.GetNetname() or "(none)",
                     pos.x / UM, pos.y / UM,
                     pad.GetSize().x / UM, pad.GetSize().y / UM,
                     pad.GetShape()))
    for num, net, x, y, w, h, sh in sorted(rows, key=lambda r: r[0]):
        print("    pad %-2s net=%-16s at (%7.3f,%7.3f)  %.2fx%.2f  shape=%s"
              % (num, net, x, y, w, h, sh))
    print()
