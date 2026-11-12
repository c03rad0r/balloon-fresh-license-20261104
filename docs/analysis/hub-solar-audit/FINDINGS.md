# Hub solar gaps — why the 9 J_W↔bypass-diode pairs have no shared copper layer

**Status:** AUDIT ONLY. No board edit, no repair, no proposed fix.
**Board under audit:** `docs/analysis/hub-repair-20261102/output/after/hub_board_v10_lora1280_7of9.kicad_pcb`
**SHA256:** `94038dd0c4608f28181017599cb7b623dcb85d81f619ec66947fdec2406c1155` — verified **before and after** this audit, unchanged.
**Toolchain:** KiCad `9.0.9-9.0.9~ubuntu24.04.1`, `pcbnew` from `/usr/bin/python3` (distro interpreter), `kicad-cli pcb drc` native.

---

## 0. Verdict up front

The question asked was *"why do the 9 pairs have no shared copper layer?"*

**They do share a copper layer — all of them share `B.Cu`.** The premise "zero shared copper
layers" is an artefact of a measurement error, not a board property. Once the J_W lands are counted
as the footprint actually defines them, **12 of 12** diode↔J_W pairs share `B.Cu` and **0 of 12**
share only `F.Cu`.

Consequently:

| explanation | verdict |
|---|---|
| **(a) diode on wrong board side** | **REJECTED** — the diodes are on `B.Cu` *by design and by ADR-120 R1*, and `B.Cu` is exactly the face where the wing lands live too. |
| **(b) J_W land should be PTH/slot, not SMD** | **REJECTED** — the two outer-face SMD lands are the *specified* interface (`WING-TO-HUB-SOCKET-SPEC.md` §2, "soldered from both sides"). A PTH land would violate ADR-046 §2.2. |
| **(c) connection intended in harness/tab, so pad net assignment is wrong** | **PARTLY CORRECT — this is the operative cause.** The nets are assigned correctly; what is missing is *routing*, because three solar-return nets were never routed in any commit in board history. |
| **(d) real defect from an earlier placement change** | **REJECTED** — no placement change created these; the nets have never carried copper. |

**The single correct answer is (c), in a narrower form than the option states:** the pad/net
assignment is *right*; the interface is completed **in assembly** (the wing tab bridges the two outer
faces when soldered, by design), and the remaining gap is **unrouted board copper on the solar-return
nets**, which was never laid down. These are **not "not board-fixable"** — a `B.Cu` track provably
bridges every one of them (§4).

---

## 1. The measurement error that produced the premise

`Wing_Tab_4P.kicad_mod` defines **8 copper lands per interface**, not 4:

```
(pad "1" smd rect (at  3.0 -2.7) (size 4.0 1.2) (layers "F.Cu" "F.Paste" "F.Mask") ...)
(pad "2" smd rect (at  3.0 -0.9) (size 4.0 1.2) (layers "F.Cu" "F.Paste" "F.Mask") ...)
(pad "3" smd rect (at  3.0  0.9) (size 4.0 1.2) (layers "F.Cu" "F.Paste" "F.Mask") ...)
(pad "4" smd rect (at  3.0  2.7) (size 4.0 1.2) (layers "F.Cu" "F.Paste" "F.Mask") ...)
(pad "1" smd rect (at  3.0 -2.7) (size 4.0 1.2) (layers "B.Cu" "B.Paste" "B.Mask") ...)
(pad "2" smd rect (at  3.0 -0.9) (size 4.0 1.2) (layers "B.Cu" "B.Paste" "B.Mask") ...)
(pad "3" smd rect (at  3.0  0.9) (size 4.0 1.2) (layers "B.Cu" "B.Paste" "B.Mask") ...)
(pad "4" smd rect (at  3.0  2.7) (size 4.0 1.2) (layers "B.Cu" "B.Paste" "B.Mask") ...)
```
— `tracker/hardware/footprints/tracker_mechanical.pretty/Wing_Tab_4P.kicad_mod` lines 13–22.

The footprint's own description says so explicitly: *"4 copper lands on EACH outer face (F.Cu + B.Cu)
= 8 lands per interface"*, and the note file records the reason verbatim: *"the SAME 4 lands on the
BOTTOM face (B.Cu): **the tab is soldered from BOTH sides**"* (`Wing_Tab_4P.md` lines 34–35).

This was deliberate at the very first commit that added the interfaces — `0cd22327 feat(v9 hub): add
the FOUR wing-mount interfaces (ADR-048 / ADR-046)` — and the 8-pad structure has not changed in any
commit since. The slot width changed once (`0.90 → 0.50 mm`, commit `23732906`); the pad set never did.

**Measured on the audited board** (`audit.py`, section `A_pad_duplication`): every J_W pad *number*
resolves to **two distinct `PAD` objects** with **distinct UUIDs**, **identical XY to 0.000000 mm**,
the **same net**, and **disjoint layer sets** (`F.Cu` vs `B.Cu`). Example, `J_W1` pad 4:

```
pad4 uuid=7656e304-0273-4ef0-b688-28439d2db1d0 layers=['F.Cu'] ... net=/W1_SOLAR_N
pad4 (second object, distinct uuid)          layers=['B.Cu'] ... net=/W1_SOLAR_N
```

**So the "contradiction" resolves cleanly:** two physically distinct pads share a number. No net is
misassigned to a face. `J_W1.4` is genuinely reported on `F.Cu` in one record and on `B.Cu` in
another because both objects exist; DRC names whichever instance its connectivity island happens to
reference.

**This is also where the "9 records" count comes from, and it does not reproduce.** DRC groups by
*copper island*, not by pad number. On the audited board the `unconnected_items` array carries **16**
records whose text contains `SOLAR`, and they classify as:

| class | count | records |
|---|---|---|
| diode pad ↔ J_W pad | **8** | 43, 44, 45, 48, 52, 54, 56, 57 |
| J_W `F.Cu` ↔ J_W `B.Cu`, same pad number | **7** | 42, 46, 47, 49, 51, 53, 55 |
| J_W ↔ J_W, different pads, same net | **1** | 50 (`J_W2.4` ↔ `J_W3.1`, `/W2_SOLAR_N`) |

The pinned figure of **9** is not reproducible as stated: the board presents **8** diode↔J_W records,
not 9. The 9th item in the pinned list (`D_BP4.2` ↔ `U2.4`) is a `GND` record and contains no `SOLAR`
net at all — it is analysed separately in §5. The verdict is unaffected either way: every one of the
8 diode↔J_W records, and the 1 J_W↔J_W record, shares `B.Cu`.

---

## 2. The diode side is intentional, not an error

`D_BP1..D_BP4` are on `B.Cu` — placed from the `BACK` dict in `tracker/hardware/build_hub_board_v10.py`
and flipped by `place(..., side="B")` (`fp.Flip(...)`, line 118):

```
D_BP1  B.Cu  orient=0.0    pos=(4.000, 33.000)
D_BP2  B.Cu  orient=-90.0  pos=(29.000, 76.000)
D_BP3  B.Cu  orient=0.0    pos=(68.000, 33.000)
D_BP4  B.Cu  orient=-90.0  pos=(29.000, 4.000)
```

The builder comment for this block reads: *"ADR-129 (sides from the same gate-verified solver run;
see FRONT)"* (line 75), and states these coordinates *"are NOT hand-tuned: they are the output of
`solve_v10_placement.py`"* (lines 29–33).

Back-side placement is mandated by **ADR-120 R1 — Two-sided population**: *"Parts are distributed
over **both sides** of the board. The digital/harvest section occupies the front; the radio sites
(ADR-119) occupy the back."*

ADR-129 D2 fixes the diodes' **net** intent, not their face, and it fixes the *function* precisely:

```
D_BP1  K→W1_SOLAR_P  A→W1_SOLAR_N
D_BP2  K→W1_SOLAR_N  A→W2_SOLAR_N
D_BP3  K→W2_SOLAR_N  A→W3_SOLAR_N
D_BP4  K→W3_SOLAR_N  A→GND
```
— `docs/adr/129-v10-power-restoration-and-bypass-diodes.md` D2, matching
`tracker/hardware/connectivity/v10_pinmap.reg` lines 265–279 and the SS24 class/function entry in
`docs/HANDOVER-WING-RELEASE-AND-BYPASS-DIODE.md` lines 50–64.

**Important:** the earlier note in `docs/fab/DECISIONS-UNROUTED-NETS.md` **D8** ("Keep components
single-sided. Do NOT move parts to `B.Cu`") governs the **v9** hub (`tracker/hardware/hub_board_v9.kicad_pcb`,
59 footprints, 70 × 70). It does **not** apply to v10: ADR-120 R1 supersedes it for v10 and the v10
board carries parts on both faces. Citing D8 against v10 would be a stale-record error.

**Even if one wanted the diodes on `F.Cu`, it would not help:** the `J_W` land is on `B.Cu` too, so an
`F.Cu`-only diode would share *nothing* with either face of the land set. The pairing is
side-compatible as built.

---

## 3. Why the connection is genuinely absent on the board

The electrical chain for each return net is: **diode pad ⇄ J_W land ⇄ wing tab**. The first two links
exist as pads on the same copper layer (`B.Cu`). The third link is the **assembly joint** — the wing
tab is inserted and soldered to both faces (`WING-TO-HUB-SOCKET-SPEC.md` §2: *"the same 4 lands on
BOTH faces of the hub edge (top and bottom), so the wing tab can be soldered from both sides"*;
ADR-046 §4.1: *"inserts 6 mm into the slot and is soldered on both faces"*; ADR-048 §2.2: *"Lands per
interface (both faces) = 8 (4 on F.Cu, 4 on B.Cu)"*).

So the lands do **not** need an on-board F↔B bridge; the tab is that bridge. What is missing is the
**B.Cu copper between the diode pad and the J_W land** — a distance of 40–58 mm per pair.

**Measured: these nets were never routed.** Section `C_solar_routing` of `audit.py`:

```
/W1_SOLAR_P   track_segments=15  vias=1     <- routed (the only solar net that was)
/W1_SOLAR_N   track_segments=0   vias=0
/W2_SOLAR_N   track_segments=0   vias=0
/W3_SOLAR_N   track_segments=0   vias=0
```

And it is not a regression from a placement change. Walking **every commit in the repository that has
ever touched `tracker/hardware/hub_board_v10.kicad_pcb`** and counting track segments per net:

```
23732906  {'/W1_SOLAR_N': 0, '/W2_SOLAR_N': 0, '/W3_SOLAR_N': 0, '/W1_SOLAR_P': 15}
d6b208c1  {'/W1_SOLAR_N': 0, '/W2_SOLAR_N': 0, '/W3_SOLAR_N': 0, '/W1_SOLAR_P': 0}
45e2fb19  {'/W1_SOLAR_N': 0, '/W2_SOLAR_N': 0, '/W3_SOLAR_N': 0, '/W1_SOLAR_P': 0}
afae0c71  {'/W1_SOLAR_N': 0, '/W2_SOLAR_N': 0, '/W3_SOLAR_N': 0, '/W1_SOLAR_P': 0}
...       (30 commits, identical: 0 / 0 / 0)
```

**Zero track segments on all three solar-return nets, in every commit ever made.** The nets were
created by the ADR-129 landing (`45e2fb19`), which added the *pads* — ADR-129 D2's own words: *"The
diode is across a wing's own `SOLAR_P`↔`SOLAR_N`"* and the landing record `45e2fb19` is titled *"25
refs in schematic AND board"*. Routing them was never part of that pass, and no later pass picked them
up.

**Why the router skipped them.** `tracker/hardware/route_v10_astar.py` line 850:

```python
RAILS = ("GND", "+3V3")
if name in RAILS and not want:
    railed.append(name)
    continue
```

Only `GND` and `+3V3` are auto-skipped as rails. The solar-N nets are **not** skipped by name, so the
router *tried* and did not converge — consistent with `docs/analysis/ROUTER-ZERO-OF-NINE-DIAGNOSIS.md`
("Status: **UNRESOLVED**"), which records `route_v10_astar.py` returning `routed 0 / failed 9`. That
diagnosis is about the LoRa1280 interface, but the same non-convergence explains why a 40–58 mm
return path across a board with 782 tracks was never completed by the greedy sequential A*. Per
`docs/fab/ROUTING-DECISION-STOP.md`, the router's non-convergence was a *known, recorded* limitation
("Sequential A* has no backtracking… whichever net routes first wins the contested cells").

So the cause is **incomplete routing**, not a wrong net assignment, not a wrong side, not a wrong land
type, and not a placement regression.

---

## 4. Falsification: "not board-fixable" is false

`docs/analysis/hub-solar-gaps/FINDINGS.md` (merged as `5c7dfd8e`, PR #431) concluded *"the 9 solar
gaps are not board-fixable"* and *"Routeable on a shared layer: 0 of 9"*. That conclusion is wrong,
and this section measures why.

**The layer test was run against one pad instance per pad number**, so it compared the diode's `B.Cu`
pad against the J_W land's `F.Cu` instance and correctly found no shared layer — for the wrong object.
Section `D_summary` of `audit.py` reproduces both readings on the same board:

```
pairs: 12
sharing a layer when ALL instances of each pad number are counted: 12   (all B.Cu)
sharing a layer when only the F.Cu instance of the J_W pad is counted: 0
```

**Direct experiment** (`probe_layer_compat.py`): copy the board, add the *minimum* straight `B.Cu`
tracks — one per net, chaining the net's pads, no A*, no obstacle avoidance — then re-run native DRC
on the copy. Result:

| | unconnected | violations | solar-paired records |
|---|---|---|---|
| baseline (pinned board) | **86** | 38 | 16 |
| after 9 straight `B.Cu` tracks | **77** | 107 | 7 |

Every **diode↔J_W** record closed. The 7 records that remain are exactly the `J_W` **F.Cu↔B.Cu
self-pairs** — i.e. the two faces of one land number, which is the assembly joint, not a routing
target:

```
['Pad 4 [/W1_SOLAR_N] of J_W1 on B.Cu', 'Pad 4 [/W1_SOLAR_N] of J_W1 on F.Cu']
['Pad 1 [/W1_SOLAR_P] of J_W1 on F.Cu', 'Pad 1 [/W1_SOLAR_P] of J_W1 on B.Cu']
...
```

The 107 violations added (`tracks_crossing` 24, `clearance` 22, `solder_mask_bridge` 15,
`shorting_items` 8) are the honest cost of straight lines with no routing — **this proves layer
compatibility only, not routeability, and it is not a fix.** It establishes one thing and only one:
**a `B.Cu` track can reach both ends of every pair**, so the "different outer layers, therefore
unfixable" argument does not hold.

---

## 5. Per-pair verdict

Verdict key: **(c)** = net assigned correctly; the physics is the assembly joint, and the board-level
defect is missing routing. All twelve pad pairs are on the same three nets.

Note the two distinct counting units, because conflating them is what produced the original error:

- **12** = *pad pairs* (diode pin × J_W land on that net). This is the electrical pairing.
- **8** = *DRC records* (§1 table). DRC reports one record per disconnected copper island pair, so
  three of the twelve pad pairs are already joined to their neighbour through existing copper and
  never surface as their own record.

| # | net | diode pad | J_W pad | diode layers | J_W layers | shared | verdict |
|---|---|---|---|---|---|---|---|
| 1 | `/W1_SOLAR_N` | `D_BP1.2` B.Cu | `J_W1.4` F.Cu+B.Cu | B.Cu | F.Cu, B.Cu | **B.Cu** | (c) |
| 2 | `/W1_SOLAR_N` | `D_BP1.2` B.Cu | `J_W2.1` F.Cu+B.Cu | B.Cu | F.Cu, B.Cu | **B.Cu** | (c) |
| 3 | `/W1_SOLAR_N` | `D_BP2.1` B.Cu | `J_W1.4` F.Cu+B.Cu | B.Cu | F.Cu, B.Cu | **B.Cu** | (c) |
| 4 | `/W1_SOLAR_N` | `D_BP2.1` B.Cu | `J_W2.1` F.Cu+B.Cu | B.Cu | F.Cu, B.Cu | **B.Cu** | (c) |
| 5 | `/W2_SOLAR_N` | `D_BP2.2` B.Cu | `J_W2.4` F.Cu+B.Cu | B.Cu | F.Cu, B.Cu | **B.Cu** | (c) |
| 6 | `/W2_SOLAR_N` | `D_BP2.2` B.Cu | `J_W3.1` F.Cu+B.Cu | B.Cu | F.Cu, B.Cu | **B.Cu** | (c) |
| 7 | `/W2_SOLAR_N` | `D_BP3.1` B.Cu | `J_W2.4` F.Cu+B.Cu | B.Cu | F.Cu, B.Cu | **B.Cu** | (c) |
| 8 | `/W2_SOLAR_N` | `D_BP3.1` B.Cu | `J_W3.1` F.Cu+B.Cu | B.Cu | F.Cu, B.Cu | **B.Cu** | (c) |
| 9 | `/W3_SOLAR_N` | `D_BP3.2` B.Cu | `J_W3.4` F.Cu+B.Cu | B.Cu | F.Cu, B.Cu | **B.Cu** | (c) |
| 10 | `/W3_SOLAR_N` | `D_BP3.2` B.Cu | `J_W4.1` F.Cu+B.Cu | B.Cu | F.Cu, B.Cu | **B.Cu** | (c) |
| 11 | `/W3_SOLAR_N` | `D_BP4.1` B.Cu | `J_W3.4` F.Cu+B.Cu | B.Cu | F.Cu, B.Cu | **B.Cu** | (c) |
| 12 | `/W3_SOLAR_N` | `D_BP4.1` B.Cu | `J_W4.1` F.Cu+B.Cu | B.Cu | F.Cu, B.Cu | **B.Cu** | (c) |

`/W1_SOLAR_P` is the one solar net that *is* routed (15 segments, 1 via) and contributes no gap.

### The 9th record is not a solar pair

The pinned brief listed 9 records including *"`D_BP4.2` B.Cu ↔ `U2.4` F.Cu"*. Verified: `D_BP4.2` is
`GND` on `B.Cu`; `U2.4` is `GND` on `F.Cu`. This is a **`GND` plane gap**, not a solar J_W↔diode pair —
it belongs to the D7/D11 zone-island family in `docs/fab/DECISIONS-UNROUTED-NETS.md`, which already
concluded a stitching via does not fix it and that it *"needs a zone/pour-rule change"*. Measured:
`D_BP4.2` sits inside the `F.Cu` and `In1.Cu` GND fill but **not** the `B.Cu` fill; the nearest `B.Cu`
GND zone vertex is **3.869 mm** away and there are **0** `GND` `B.Cu` track endpoints within 3 mm.
It is a distinct finding and is excluded from the solar verdict above.

---

## 6. What is NOT established (honest gaps)

1. **Whether a *legal* route exists for all three nets simultaneously.** The straight-line experiment
   proves layer compatibility, not routeability. A real attempt needs the A* with an obstacle model,
   and `ROUTER-ZERO-OF-NINE-DIAGNOSIS.md` records the router does not converge on this board. **This
   is the one measurement that would settle feasibility** — and it is a routing task, not an audit.
2. **The `D_BP4.2`/`U2.4` GND gap's fix.** Owned by the D7/D11 pour-rule work, not by this audit.
3. **Whether the 3 solar-N nets were ever *intended* to be routed on this revision**, or deliberately
   left for a later pass. ADR-129 D2 mandates the diodes; no record says "route the returns later."
   Absence of a "defer routing" record is evidence they were simply not reached, not evidence they
   were deferred. Nothing in the repo states either explicitly → **INSUFFICIENT** on intent, but the
   *cause* (never routed) is measured and certain.

---

## 7. Reproduce

```bash
cd ~/worktrees/hub-solar-audit

# pad duplex / diode sides / net routing / 12-pair layer table  (+ evidence/solar_audit.json)
/usr/bin/python3 docs/analysis/hub-solar-audit/audit.py

# layer-compatibility falsification on a COPY (+ evidence/solar_bridge.json)
/usr/bin/python3 docs/analysis/hub-solar-audit/probe_layer_compat.py

# source board must still be at the pinned hash
sha256sum docs/analysis/hub-repair-20261102/output/after/hub_board_v10_lora1280_7of9.kicad_pcb
# 94038dd0c4608f28181017599cb7b623dcb85d81f619ec66947fdec2406c1155

# native DRC, on a copy only (the source is never opened for write)
mkdir -p /tmp/solar-drc && cp docs/analysis/hub-repair-20261102/output/after/hub_board_v10_lora1280_7of9.kicad_p* /tmp/solar-drc/
cd /tmp/solar-drc && kicad-cli pcb drc --format json --output drc.json --severity-all hub_board_v10_lora1280_7of9.kicad_pcb
# Found 38 violations / Found 86 unconnected items

# routing history: solar-N track segments in every commit that touched the board
git log --format=%H --all -- tracker/hardware/hub_board_v10.kicad_pcb
```

`audit.py` asserts the pinned hash and **refuses to run** if it has drifted.

---

## 8. Records cited

| record | what it settles |
|---|---|
| `docs/adr/129-v10-power-restoration-and-bypass-diodes.md` D2 | `D_BP1..D_BP4` net intent, SS24 class, hub-side rationale |
| `docs/adr/129` D3 | hub array is an external panel; diodes stay hub-side |
| `docs/adr/120-v10-placement-process.md` R1 | **two-sided population is mandated** — back-face diodes are intentional |
| `docs/adr/046-wing-board-interface.md` §2.2, §4.1 | 4 lands/face, 1.8 mm pitch, "soldered on both faces" |
| `docs/adr/048-v9-hub-wing-interfaces.md` §2.2 | "Lands per interface (both faces) = **8** (4 F.Cu, 4 B.Cu)" — **CITED** |
| `docs/adr/136-flight-wing-interface-two-land-and-routing-sequence.md` §2.1 | pads 1 and 4 are the flight interface; 2/3 retained-unused |
| `docs/adr/137-no-rf-on-hub-antenna-at-module.md` | no RF on hub (does not bear on the solar returns) |
| `docs/WING-TO-HUB-SOCKET-SPEC.md` §2 | 8 lands/interface "so the wing tab can be soldered from both sides" |
| `tracker/hardware/footprints/tracker_mechanical.pretty/Wing_Tab_4P.kicad_mod` | the 8 pad objects; the ground truth of this audit |
| `Wing_Tab_4P.md` lines 34–35 | "the tab is soldered from BOTH sides" |
| `tracker/hardware/connectivity/v10_pinmap.reg` lines 163–185, 265–279 | pad→net source of truth; all assignments correct |
| `tracker/hardware/build_hub_board_v10.py` `FRONT`/`BACK` | `D_BP*` placed from `BACK`, flipped at line 118 |
| `docs/fab/DECISIONS-UNROUTED-NETS.md` D7/D11 | GND zone gaps need a pour-rule change, not a via (the `D_BP4.2`/`U2.4` record) |
| `docs/fab/ROUTING-DECISION-STOP.md` | router non-convergence is recorded, not new |
| `docs/analysis/ROUTER-ZERO-OF-NINE-DIAGNOSIS.md` | A* `routed 0 / failed 9`, status UNRESOLVED |
| `docs/HANDOVER-WING-RELEASE-AND-BYPASS-DIODE.md` lines 50–64 | SS24 part class and diode-to-node mapping |

`docs/fab/DECISIONS-UNROUTED-NETS.md` **D8** ("keep components single-sided") is cited here **only to
record that it does not govern v10** — it is a v9 record, superseded for v10 by ADR-120 R1.

---

## 9. Effect on order/fab status

Unchanged by this audit: the pinned board is **NOT ORDERABLE** (38 violations, 86 unconnected). This
document does not change that, does not repair it, and does not authorise an order. It corrects the
*reason* recorded for 12 of the 86 unconnected items: they are **unrouted copper on layer-compatible
pads**, not an interface that the board cannot express.
