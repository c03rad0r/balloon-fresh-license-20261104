# PR531 bounded supply milestone — 2026-11-10

Start: isolated worktree clean, HEAD 7fca474dc1ee68a45cd8bc2c082e74f26a4fc69f,
branch pr-pressure-controller-core. GitHub PR531 head owner felixfelix-bot,
repository balloon-fresh. No other board edited.

Replaced AP2112 with complete TPS62160DSGR WSON 1A buck circuit, inductor,
input/output capacitors, feedback and EN/VOS wiring. Official symbols/packages.
Preserved S3, USB, motor-supply exclusion. Fixed inherited display flags.

Observed tests:
1. New zero-ERC exported test against old files: RED AssertionError on inherited
   AP2112 lib_symbol_mismatch.
2. New BOM/arithmetic test against `git show HEAD:.../core.xml`: RED ValueError
   '1A WSON buck required'. First probe had a harness __file__ NameError;
   corrected probe reached the intended rejection.
3. Arithmetic negative control changing 32k denominator to 33k in an in-memory
   copy: RED ValueError 'feedback equation'; artifact unchanged.
4. Regenerated schematic; native KiCad XML export exit 0.
5. Native ERC --format json --exit-code-violations: zero violations, exit 0.
6. test_core.py: GREEN all 41 S3 pins, reset/boot, USB-C, buck/sense/feedback,
   output capacitance, no motor supply net, zero ERC.
7. test_supply.py: GREEN; also GREEN with python3 -O (explicit checks).
   Vout 3.300V; conditional ripple 0.476A; peak 1.238A; RMS 1.009A;
   reference IC loss budget 1.052W @60C; input 0.926A at 75% acceptance.
8. git diff --check: clean.

This does NOT complete all requested qualification: numeric capacitor DC-bias
curve unavailable, so effective capacitance remains a release gate. Frequency,
hot inductor and actual PCB thermal bounds require validation. No guaranteed
efficiency inferred from typical plots. README gives exact scope, sources and
acceptance requirements. No PCB/fabrication/physical operation claim.
