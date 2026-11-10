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

**Zero previously-connected pairs broken:** proofs/preservation.json proves all 93 baseline
objects preserved in batch1 and all 94 batch1 objects preserved in batch2, including every
footprint/pad/net/pose, setup, outline, reservation and existing filled polygon. Only one new
zone each time. Additive copper cannot sever prior connectivity. The GetConnectedPads counts
in batch proofs are direct pad adjacency only, NOT a complete transitive zone connectivity
proof; preservation is the authoritative no-break proof for these two additive batches.

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

placement/core-placement.kicad_pcb now equals batch2.kicad_pcb. Original unrouted placement
proofs are historical; do NOT regenerate placement.py over the routed file. Routing-specific
proofs and current renders are here: top.png/top.svg, bottom.png/bottom.svg, manifest.json.
No flashing, purchases or actuation. No completed-controller, USB SI, regulator-current,
sensor-thermal or fabrication-readiness claim.
