# BOARD STATUS REGISTER — what exists, what is measured, what is deferred to flight

**Date:** 2026-10-25 · **Repo state:** master `f6b3269f`
**Purpose:** one honest page. Every number below was **measured on the committed board**, not
recalled from an ADR. Anything unmeasured is labelled as such.

> ## ➡️ Split into per-generation pages (2026-11-11)
>
> This register now covers **general and flight-deferral content only**. Board state moved to one
> page per generation, so a stale section cannot contradict a current one:
>
> | generation | page | state |
> |---|---|---|
> | **v10 (hub + wing)** | **[V10-STATUS.md](V10-STATUS.md)** | fabricated, 10 assembled boards, **82 nets still unconnected** |
> | **v11** | **[V11-STATUS.md](V11-STATUS.md)** | **specification only — no board file exists** |
>
> **The hub table in §1 below is stale.** It reads `127 unrouted` from 2026-10-25; the board measures
> **82 unconnected** as of 2026-11-11 (`ace09314`). The v10 page carries the current numbers and the
> reproduce command. Where the two disagree, **the per-generation page wins** — it is measured with a
> recorded command, this register is a snapshot.


Operator direction that shapes this document: *"lets skip these tests and just investigate +
record this kind of stuff as part of the balloon flight. We might focus on the wrong details
if we go too deep into the details before doing our first flight."*

So this register **separates what blocks a flight from what is merely open**. Open items go
into §4 and get resolved with flight data; they do not block.

---

## 1. Boards in this build

| board | size | fps | pads | nets | tracks | unrouted | DRC violations |
|---|---|---|---|---|---|---|---|
| **wing interconnect** `wing_interconnect_v1` | 34.7 × 20.1 mm | 7 | 14 | 5 | 34 | **0** | **0** |
| **hub** `hub_board_v10` | 72 × 80 mm | 53 | 317 | 59 | 775 | **147** | **147 unconnected + 16 copper_edge_clearance** |
| **flight (C3)** `v8i_krt_gnss` | (frozen reference) | — | — | — | — | — | — |

Renders: `docs/fab/status/hub_v10_master.png`, `docs/fab/status/wing_ic_master.png`

### Wing interconnect — DONE
- Routed, 4 nets, per-cell bypass, 2-pin tab (ADR-134).
- DRC: `Found 0 violations / Found 0 unconnected items`.
- Schematic↔board parity: G1–G4 PASS, 0 failures (ADR-135).
- Gates: board (7 tests), schematic (7), sync (3), first-article doc (4).
- **Mass:** 6.92 cm² → 0.62 g/wing → **2.50 g for four** (was 3.18 g).
- Needs first-article Test A before cells are soldered — see
  `docs/fab/wing-3d/FIRST-ARTICLE-TEST.md`.

### Hub — NOT DONE
**147 unrouted items.** The render confirms it independently of the count: substantial empty
regions, many pads with no visible copper, sparse long runs. This board is not close to
orderable and no amount of DRC tuning changes that — the routing work itself is outstanding.

- 16 `copper_edge_clearance` at `x≈35.75–36.25, y≈74–80` and `x≈72, y≈40.25` — this is the
  **J_W2 wing-seat slot** region that AGENTS.md §B43 documents (a slot cut into a footprint's
  own Edge.Cuts, which the copper does not keep out of).
- ADR-134 removed `GND` and `RF_FEED` from the wing tab, so the hub's **4-land interface is
  now superseded** and the hub has not been changed to match. Routing 147 nets against a
  superseded interface would be work done twice.

---

## 2. Bypass diode coverage — the direct answer

**Yes, the hub carries a per-wing bypass for the entire wing.** Fitted on the board, verified
by reference:

```
D_BP1  D_BP2  D_BP3  D_BP4      <- one per wing, SS24
D_HUB1 D_HUB2                    <- per-cell bypass on the HUB's own solar array
```

Per ADR-129 §D2:

| diode | K (cathode) | A (anode) |
|---|---|---|
| `D_BP1` | `W1_SOLAR_P` | `W1_SOLAR_N` |
| `D_BP2` | `W1_SOLAR_N` | `W2_SOLAR_N` |
| `D_BP3` | `W2_SOLAR_N` | `W3_SOLAR_N` |
| `D_BP4` | `W3_SOLAR_N` | `GND` |

`D_BP4`'s anode is `GND` because the stack bottom is `W4_SOLAR_N`, which is the string return.

### The two layers do different jobs — both are needed

| layer | where | protects against | cannot see |
|---|---|---|---|
| `D_HUB1/2`, and the wing's own per-cell diodes | per **cell** | soft shunt / hot spot on one cell (ADR-054 §2.3(b)) | a whole wing going open |
| `D_BP1..4` | per **wing**, on the hub | a wing cut away or failing open — the string keeps producing | which cell inside a wing failed |

Without `D_BP`, a single wing cut = **0.00 W, 100 % loss** (ADR-054 §2.2). With it, only that
wing's cells are lost. This is why `U_CUT1..4` and `D_BP1..4` landed together in ADR-129 §D5.

**Wing side:** each wing now also has **3 per-cell SS24** on its interconnect board (ADR-132),
one across each cell — verified in the netlist, `D1.1(K)→SOLAR_P`, `D1.2(A)→SOLAR_MID1` etc.

---

## 3. What must be true before a first flight

Only these. Everything in §4 does not block.

- [ ] Wing interconnect: **Test A** (bare board, diode polarity) passed, recorded per wing.
- [ ] Each wing: **Test B** open-circuit ≈1.5 V at the tab — a ≈1.0 V reading means a reversed
      diode (33 % signature, see the procedure).
- [ ] Hub: routing complete enough to carry the four wing interfaces and the radio — see §5.
- [ ] Mass: total payload vs the ≈42 g corrected budget (wing side now 2.50 g for four).
- [ ] Balloon and recovery path per `docs/flight/first-flight-checklist.md`.

---

## 4. DEFERRED TO FLIGHT — record, do not block

These are the "we might focus on the wrong details" items. Each gets measured once there is a
flight, and only then does it deserve engineering time.

| # | open item | why it can wait | what flight data resolves it |
|---|---|---|---|
| 1 | **Soft-shunt vs hard-shunt dominance** (ADR-054 §2.3, bench crack test never run) | decides whether per-cell granularity must move from Rank 3 to Rank 2 | cell I-V after a real thermal/mechanical cycle, or a deliberate crack test |
| 2 | **Low sun angle current** (survey §7.1 item 4, unmeasured) | only matters if a winter launch is attempted; the +3.3 % tilt cost is already known | one winter or low-elevation flight |
| 3 | **Contact resistance at 400 mA cold** (ADR-131) | design is tolerant of it; the number is unknown | measured drop at the tab under load, first article |
| 4 | **Passive-rotation behaviour after a cut** (asymmetry uncharacterised) | there is no attitude control to lose; the balloon rotates regardless | flight video / rotation rate after separation |
| 5 | **Hub `copper_edge_clearance` × 16 at the J_W2 slot** | they are at ONE wing seat, not a systemic fault; DRC flags them, they do not stop a bench bring-up | first article inspection of the J_W2 seat slot |
| 6 | **Silk over traces** (D1/SC1 designators, `+` marks) on the wing board | DRC reports 0 silk violations — the marks sit over solder-mask-covered copper, not pads | first article visual |
| 7 | **3 pre-existing failing tests** (`test_c_host` FIPS, `test_system_diagram_geometry`, `test_v10_connectivity`) | reproduced on clean `1ce07990` **before** any wing work; they gate the v10 registry, not the wing | fix when the v10 board work resumes |

Item 7 is recorded so it is not mistaken for wing regression. It is not: verified by running
those three tests on clean master.

---

## 5. The hub decision that must be taken before hub routing resumes

**Do not route 147 nets against the old interface.** ADR-134 removed `GND` and `RF_FEED` from
the wing tab; the hub still presents the 4-land row `SOLAR_P / GND / RF_FEED / SOLAR_N`.

Order of work that avoids doing it twice:

1. Change the hub's wing interface to **2 lands** (`W<n>_SOLAR_P`, `W<n>_SOLAR_N`).
2. Re-run the hub's schematic↔board parity (`check_schematic_parity.py` with its registry).
3. Then route the remaining nets, and re-check the 16 edge-clearance violations at J_W2.

`D_BP1..4` do **not** change in this step — they are per-wing and stay.

---

## 6. Reproduce every number in this document

```bash
# wing
kicad-cli pcb drc --exit-code-violations tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb
/usr/bin/python3 -c "import pcbnew;b=pcbnew.LoadBoard('tracker/hardware/wing_interconnect/wing_interconnect_v1.kicad_pcb');b.BuildConnectivity();print(b.GetConnectivity().GetUnconnectedCount(False))"

# hub
kicad-cli pcb drc tracker/hardware/hub_board_v10.kicad_pcb
/usr/bin/python3 -c "import pcbnew;b=pcbnew.LoadBoard('tracker/hardware/hub_board_v10.kicad_pcb');b.BuildConnectivity();print(b.GetConnectivity().GetUnconnectedCount(False))"

# bypass diodes actually fitted
/usr/bin/python3 -c "import pcbnew;b=pcbnew.LoadBoard('tracker/hardware/hub_board_v10.kicad_pcb');print([f.GetReference() for f in b.GetFootprints() if f.GetReference().startswith(('D_BP','D_HUB'))])"
```
