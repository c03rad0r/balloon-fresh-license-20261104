#!/usr/bin/env python3
"""Print a labelled free/blocked map for one net on B.Cu, so a blocked pair
can be diagnosed instead of guessed at."""
import sys

import numpy as np
import pcbnew as k
import shapely

sys.path.insert(0, '/home/c08r4d0r/.hermes/profiles/manager/cache/scratch/solar-fix')
import route2 as R  # noqa: E402

BOARD = sys.argv[1]
NET = sys.argv[2]
X0, Y0, X1, Y1 = [float(v) for v in sys.argv[3:7]]

b = k.LoadBoard(BOARD)
poly = R.board_polygon(b)
inside = poly.buffer(-(R.EDGE + R.HALF))
bad = R.forbidden(b, NET, R.LAYER)
xs, ys, mask = R.grid_and_mask(inside, bad, (X0, Y0, X1, Y1))
print(f'net {NET} on {R.LAYER}; x {X0}..{X1}, y {Y0}..{Y1}, grid {R.GRID}')
for j in range(len(ys) - 1, -1, -1):
    print(f'{ys[j]:6.1f} ' + ''.join('#' if mask[j, i] else '.' for i in range(len(xs))))
print('       ' + ''.join(str(int(round(x * 10)) % 10) for x in xs))
