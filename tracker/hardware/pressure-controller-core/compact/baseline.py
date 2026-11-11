#!/usr/bin/env python3
"""Measure the committed 80x60 baseline with the SAME kernels as the candidate.

Read-only: loads the source checkpoint and reports courtyards/space. Writes
baseline.json next to this file so the comparison table in
COMPACT-PLACEMENT-REPORT.md is reproducible.
"""
import json
from pathlib import Path
import pcbnew as pcb
from shapely.geometry import box
import study

HERE = Path(__file__).resolve().parent


def main():
    b = pcb.LoadBoard(str(study.SOURCE))
    fps = list(b.GetFootprints())
    polys = {f.GetReference(): study.courtyard(f) for f in fps}
    outline = box(0, 0, 80, 60)
    total = sum(p.area for p in polys.values())
    inside = sum(p.intersection(outline).area for p in polys.values())
    motor = box(48, 34, 78, 58)
    biggest, where = study.largest_empty_rect(list(polys.values()) + [box(4, -21.025, 52, 0)],
                                              None, 0, 0, 80, 60)
    out = {'board_mm': [80, 60], 'board_area_mm2': 4800.0,
           'references': len(fps),
           'side_counts': {'top': sum(1 for f in fps if f.GetLayer() == pcb.F_Cu),
                           'bottom': sum(1 for f in fps if f.GetLayer() == pcb.B_Cu)},
           'courtyard_area_total_mm2': round(total, 3),
           'courtyard_area_inside_board_mm2': round(inside, 3),
           'courtyard_occupancy_percent_inside_board': round(inside / 4800 * 100, 2),
           'free_area_inside_board_mm2': round(4800 - inside, 3),
           'largest_single_empty_rectangle_mm2': biggest,
           'largest_single_empty_rectangle_at_mm': [round(v, 2) for v in where],
           'motor_reservation_mm': [48, 34, 78, 58], 'motor_area_mm2': 720,
           'motor_share_of_board_percent': round(720 / 4800 * 100, 2),
           'tracks': len(list(b.GetTracks())),
           'copper_zones': sum(1 for z in b.Zones() if not z.GetIsRuleArea())}
    (HERE / 'baseline.json').write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
