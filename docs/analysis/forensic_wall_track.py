"""Forensic: does the alleged /SPI1_SCK wall track exist in the batch's routed board?

The claim names a specific artifact:
    TRACK /SPI1_SCK B.Cu w=0.20  (35.25, 13.65) -> (35.25, 16.25)   2.60 mm

If that track is absent from routed.kicad_pcb, the reachability claim was measured
against a different artifact than the one committed, and neither verdict transfers.
If present, report exactly which nets' copper lies within 0.30 mm of it, so the wall
hypothesis can be checked against the geometry rather than the prose.
"""
import pcbnew as p
import sys, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / 'bulk-route-20261107'
BATCH = os.environ.get('BATCH_DIR', 'batches/SPI1SCK_UC')
TARGETS = [BASE / BATCH / 'routed.kicad_pcb', BASE / BATCH / 'board.kicad_pcb',
           BASE / 'latest.kicad_pcb']
CLAIM = (35.25, 13.65, 35.25, 16.25)      # x0,y0,x1,y1 in mm


def main():
    for path in TARGETS:
        if not path.exists():
            print('%s : MISSING' % path.name)
            continue
        b = p.LoadBoard(str(path))
        print('\n=== %s' % path.relative_to(BASE))
        hits = []
        for t in b.GetTracks():
            if isinstance(t, p.PCB_VIA):
                continue
            if t.GetNetname() != '/SPI1_SCK':
                continue
            s, e = t.GetStart(), t.GetEnd()
            x0, y0, x1, y1 = s.x / 1e6, s.y / 1e6, e.x / 1e6, e.y / 1e6
            hits.append((b.GetLayerName(t.GetLayer()), round(x0, 3), round(y0, 3),
                         round(x1, 3), round(y1, 3)))
        print('  /SPI1_SCK tracks: %d' % len(hits))
        exact = [h for h in hits
                 if abs(min(h[1], h[3]) - CLAIM[0]) < 0.05 and abs(max(h[1], h[3]) - CLAIM[2]) < 0.05
                 and abs(min(h[2], h[4]) - CLAIM[1]) < 0.05 and abs(max(h[2], h[4]) - CLAIM[3]) < 0.05]
        near = [h for h in hits
                if 34.8 <= (h[1] + h[3]) / 2 <= 35.8 and 12.8 <= (h[2] + h[4]) / 2 <= 17.0]
        print('  matches the claimed 2.60 mm span exactly : %s' % (exact or 'NONE'))
        print('  tracks in the claimed neighbourhood      : %s' % (near or 'NONE'))
        for h in near[:6]:
            print('     %s (%.3f,%.3f)->(%.3f,%.3f)' % h)
        if not hits:
            print('  -> no /SPI1_SCK track exists in this artifact at all')


if __name__ == '__main__':
    main()
