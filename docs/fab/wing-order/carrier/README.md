# carrier

Solar cell carrier. Six solar-cell solder lands: SC1-SC3 on the front face and
SC4-SC6 on the back face at the same X centres (ADR-065 parallel string), so the
coincident bounding boxes are one cell seen from both sides, not a duplicated part.

The cells have no LCSC number, so this is ordered as a BARE PCB and the cells are
soldered by hand -- which is the purpose of the board.

Two nets are single-pad by design: `GND` (no plane on this board) and `RF_FEED`
(ADR-046 s2.4 V2 provision land).

- board `342187e1`, 184.0 x 25.0 mm, 2-layer
- drill 11 holes: 0.300 mm x 8, 2.200 mm x 3
- gerbers exported with `--no-x2 --subtract-soldermask`
