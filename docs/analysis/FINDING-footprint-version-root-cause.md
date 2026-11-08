# Root cause found: the footprint files declare a format version this pcbnew cannot parse

**2026-11-07, board `e00b98e7`. Supersedes the "version mismatch" guess in
`FINDING-library-items-are-version-mismatch.md` with a controlled measurement.**

## The measurement

`pcbnew.FootprintLoad()` returns `None` for the four `balloon_flight_v10` footprints. Rather than
guess, I varied **one field at a time** on a copy of the file:

```
version 20250114  -> None
version 20241229  -> LOADED OK
version 20240108  -> LOADED OK
version 20231120  -> LOADED OK
```

**That is the whole defect.** The file's `(version 20250114)` is above what this pcbnew (9.0.9)
accepts. One earlier version and it loads cleanly. Nothing else about the file is wrong.

## What was ruled out first, by test

Before the version test I falsified three plausible explanations:

1. **Library not registered.** Registered it board-local *and* in
   `~/.config/kicad/9.0/fp-lib-table` with correct absolute URIs. Count unchanged.
2. **Name mismatch.** The file declares `(footprint "balloon_flight_v10:LoRa2021F33_2G4")` — library
   files normally carry no `lib:` prefix. Stripped the prefix: still `None`.
3. **Malformed header / duplicate tags.** The file genuinely has **duplicated** `(version ...)` and
   `(generator ...)` lines (`20250114` then `20240108`). De-duplicated them: still `None`.

A control proved the API itself works: a **stock** KiCad library loads fine.

```
/usr/share/kicad/footprints/RF.pretty -> Skyworks_SKY13575_639LF -> LOADED
```

So `FootprintLoad` is the right call, the path is right, the name is nearly right, and the file is
well-formed enough to parse — the version date alone decides it.

## Why the file says 20250114

The header duplicates `(version 20250114)` with a `(generator_version "9.0")`, then repeats
`(version 20240108)` with a second `(generator "pcbnew")`. That looks like a file that was written by
one tool version and then re-saved by an older one, or hand-edited, leaving both headers. Whichever
happened, the **first** version token is what the loader reads, and it is the one that fails.

## Consequence for the order

**None.** Libraries are never sent to a board house; the board file is, and it embeds its own
footprint geometry. The gerbers already plotted from this board and were independently verified with
`gerbv`. This is a toolchain artefact, not a manufacturing defect.

## The repair, if the gate is to go green

Rewriting the four `balloon_flight_v10` footprints' version token to `20241229` makes them load, and
the four `lib_footprint_issues` disappear. That is a **two-line change per file** and touches no
geometry — the pads, layers and outlines are byte-identical.

I have NOT done it. Reasons:

- it edits committed library files that other worktrees and the schematic also reference;
- "rewrite a format version so a parser accepts it" is exactly the kind of change that should be
  deliberate, not incidental, and it wants a note in the repo's own docs;
- the gate fails only on a comparison it cannot perform, and 11 `lib_footprint_mismatch` items
  remain anyway from standard-library drift, so fixing this alone does not make `check_drc` pass.

## What WOULD make check_drc pass

Two separate things, and this session has only addressed the first:

1. **4 x `lib_footprint_issues`** — the version token above.
2. **11 x `lib_footprint_mismatch`** — board copies differ from this machine's standard KiCad
   libraries (`MountingHole` x8, `CP_Radial` x2, `SolderJumper` x1). Either re-sync those footprints
   from the project's intended library versions, or run the gates on a machine whose KiCad matches
   the project.

## Reproduce

```
python3 -c "import pcbnew as p; print(p.FootprintLoad('<libdir>','LoRa2021F33_2G4'))"
# then change only (version 20250114) to 20241229 in a copy and repeat -> loads
```
