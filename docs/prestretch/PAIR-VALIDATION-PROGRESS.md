# Paired-pressure validation increment — local, not qualified

2026-11-10, branch pr/pressure-pair-validation, based on master a26af189.

Implemented pure-C `main/pressure_pair.{c,h}` and exercised via the normal host Makefile. Tests first failed for missing API, then failed on invalid-sample acceptance before validation implementation. Final `make -C tools/balloon_pressure_test/test clean check` passes existing 33 interlock assertions, 12 analysis tests, and new paired-pressure assertions.

Contract: signed Pa subtraction, explicit externally calibrated offset, fixed same-bus internal 0x77 / ambient 0x76 roles, explicit age/skew and fixture pressure/temperature bounds. Rejects null, invalid, non-finite, out-of-bounds, stale, future-dated or mismatched-role input. Invalid results are NaN, never a plausible zero. No re-zero API or actuator output exists.

NOT integrated into app_main or ESP-IDF CMake; no paired I2C acquisition implemented yet. Address validation is not proof of sensor identity: acquisition must verify actual MS5611 PROM/CRC and independent reads. Driver errors must mark samples invalid. Offset metadata/provenance and qualified ranges remain caller responsibilities. No hardware calibration, S3 build, firmware flashing or pump actuation performed.

Salvage verification (2026-11-10): preserved the existing implementation; added 20 per-role poison cases (invalid flag, NaN/Inf, pressure/temperature bounds, stale/future timestamps and wrong address), inclusive boundary checks, negative offset and retained-absolute-input checks. `make -C tools/balloon_pressure_test/test clean check` returned `test_interlock: 33 passed, 0 failed`, `test_plot_pressure: 12 passed, 0 failed` and both paired-pressure success lines. The paired suite also passed with `CFLAGS='-std=c11 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined'`. `make test-unit` returned `94 passed in 14.94s` (pre-existing duplicate Makefile recipe warnings). Built binaries are excluded from this commit.

DECISIONS: retain this pure validation increment under ADR-087, rather than redesign or imply completed acquisition. `raw_pa` means uncorrected differential; absolute inputs remain unchanged and must be logged by the eventual caller. The offset is externally supplied on every call: immutability and calibration provenance are caller obligations, not properties this stateless helper can enforce. Bounds in the tests are synthetic fixtures, not qualified operating limits. No live acquisition or hardware test was performed.

Next: independent parent review, then integrate two device handles with per-device calibration and CRC, bounded I2C timeouts, synchronized readings and raw/corrected logging. Existing main.c mixes new I2C handle types with legacy API function names; resolve in the driver integration with a real S3 build. Keep pump hardware disabled. Roadmap first item remains incomplete. No deployment/qualification claim.

## Integration correction and review — 2026-11-10

Chosen board assignment: **U3 internal = CSB LOW = 0x77; U4 ambient = CSB
HIGH = 0x76**, matching PR #537 measurement commit
`99f1fad5784b527eb6a2ff701c1a3bc2d79db8f6` and its native schematic/report.
Read alongside live master `665c973e` ADR-087 and PR #535's proposed address
correction. Roles are freely assignable at board/plumbing design time; silicon
CSB polarity is not: address `111011C` uses the complement of CSB. This module
chooses the existing schematic's roles explicitly. No schematic was changed.
PR #535 owns the broader electronics-spec correction; its separate ADR proposal
is not substituted for the accepted live ADR-087 here.

Regression evidence: the new two-distinct-address wrong-role test failed against
the old implementation at `!pp_evaluate(...)`; after correcting the role check,
the full host `clean check` passed (33 interlock assertions, 12 analysis tests,
all pair assertions including the 20 poison cases). The same full suite passed
with `-O1 -g -fsanitize=address,undefined` and no sanitizer diagnostics.
Additional tests pin UINT64_MAX age/skew arithmetic and corrected-value overflow
from finite pressure/offset inputs. These are host tests, not live actuation.

Additional root `make test-unit` run: **93 passed, 1 failed**. The unchanged
FIPS transport tracked test binary cannot load `libmbedcrypto.so.16` on this
host; this is outside the pair/interlock suite. No root-suite green claim is made.

Review of this pure helper found no additional blocking defect in nonfinite,
stale, skew or offset arithmetic: all floating inputs/config bounds must be
finite, outputs are poisoned before validation, future timestamps are rejected
before unsigned age subtraction, skew subtracts smaller from larger, and both
computed results must be finite. Offset is subtracted with its sign preserved.
Open integration obligations remain: calibrate/freeze the offset and bound its
uncertainty externally; provide trustworthy monotonic acquisition timestamps,
per-device PROM/CRC and compensation, and validated physical role/plumbing.
Address validation alone cannot detect swapped hoses or a caller mislabeling
samples. This helper does not enforce a balloon limit, acquire sensors or drive
the existing interlock. Passing legacy interlock tests does not qualify its
absolute-pressure runtime path for the new differential basis. Parent review
and CI are still required; no cross-family review is claimed by this fix.
