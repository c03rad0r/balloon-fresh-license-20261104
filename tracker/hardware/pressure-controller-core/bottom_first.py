#!/usr/bin/env python3
"""Route the pressure-controller board BOTTOM-FIRST, in proven batches.

WHY THIS IS A SEPARATE DRIVER AND NOT A ROUTER FLAG

`route_v10_astar.py` (ADR-126, the only permitted routing method) searches over (i, j, layer) and
may use both layers for any net; it has no notion of a "preferred first layer". Bolting a
`--bottom-first` flag onto it would have meant editing the router's search, and AGENTS.md §27
requires any router change to keep `tests/test_router_grid_validator_agreement.py` green — a real
constraint, and the reason this is a driver instead.

The operator's instruction is "bottom copper first, batch proof per batch". The driver implements
exactly that as a NET ORDER plus per-batch verification:

  1. Route in electrically coherent batches and prove each one.

MEASURED LIMIT ON "BOTTOM FIRST" (2026-11-10, this candidate): it cannot be delivered as a
preference on a SINGLE-SIDED board, and the driver does not pretend otherwise.
  * 147 of 147 netted pads: only 19 (13 %) exist on B.Cu. Every other pad is F.Cu-only, and a pad
    that exists only on F.Cu can only be ENTERED from F.Cu -- so each net needs at least one F.Cu
    segment no matter what order or layer bias is used.
  * The router's layer lever `--via-cost` is INERT here: 25 top segments at via-cost 0, 1, 2 and 25.
    Lowering it cannot make the search prefer the back layer.
  * Result on this board: 59 F.Cu segments, 1 B.Cu segment, 2 vias. Reported as measured, not as
    "bottom first".
What WOULD deliver a bottom-first board: two-sided placement (B.Cu pads to land on), or a
layer-preference term in the router's cost function -- a change to ADR-126's router that must keep
tests/test_router_grid_validator_agreement.py green, and is not made here.
  2. After every batch, run `batch_proof.py`: native DRC must show no hard violation class, and the
     per-net open count must not rise against the previous batch. A batch that adds copper and
     closes nothing is REJECTED and the board reverts to the last accepted checkpoint.

WHAT IT REFUSES
  * it will not pass `--nets` names that are not in the board's net list;
  * it will not report a batch as accepted unless `batch_proof.py` returns 0;
  * it never claims a routed board is fab-ready: opens are reported as measured numbers.

USAGE
    bottom_first.py --board routing/route.kicad_pcb [--batch N] [--dry-run]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pcbnew as pcb

HERE = Path(__file__).resolve().parent
HW = HERE.parent
ROUTER = HW / 'route_v10_astar.py'
PY = sys.executable

# Nets are grouped so each batch is a coherent electrical function, not an alphabetical slice.
# Bottom-natural nets first: their pads live on B.Cu (the module's thermal/ground pads and the
# buck's bottom lands), so laying them early is what "bottom copper first" means physically.
# GND and +3V3 are RAILS: route_v10_astar defers them to copper pours (RAILS = ("GND", "+3V3")).
# This candidate has NO copper pour zones -- only the one rule area -- so a rail cannot be routed
# and a pour does not exist to carry it. They are therefore NOT in a routing batch here and their
# opens stay open until pours are added as deliberate work. Listing them would only produce a
# batch that cannot succeed while looking like it tried.
BATCHES = [
    ('power', ['/USB5V', '/BUCK_SW', '/BUCK_FB']),
    ('usb', ['/USB_DN', '/USB_DP', '/USB_DN_CONN', '/USB_DP_CONN', '/CC1', '/CC2']),
    ('control', ['/EN', '/BOOT']),
    ('i2c', ['/I2C_SCL', '/I2C_SDA']),
]


def pads_by_layer(board):
    """Net -> set of copper layer names its pads actually occupy."""
    out = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            n = p.GetNetname()
            if not n:
                continue
            out.setdefault(n, set()).update(
                pcb.LayerName(l) for l in p.GetLayerSet().Seq()
                if pcb.LayerName(l) in ('F.Cu', 'B.Cu'))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board', default=str(HERE / 'routing' / 'route.kicad_pcb'))
    ap.add_argument('--batch', type=int, default=0, help='run batches 0..N inclusive')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--expect-footprints', type=int, default=26)
    args = ap.parse_args()

    board = Path(args.board)
    if not board.exists():
        raise SystemExit(f'no board at {board}')
    b = pcb.LoadBoard(str(board))
    layers = pads_by_layer(b)
    # GetNetsByName() returns wxString keys, which do NOT compare equal to Python str, so a bare
    # set membership test reported EVERY planned net as missing. Convert once at the boundary.
    known = {str(k) for k in b.GetNetsByName().keys()}
    del b

    planned = [n for _label, nets in BATCHES for n in nets]
    missing = [n for n in planned if n not in known]
    if missing:
        raise SystemExit(f'REFUSED: planned nets not on the board: {missing}')

    # Report the bottom-natural claim instead of asserting it.
    print('net layer census (pads only):')
    for _label, nets in BATCHES:
        for n in nets:
            print(f'  {n:14s} {sorted(layers.get(n, []))}')

    todo = BATCHES[:args.batch + 1] if args.batch else BATCHES
    prev = HERE / 'routing' / f'{board.stem}-batch0.json'
    for i, (label, nets) in enumerate(todo, start=1):
        nets_arg = ','.join(nets)
        print(f'\n=== batch {i} [{label}] nets={nets_arg}')
        if args.dry_run:
            cmd = [PY, str(ROUTER), '--board', str(board), '--nets', nets_arg,
                   '--append' if i > 1 else '--dry-run', '--dry-run',
                   '--expect-footprints', str(args.expect_footprints)]
        else:
            # UNIQUE, BOARD-DERIVED checkpoint names. Using `batchN.kicad_pcb` next to the board
            # collided with the PREVIOUS campaign's files (80x60, a different board entirely), so
            # the restore point was a stale 80x60 board and the "accepted" proofs in batch*.json
            # were DRC runs on that other board. Measured 2026-11-10. Deriving the name from the
            # board stem makes a collision impossible, and the stamp records which board it belongs
            # to so a wrong restore point is visible rather than silent.
            checkpoint = board.with_name(f'{board.stem}-ckpt{i - 1}.kicad_pcb')
            if not checkpoint.exists():
                shutil.copyfile(board, checkpoint)
            cmd = [PY, str(ROUTER), '--board', str(board), '--nets', nets_arg,
                   '--append', '--expect-footprints', str(args.expect_footprints)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        tail = [ln for ln in (r.stdout or '').splitlines() if ln.strip()][-4:]
        for ln in tail:
            print('   ', ln)
        if r.returncode != 0:
            print(f'    ROUTER rc={r.returncode}; stderr tail:')
            for ln in (r.stderr or '').splitlines()[-3:]:
                print('     ', ln)
        if args.dry_run:
            continue

        # A checkpoint that is not THIS board is worse than no checkpoint: it silently restores a
        # different design. Assert the outline matches before the restore is ever needed.
        cb = pcb.LoadBoard(str(checkpoint))
        ob = cb.GetBoardEdgesBoundingBox()
        bb0 = pcb.LoadBoard(str(board)).GetBoardEdgesBoundingBox()
        del cb
        if (round(ob.GetWidth() / 1e6), round(ob.GetHeight() / 1e6)) != \
           (round(bb0.GetWidth() / 1e6), round(bb0.GetHeight() / 1e6)):
            raise SystemExit(
                f'REFUSED: checkpoint {checkpoint.name} is '
                f'{ob.GetWidth() / 1e6:.0f}x{ob.GetHeight() / 1e6:.0f} mm but the board is '
                f'{bb0.GetWidth() / 1e6:.0f}x{bb0.GetHeight() / 1e6:.0f} mm -- it belongs to a '
                f'different design and must not be used as a restore point')

        proof_out = HERE / 'routing' / f'{board.stem}-batch{i}.json'
        pr = subprocess.run([PY, str(HERE / 'batch_proof.py'), '--board', str(board),
                             '--baseline', str(prev), '--label', f'batch{i} {label}',
                             '--out', str(proof_out)], capture_output=True, text=True)
        print('   ', ' | '.join(ln.strip() for ln in (pr.stdout or '').splitlines()
                                if ln.startswith('records') or ln.startswith('per net')
                                or ln.startswith('VERDICT')))
        if pr.returncode != 0:
            print(f'    REJECTED batch {i}: restoring {board.name} from batch{i - 1}')
            for ln in (pr.stdout or '').splitlines():
                if ln.startswith('REJECT'):
                    print('     ', ln)
            shutil.copyfile(checkpoint, board)
            return 1
        prev = proof_out

    print('\nall requested batches accepted; last proof:', prev)
    return 0


if __name__ == '__main__':
    sys.exit(main())
