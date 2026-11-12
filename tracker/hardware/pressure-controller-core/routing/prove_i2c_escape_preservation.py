#!/usr/bin/env python3
"""Prove the I2C escape batch breaks no previously-connected pair.

METHOD (the one this campaign already uses, not a new one): physical copper polygon partitions
from `physical_partitions.py` -- native KiCad polygonization at 100 nm maximum error, individual
filled islands and holes, vias modelled as barrels. A "split" is a group of pads that shared a
copper component BEFORE and does not fit inside any component AFTER. Any split means copper that
used to connect two pads no longer does, which no open-count improvement can excuse.

Two negative controls run in the same process, because a proof that cannot fail is not a proof:
  * removing a GND fill must split /GND (the graph detects real disconnection), and
  * the UNMODIFIED before-board against itself must split nothing (not always-red).
"""
import json
import subprocess
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import physical_partitions as P  # noqa: E402

BEFORE = ROOT / 'route-ckpt3.kicad_pcb'      # board of record before this batch (69 opens)
AFTER = ROOT / 'route.kicad_pcb'             # board of record with the I2C escape batch


def main():
    before = P.partitions(BEFORE)
    after = P.partitions(AFTER)
    broken = P.splits(before, after)
    print(f'pads-bridged pairs  before={P.pairs(before)}  after={P.pairs(after)}')
    print(f'previously-connected pairs BROKEN: {len(broken)}')
    for b in broken:
        print('  BROKEN', b['net'], b['pads'])

    # control 1: the proof must be able to see a real disconnection. A GND-fill control is VACUOUS
    # here -- this candidate has no pour zones at all, so removing fills changes nothing and the
    # control would "pass" while testing nothing (measured: it failed exactly this way). The
    # control therefore strips the copper of a net that IS connected by tracks in this batch and
    # requires the graph to report the split.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        cut = Path(tmp) / 'noscl.kicad_pcb'
        subprocess.run([sys.executable, '-c', (
            'import pcbnew,sys\n'
            'b=pcbnew.LoadBoard(sys.argv[1])\n'
            'net=sys.argv[3]\n'
            'for t in [t for t in b.GetTracks() if t.GetNetname()==net]:\n'
            '    b.Remove(t)\n'
            'pcbnew.SaveBoard(sys.argv[2],b)\n'), str(AFTER), str(cut), '/I2C_SCL'], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ctl_cut = P.partitions(cut)
        remaining = [t for t in pcbnew.LoadBoard(str(cut)).GetTracks() if t.GetNetname() == '/I2C_SCL']
        assert not remaining, f'CONTROL precondition failed: {len(remaining)} /I2C_SCL items remain'
        ctl = P.splits(after, ctl_cut)
        assert any(x['net'] == '/I2C_SCL' for x in ctl), \
            'CONTROL FAILED: stripping /I2C_SCL copper did not split /I2C_SCL -- graph is blind'
        print(f'CONTROL PASS  stripping /I2C_SCL copper splits /I2C_SCL ({len(ctl)} group(s))')

    # control 2: not always-red
    assert not P.splits(before, before), 'CONTROL FAILED: the before-board splits against itself'
    print('CONTROL PASS  before-board vs itself splits nothing')

    if broken:
        print('VERDICT REJECT  previously-connected pairs were broken')
        return 1
    print('VERDICT PASS  zero previously-connected pairs broken')
    return 0


if __name__ == '__main__':
    sys.exit(main())
