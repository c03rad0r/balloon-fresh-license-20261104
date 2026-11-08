"""What exactly does U_LORA1280's silkscreen collide with, and can it move?

check_silk.py fails with 3 silk_over_copper items, all on U_LORA1280:
  2x  Segment of U_LORA1280 on F.Silkscreen  <->  (over copper)
  1x  Footprint text of U_LORA1280 (U_LORA1280)  <->  (over copper)

Per AGENTS.md 26 a silk fix may move REFERENCE TEXT and move silk GRAPHICS to the Fab layer. It
must never touch pads, tracks, vias, zones, courtyards, the outline, or connectivity. Moving a
component body outline to F.Fab is lossless and is the documented preferred fix (trimming was
measured to make things WORSE, 9 -> 12 violations).

This reports, per violating silk item: its geometry, what copper it overlaps, and whether the
overlap is a body outline (Fab-layer candidate) or the reference text (movable).
"""
import json
import subprocess

import pcbnew as p

BOARD = '/home/c08r4d0r/worktrees/pr-bulk-route-20261107/docs/analysis/bulk-route-20261107/latest.kicad_pcb'


def main():
    b = p.LoadBoard(BOARD)

    for f in b.GetFootprints():
        if f.GetReference() != 'U_LORA1280':
            continue
        c = f.GetPosition()
        bb = f.GetBoundingBox(False, False)
        print('U_LORA1280  fp=%s at (%.3f,%.3f) rot=%.0f'
              % (f.GetFPID().GetLibItemName(), c.x / 1e6, c.y / 1e6,
                 f.GetOrientationDegrees()))
        print('  courtyard/bbox: (%.2f,%.2f)-(%.2f,%.2f)'
              % (bb.GetLeft() / 1e6, bb.GetTop() / 1e6,
                 bb.GetRight() / 1e6, bb.GetBottom() / 1e6))

        print('\n  silk graphics on F.Silkscreen:')
        for it in f.GraphicalItems():
            if it.GetLayer() != p.F_SilkS:
                continue
            try:
                s, e = it.GetStart(), it.GetEnd()
                w = it.GetWidth()
                print('    %-12s (%7.3f,%6.3f)->(%7.3f,%6.3f) w=%.3f'
                      % (type(it).__name__, s.x / 1e6, s.y / 1e6,
                         e.x / 1e6, e.y / 1e6, w / 1e6))
            except Exception:
                g = it.GetBoundingBox()
                print('    %-12s bbox (%.2f,%.2f)-(%.2f,%.2f)'
                      % (type(it).__name__, g.GetLeft() / 1e6, g.GetTop() / 1e6,
                         g.GetRight() / 1e6, g.GetBottom() / 1e6))

        print('\n  reference field:')
        rf = f.Reference()
        pos = rf.GetPosition()
        print('    text "%s" at (%.3f,%.3f) layer=%s height=%.3f visible=%s'
              % (rf.GetText(), pos.x / 1e6, pos.y / 1e6,
                 b.GetLayerName(rf.GetLayer()), rf.GetTextHeight() / 1e6, rf.IsVisible()))

    # what copper is near U_LORA1280?
    print('\n  copper owned by U_LORA1280 (pads):')
    for f in b.GetFootprints():
        if f.GetReference() != 'U_LORA1280':
            continue
        for q in f.Pads():
            qc = q.GetPosition()
            print('    pad %-3s %-16s (%7.3f,%6.3f) %.2fx%.2f'
                  % (q.GetNumber(), q.GetNetname(), qc.x / 1e6, qc.y / 1e6,
                     q.GetSize().x / 1e6, q.GetSize().y / 1e6))

    # report the gate's own structured view if available
    print('\n  --- check_silk --json ---')
    r = subprocess.run(['/usr/bin/python3', '-B', 'tracker/hardware/check_silk.py',
                        '--board', BOARD, '--json'],
                       cwd='/home/c08r4d0r/worktrees/pr-bulk-route-20261107',
                       capture_output=True, text=True, timeout=900)
    out = (r.stdout or '')
    i = out.find('{')
    if i >= 0:
        print(out[i:i + 1500])
    else:
        print(out[-800:])


if __name__ == '__main__':
    main()
