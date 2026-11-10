# D_BP2 native placement trial — rejected candidates, not routed

Based on live master 2449ad8a (includes PR525); inspected the v11 probe branch too. Original source board/rules unchanged. This is an isolated v11 investigation using copies of the spec's frozen source, not a v10 edit.

Run `/usr/bin/python3 tracker/hardware/v11_dbp2_native_trial.py` with KiCad 9.0.9. Each copy stays beside the source, preserving relative library paths, with byte-identical matching-basename project and rule sidecars. Native zone refill and severity-all DRC run for baseline, two candidates and planted-short control. No copper removed, rule relaxed or cavity exclusion added. Native DRC evaluates actual copper layers/pad geometry/courtyards: no body-radius, all-layer pad-circle or track-midpoint approximation.

## Results

PR525/spec site (36.5,77), rotation 0, F.Cu, is NOT legal: introduces 3 shorts, 6 copper clearance violations, 1 courtyard overlap (J_W2). No introduced edge-copper violation. Actual pad assignments: D_BP2.1 `/W1_SOLAR_N` at (34.5,77); D_BP2.2 `/W2_SOLAR_N` at (38.5,77). Pad1 shorts J_W2.2/GND and its GND track; pad2 shorts J_W2.3 `/CUT_SENSE_W2`. Six clearances to CUT_SENSE_W2 tracks measure 0.0500–0.1815 mm against the unchanged 0.2000 mm rule.

Nearby trial (36.5,74), rotation 0 also fails: 12 shorts, 6 clearances, 4 hole clearances, 1 courtyard overlap. These two failed samples do NOT establish impossibility elsewhere.

`summary.json` lists introduced violations by type + unordered item UUID identity, with full descriptions and positions, and original/new net-bound pad endpoints. Reports retain all baseline violations and unconnected records. Added GND track physically crossing pad1 produces an additional native short identity beyond the spec-site failures; the test asserts that identity delta, not merely that an already-bad board remains bad.

Goal of one legal candidate was not achieved within this bounded trial. No reconnect route is claimed or prescribed for rejected placements. Original pad coordinates in summary are the old reconnect anchors; the trial leaves existing copper intact. Further placement requires a wider native-geometry search. This milestone falsifies the spec's best-site legality claim, not all top-side placement feasibility.
