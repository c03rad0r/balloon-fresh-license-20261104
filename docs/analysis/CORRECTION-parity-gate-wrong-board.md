# CORRECTION: the schematic-parity G4 failures were not on this board

**Written 2026-11-07, immediately after the error.**

## What I claimed, wrongly

I ran:

```
tracker/hardware/check_schematic_parity.py          # no --board argument
```

and reported that the board failed G4 node parity on 6 nets, that the board carries `U_E28`
while the schematic carries `U_LORA1280`, and that this "dwarfs the opens" as the real order
blocker.

**None of that was true of the live board.** The gate's `--board` argument defaults to

```
BOARD = os.path.join(HERE, "hub_board_v10.kicad_pcb")
```

which is a **different board** in the repo (`tracker/hardware/hub_board_v10.kicad_pcb`). I
ran the gate against that file and attributed its findings to
`docs/analysis/bulk-route-20261107/latest.kicad_pcb`.

## What is actually true

Running it with the board named explicitly:

```
check_schematic_parity.py --board docs/analysis/bulk-route-20261107/latest.kicad_pcb
```

```
PASS  G1 SCHEMATIC EXISTS: v10_flight.kicad_sch
PASS  G2 ERC: 9 error(s) within the documented allowance
      [label_dangling:5, pin_not_driven:2, power_pin_not_driven:2]
info  schematic nets: 53   board nets: 53
PASS  G3 NET PARITY: 53 net(s) agree both ways
PASS  G4 NODE PARITY: per-net (ref,pin) sets equal
skip  G5 REGISTRY AGREEMENT: no --registry given -- SKIPPED, not passed
PARITY: 0 failure(s)
```

**The live board is fully schematic-parity clean.** G1-G4 all pass. There is no `U_E28` on
this board (I verified: the footprint does not exist; the board has `U_LORA1280` / LoRa1280
with 16 pads carrying every E28 net).

G5 was SKIPPED for lack of a `--registry` argument, and the tool says so rather than passing
it — which is the correct refusal semantics, but it does mean registry agreement is
**unverified**, not verified.

## The lesson, stated plainly

A gate's *default* target is not necessarily *my* target. This repo contains multiple boards
(`hub_board_v10.kicad_pcb`, `v_c3_flight`, the analysis copies, plus batch boards), and I ran
a gate without naming which board I meant, then reported its output as if it described mine.

Compounding it: I then "confirmed" the claim by searching for `U_E28` on the live board and
in the schematic, found it in neither, and reported that as `U_E28` being on the board. It was
not. The measurement contradicted my claim and I read it as support.

This is the same failure mode as the earlier four: I did not check that the instrument was
pointed at the thing I was talking about.

## What still stands from this line of enquiry

- `check_drc.py --board <live>` reports **21 failing violations, 25 allowed, 22 unconnected**.
  That run DID name the live board, so that finding stands.
- AGENTS.md §21 requires DRC 0 before a board commit is legitimate, so the board is not
  gate-clean on DRC.
- The 104 mm2 orphaned `/VSCAP` B.Cu island stands (measured on the live board directly).
- The wing-tab slot clearance stands (measured on the live board directly).

Correction: the parity claim is withdrawn entirely.
