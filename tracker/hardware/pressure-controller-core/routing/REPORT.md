# Partial routing checkpoint — not fabrication ready

Operator routing sign-off supplied in delegated request on 2026-11-10. Input d942df67,
board SHA256 9ee4f157ae021c8fde5d6b95a7a98d8b6c3d91b6aa0b9b4703fc88a100ff23ed.
Clean worktree verified before changes. No placement, pad/net assignment, sensor orientation,
keepout, motor reservation or project-rule changes.

| Batch | Addition | Native opens before→after | Shorts | Clearance | New violations |
|---|---|---:|---:|---:|---:|
| 1 | /GND B.Cu pour (bottom FIRST) | 77→72 | 0 | 0 | 0 |
| 2 | /GND F.Cu pour | 72→47 | 0 | 0 | 0 |

Both additive batches refilled with pcbnew.ZONE_FILLER then checked with native KiCad 9.0.9 DRC.
Only existing violation: lib_footprint_mismatch U1 (declared silk→Fab move).
Full records in proofs/batch*-drc-*.json; no exclusion of new violation records.
Pours use direct pad connection (not thermal relief), 0.20 mm clearance, 0.25 mm minimum
width and edge inset >0.50 mm. Direct connections require assembly/thermal review, particularly
for sensor thermal coupling; electrical closure does not qualify analog or assembly performance.

**Prior connectivity independently rechecked:** object preservation alone is not a sufficient
post-refill connectivity proof. `proofs/batch3-physical-native.json` now contains actual
physical pad partitions for batch0, batch1, batch2 and batch3. Native copper polygons
(including each filled island and holes separately) are intersected per layer, with only
physical through-hole pads joining layers. Both prior pour transitions have zero partition
splits. All 48 GND pads form one physical component in batch2 and batch3. The historical
GetConnectedPads counts are direct adjacency, not transitive zone connectivity evidence.

/GND fully closed. Remaining native opens (47):
/+3V3 19; /BOOT 3; /BUCK_FB 2; /BUCK_SW 1; /CC1 1; /CC2 1; /EN 4;
/I2C_SCL 3; /I2C_SDA 3; /USB5V 4; /USB_DN 1; /USB_DN_CONN 2;
/USB_DP 1; /USB_DP_CONN 2.

Native per-net records changed /BOOT 2→3 and /EN 3→4 while /USB5V 6→4:
this is recorded, not hidden. No pre-existing copper changed; raw DRC spanning-edge accounting
is not identical to endpoint connectivity. Do not infer newly broken pairs from these counts.

## Stop / rejected attempt

A third attempt using a thin driver over docs/analysis/bulk-route-20261107/route_batch.py
requested /USB5V C4.1→U2.2 with 30-second search deadline, external 90-second timeout.
Search returned deadline after 36.03 seconds, wrote NO copper. Accepted state remains batch2,
47 opens; USB and I2C routing NOT completed. proofs/route-batch3.json retains actual result.

Inspection found tooling limitations: the driver enumerated board.Zones() only (one keepout),
missing THREE footprint-local keepouts on U1/U3/U4. Upstream router also does not model filled
zones as obstacles. It is therefore unsafe to use for further routing without correction and
negative controls. Driver removed rather than publishing it as safe. This is a **tooling wall**,
NOT evidence of a physically unroutable net. No exact physical obstacle has been established.
Measured U2.2 copper bounds x11.8…12.3, y42.625…42.875 mm; adjacent U2.1 y42.125…42.375
and U2.3 y43.125…43.375. A deadline is not proof this escape is impossible.
Freerouting 2.5.0 available under /opt/freerouting; not used for an accepted batch.

Exploratory pours before accepted batches were not promoted: thermal F.Cu GND produced seven
starved_thermal records (U4.3, J1.A1, J1.B12, U3.3, U3.4, U3.5, U2.1), each required two spokes,
actual one. A full +3V3 top pour displaced GND and was rejected. Accepted direct-connection
GND pours have none of these records; no DRC/project floors were changed.

## Reproduce

Run from this directory with /usr/bin/python3 (pcbnew 9.0.9):

```
python3 pour_stage.py batch0.kicad_pcb --net /GND --layer B.Cu --out batch1.kicad_pcb --report proofs/pour-batch1.json
python3 verify_batch.py batch1.kicad_pcb --before batch0.kicad_pcb --label batch1 --out proofs/batch1.json
python3 pour_stage.py batch1.kicad_pcb --net /GND --layer F.Cu --out batch2.kicad_pcb --report proofs/pour-batch2.json
python3 verify_batch.py batch2.kicad_pcb --before batch1.kicad_pcb --label batch2 --out proofs/batch2.json
python3 check_preservation.py
```

## Accepted batch3 — short buck switch node

Clean ownership checked at 9ea4df60 (PR #542); no competing routing process found.
One exact native pad-centre segment closes /BUCK_SW: U2.7 (13.95,42.75) to
L1.1 (16.23,42.75), F.Cu, 2.28 mm length, 0.20 mm width, no vias. This is a
bounded electrical-connectivity checkpoint, NOT regulator-current/EMI qualification.
Bottom-first pour sequence remains 77→72→47; this batch is **47→46 native opens**.
Native post-refill DRC: zero shorts, zero clearance, exact new violation records **[]**;
only unchanged U1 library footprint mismatch remains. No prior physical partition splits.
All 92 original non-zone objects and zone definitions remain unchanged, including
antenna/local keepouts and motor reservation. Fill polygons were allowed to regenerate,
then connectivity was remeasured. No placement, rules, or thermal-policy change.

The unsafe router remains removed. `short_buck_batch.py` uses native KiCad refill +
full-board DRC as the geometry acceptance oracle, not an incomplete custom obstacle map.
Negative control deliberately routes via U2.6 (+3V3): rejected with two native
shorting_items and two solder_mask_bridge records, all exact item UUIDs retained in
`proofs/rejected-buck-native-after.json`. Negative physical-graph control removes fills
and correctly detects a GND split (`proofs/batch3-controls.json`).
The physical graph uses native polygonization at 100 nm maximum error; it fails closed
on vias (none exist in these boards), and is scoped to this two-copper-layer board.

Reproduce: `/usr/bin/python3 short_buck_batch.py` then
`/usr/bin/python3 test_physical_partitions.py`. Native JSON proofs include exact UUID
identities (KiCad violations have no separate violation UUID). Current renders are
`batch3-top.png/svg` and `batch3-bottom.png/svg`; old top/bottom images remain historical.
Direct GND pad-connect caveat remains: **no thermal or assembly approval**.

placement/core-placement.kicad_pcb now equals batch3.kicad_pcb. Original unrouted placement
proofs are historical; do NOT regenerate placement.py over the routed file. Routing-specific
proofs and batch-labelled renders are here; top.png/top.svg and bottom.png/bottom.svg
are historical (batch2), not the latest board. See manifest.json and the newest batch below.
No flashing, purchases or actuation. No completed-controller, USB SI, regulator-current,
sensor-thermal or fabrication-readiness claim.

## Accepted batches 4 and 5 — independent CC terminations

Clean ownership verified at exact ee571459ebfa9cd46e3b8aca993e3db2c892a675;
PR #542 remote tip matched and no other routing/KiCad process was found.
Fixed placement and bottom-first sequence preserved. No unsafe router or search used.

| Batch | Net / endpoints | Native opens | Net opens | New violations |
|---|---|---:|---:|---:|
| 4 | /CC1: J1.A5 → R3.1 (5.1k 1%) | 46→45 | 1→0 | 0 |
| 5 | /CC2: J1.B5 → R4.1 (5.1k 1%) | 45→44 | 1→0 | 0 |

Each uses two 0.20 mm F.Cu segments, exiting the native connector pad bounding box
horizontally with 0.30 mm margin before heading to its resistor. No vias or via-in-pad.
A first straight-line CC1 candidate failed native clearance (0.0954 mm vs 0.20 mm)
at J1.B8 and was not promoted; the bounded pad-exit construction passed.
After every accepted batch: native refill, full native DRC, exact violation-record delta,
physical polygon partitions (filled islands and holes included), immutable pre-existing
objects/zone definitions/project checks. Zero shorts/clearances, zero prior partition
splits, zero unintended partition changes on every non-target net. GND and BUCK_SW
remain connected and their existing copper is unchanged. Only existing U1 library
footprint mismatch remains. Copper fills regenerate; placement, netlist, keepouts and
rules do not change. The physical graph is same-net partition evidence; cross-net
short rejection is the complementary native DRC gate, not an inference from that graph.

Illegal control `/CC1` through R3.2 GND is rejected despite reducing opens: native
DRC reports two shorting_items and three solder_mask_bridge records (also intersects
J1.B8). Exact records and rejected board retained under rejected-cc* / proofs/.
Reproduce: `/usr/bin/python3 cc_batch.py` (fails closed before promotion).

Remaining 44 native opens: /+3V3 19; /BOOT 3; /BUCK_FB 2; /EN 4;
/I2C_SCL 3; /I2C_SDA 3; /USB5V 4; /USB_DN 1; /USB_DN_CONN 2;
/USB_DP 1; /USB_DP_CONN 2. Per-net before/after and full physical partitions are in
proofs/batch4-physical-native.json and proofs/batch5-physical-native.json.
Current placement/core-placement.kicad_pcb equals batch5.kicad_pcb; renders are
batch5-top.png/svg and batch5-bottom.png/svg. Historical renders remain labelled.

### BUCK_SW power-layout warning — still unresolved

The prior 2.28 mm × 0.20 mm U2.7→L1.1 segment is untouched and electrically closed,
**not power-qualified**. TI TPS6216x datasheet SLVSAM2E (Rev. E, May 2017),
[§11.1 Layout Guidelines, p26 and Figure 42](https://www.ti.com/lit/ds/symlink/tps62160.pdf),
says switched-load-current paths should be “as short and wide as possible”, narrow
traces should be avoided, and the SW→inductor→output capacitor→PGND loop area
minimized. Input capacitor VIN/PGND paths also must be short and wide; sensitive
FB/VOS wiring must stay away from SW. The part supports up to 1 A output (§1/§3),
which is not evidence this 0.20 mm trace is suitable. TI gives no universal numeric
minimum SW width here: review actual load plus inductor ripple/peak current, copper
thickness, allowed rise/drop, and complete high-di/dt loop geometry before approval.
This batch neither widens the switch path nor modifies placement; regulator-current,
thermal/EMI and assembly qualification remain explicit open requirements.
