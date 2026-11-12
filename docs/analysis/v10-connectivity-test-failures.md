# v10 connectivity: 3 failing tests, adjudicated — and why CI never saw them

**Date:** 2026-11-11 · **Board of record:** `docs/analysis/bulk-route-20261107/latest.kicad_pcb`
**Subject:** `tests/test_v10_connectivity.py` — 3 of 10 fail on a developer machine with KiCad
installed. This record says what each failure actually was, what was fixed, and why the same
tests have been **passing (by skipping) in CI the whole time**.

**Bottom line: every one of the three was a TEST or TOOL defect, not a board defect.** The
fabricated board is unchanged. One real, small board fact emerged — 3 track stubs — and it was
already there; nothing about it is new or dangerous.

---

## Why CI was green while local was red

`.github/workflows/ci-host-tests.yml` runs the connectivity suite in a job that installs
`gcc g++ make libmbedtls-dev libcjson-dev` — **and not KiCad**. The pcbnew-dependent tests
loud-skip. Suite 10 is the only thing that runs `tests/test_v10_connectivity.py`, and 8 of its
10 tests need pcbnew:

| test | needs pcbnew | in CI |
|---|---|---|
| `test_registry_matches_board` | yes | **skipped** |
| `test_lane_integrity_clean_board_passes` | yes | **skipped** |
| `test_back_side_pads_are_checked` | yes | **skipped** |
| 5 others | yes | **skipped** |
| `test_registry_file_is_parseable_without_pcbnew` | no | runs |
| static/file-shape checks | no | runs |

So the three failures had **never executed in CI**. They were not "pre-existing failures nobody
noticed" — they were invisible. A separate job (line ~164) does install KiCad for "the four
behavioural PCB pipeline gates", but the connectivity suite is not in it.

**This is the important finding, more than any single test.** A gate that silently skips on the
only machine that runs it is not a gate. The fix is to run Suite 10 in the KiCad job, not to
make local green by weakening assertions.

---

## Correction to what I told the operator earlier

I reported "**0 runners registered, CI is dead**". That was wrong, twice over:

- The workflows request `runs-on: ubuntu-latest` — **GitHub-hosted**. `actions/runners` returning
  `total_count: 0` is *normal* for GitHub-hosted runners; it does not indicate a dead CI.
- CI actually **ran and passed**: `git log` shows the push at 21:46 produced
  `completed/success` for both "Host Unit Tests" and "Tests".

What *is* true is that four runs from 20:37–20:38 on `pull_request`/`push` sit in `queued`
forever. That is a queue artefact worth checking, but it is not "CI is dead", and I should not
have merged a PR on that reasoning. The merge itself is still defensible — the PR was docs-only —
but the *stated reason* was wrong.

---

## Failure 1 — `test_registry_matches_board`: EVERYTHING WAS POINTED AT THE WRONG BOARD

Root cause was a **hardcoded board path in two places**, both naming a file that was never
fabricated:

```python
BOARD = os.path.join(HW, "hub_board_v10.kicad_pcb")            # tests/test_v10_connectivity.py
DEFAULT_BOARD = os.path.join(HERE, "..", "hub_board_v10.kicad_pcb")   # connectivity/registry.py
```

`hub_board_v10.kicad_pcb` is **superseded**: it carries a `U_E28` radio (782 tracks). The board
that was actually ordered, and the registry, use `U_LORA1280` (3092 tracks).

That single mismatch produced 18 phantom "pin in registry, absent from board" and 18 phantom
"pin on board, absent from registry" drifts — all from comparing the registry to a board nobody
built.

**Fixes applied:**

- `registry.py` `DEFAULT_BOARD` → the board of record
- `tests/test_v10_connectivity.py` `BOARD` → the board of record

**One genuine drift remained and was fixed:** `U1.27` is `/IO0` on the board and was
`UNASSIGNED` in `v10_pinmap.reg`. Commit `321617cd` changed the board without updating the
registry. One line changed. Registry now agrees **257/257 pins, DRIFT 0, MISSING 0**.

---

## Failure 2 — `test_lane_integrity_clean_board_passes`: THE CHECKER IGNORED ZONES

`check_lane_integrity.py` decided "dead end" by testing only two things: a **pad** of the same
net, or **another track's endpoint**. It never consulted **filled zones**, and never recognised
a track **passing through** the point (a T-junction).

I asked the board directly, using pcbnew's own `zone.HitTestFilledArea`, whether each reported
endpoint is bare:

| verdict | count |
|---|---|
| inside a **same-net filled zone** → connected | **58** (43 GND, 11 `+3V3`, 4 `/VSCAP`) |
| nothing of its own net under it | **3** |

**Fixes applied:** the checker now consults filled zones per net and treats a passing track as
a connection. Result on the board of record: **61 violations → 3**, and the 3 exactly match the
independent adjudication.

The test was rewritten to assert *"exactly these 3 known stubs and no others"* — stricter than
the old `rc == 0`, because it now fails both if a **new** dead end appears **and** if the checker
starts inventing them again.

### Negative control (required — a checker that reports nothing is not a gate)

A planted 6 mm isolated stub on a fresh net is still detected, exit code 1, both endpoints
reported:

```
planted a 6 mm isolated stub on /NEGATIVE_CONTROL_STUB at (1.0,1.0)
checker exit code : 1
DEAD END: track on /NEGATIVE_CONTROL_STUB ends at (1.00,1.00) with nothing under it
DEAD END: track on /NEGATIVE_CONTROL_STUB ends at (7.00,1.00) with nothing under it
NEGATIVE CONTROL: PASS
```

### A vacuous pass I caught in my own work

My first adjudication script iterated **all** tracks of the net including the flagged track, so
`GetEnd() == (x,y)` matched its own endpoint and it declared **every** endpoint connected — it
would have reported zero defects on a genuinely broken board. Corrected by counting connections
that are **not** the stub itself. Recorded here because the wrong version produced a tidy,
confident, wrong answer.

### The 3 real stubs

| net | endpoint |
|---|---|
| `/SPI1_MISO` | (8.75, 44.05) |
| `/SPI1_MISO` | (8.75, 41.25) |
| `/USB_DN` | (23.65, 51.25) |

Minor: none is a power rail, and the board is already fabricated. They are now a **recorded,
tested fact** rather than noise.

---

## Failure 3 — `test_back_side_pads_are_checked`: STALE REFERENCE LIST

The test asserted `U3`, `U_C`, `U_E28`, `ANT2`, `ANT3` exist and are back-side. Measured on the
board of record: **`ANT2` and `ANT3` do not exist** (removed with the antenna change), and
`U_E28` is on the superseded file.

My first fix replaced them with `U_LORA1280`, assuming it was flipped. It is **not**:
`IsFlipped()=False`, `GetLayer()=F_Cu`, all 16 pads on `F.Cu`. That "fix" asserted a false
premise and failed again — same error as the original, one level deeper.

**Fix applied:** refs that are *measured* to be back-side — `U3`, `U_C`, `U_CUT1`, `U_CUT2`,
`J_VCC` — each verified `IsFlipped()=True`, `GetLayer()=B.Cu`, pads on `B.Cu`.

---

## Result

```
tests/test_v10_connectivity.py .......... 10 passed in 139.07s
```

| # | defect | who | severity |
|---|---|---|---|
| 1 | Suite 10 skips in the only CI job that runs it (no KiCad) | CI config | **high** |
| 2 | `check_lane_integrity.py` ignored zones → 58/61 false positives | tool | **high** |
| 3 | Board path hardcoded to a superseded file, in two places | test + tool | **high** |
| 4 | `U1.27` `/IO0` missing from registry | registry | low, fixed |
| 5 | Stale `ANT2`/`ANT3` refs | test | low, fixed |
| 6 | 3 track stubs on the fabricated board | board | low, recorded |

The board itself: **0 DRC errors**, unchanged by this work. Nothing fabricated, ordered, flashed
or actuated.

---

## Reproduce

```bash
B=docs/analysis/bulk-route-20261107/latest.kicad_pcb
export PYTHONPATH=/usr/lib/python3/dist-packages

/usr/bin/python3 tracker/hardware/connectivity/registry.py check         # DRIFT 0
/usr/bin/python3 tracker/hardware/check_lane_integrity.py --board $B     # VIOLATIONS 3
/home/c08r4d0r/.venvs/ho-test/bin/python -m pytest tests/test_v10_connectivity.py -q
```
