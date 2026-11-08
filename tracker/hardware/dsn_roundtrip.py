#!/usr/bin/env python3
"""dsn_roundtrip.py -- KiCad <-> freerouting bridge.

`kicad-cli` has no Specctra DSN export (checked: its export subcommands are
brep/drill/dxf/gencad/gerber/ipos/odb/pdf/ply/pos/step/stl/svg/vrml/xao). Only the
pcbnew Python API exposes ExportSpecctraDSN / ImportSpecctraSES, so this wraps them.

The SES import ADDS the routed tracks to the existing board rather than replacing
them, which is what we want: freerouting should only fill in what is missing.

USAGE
  dsn_roundtrip.py export BOARD.kicad_pcb OUT.dsn
  dsn_roundtrip.py import BOARD.kicad_pcb IN.ses OUT.kicad_pcb

Must run under an interpreter that can import pcbnew. On this fleet that is
/usr/bin/python3 (the distro python), NOT the pytest venv.
"""
import sys

import pcbnew

CMD = sys.argv[1] if len(sys.argv) > 1 else ""

if CMD == "export":
    if len(sys.argv) < 4:
        print("usage: dsn_roundtrip.py export BOARD.kicad_pcb OUT.dsn", file=sys.stderr)
        sys.exit(2)
    src, out = sys.argv[2], sys.argv[3]
    ok = pcbnew.ExportSpecctraDSN(pcbnew.LoadBoard(src), out)
    print(f"export {src} -> {out}: {'ok' if ok else 'FAILED'}")
    sys.exit(0 if ok else 1)

if CMD == "import":
    if len(sys.argv) < 5:
        print("usage: dsn_roundtrip.py import BOARD.kicad_pcb IN.ses OUT.kicad_pcb",
              file=sys.stderr)
        sys.exit(2)
    src, ses, out = sys.argv[2], sys.argv[3], sys.argv[4]
    b = pcbnew.LoadBoard(src)
    ok = pcbnew.ImportSpecctraSES(b, ses)
    print(f"import {ses} into {src}: {'ok' if ok else 'FAILED'}")
    if ok:
        pcbnew.SaveBoard(out, b)
        print(f"saved {out}")
    sys.exit(0 if ok else 1)

print(f"unknown command {CMD!r}; use export|import", file=sys.stderr)
sys.exit(2)
