# interconnect

Per-wing bypass interconnect. Three SS24 (SMA) diodes across the cell string:
SOLAR_P - SOLAR_MID1 - SOLAR_MID2 - SOLAR_N.

These are NOT duplicates of the hub D_BP1..4: the hub carries bypass BETWEEN wings
(W1_P..W1_N..W2_N..W3_N..GND) while this board carries PER-CELL bypass inside one wing.

- board `28aafd9b`, 34.7 x 20.1 mm, 2-layer
- drill 2 holes: 0.400 mm x 2
- gerbers exported with `--no-x2 --subtract-soldermask`
