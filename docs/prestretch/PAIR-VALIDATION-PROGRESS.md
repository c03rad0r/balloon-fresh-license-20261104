# Paired-pressure validation increment — local, not qualified

2026-11-10, branch pr/pressure-pair-validation, based on master a26af189.

Implemented pure-C `main/pressure_pair.{c,h}` and exercised via the normal host Makefile. Tests first failed for missing API, then failed on invalid-sample acceptance before validation implementation. Final `make -C tools/balloon_pressure_test/test clean check` passes existing 33 interlock assertions, 12 analysis tests, and new paired-pressure assertions.

Contract: signed Pa subtraction, explicit externally calibrated offset, fixed same-bus internal 0x76 / ambient 0x77 roles, explicit age/skew and fixture pressure/temperature bounds. Rejects null, invalid, non-finite, out-of-bounds, stale, future-dated or mismatched-role input. Invalid results are NaN, never a plausible zero. No re-zero API or actuator output exists.

NOT integrated into app_main or ESP-IDF CMake; no paired I2C acquisition implemented yet. Address validation is not proof of sensor identity: acquisition must verify actual MS5611 PROM/CRC and independent reads. Driver errors must mark samples invalid. Offset metadata/provenance and qualified ranges remain caller responsibilities. No hardware calibration, S3 build, firmware flashing or pump actuation performed.

Salvage verification (2026-11-10): preserved the existing implementation; added 20 per-role poison cases (invalid flag, NaN/Inf, pressure/temperature bounds, stale/future timestamps and wrong address), inclusive boundary checks, negative offset and retained-absolute-input checks. `make -C tools/balloon_pressure_test/test clean check` returned `test_interlock: 33 passed, 0 failed`, `test_plot_pressure: 12 passed, 0 failed` and both paired-pressure success lines. The paired suite also passed with `CFLAGS='-std=c11 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined'`. `make test-unit` returned `94 passed in 14.94s` (pre-existing duplicate Makefile recipe warnings). Built binaries are excluded from this commit.

DECISIONS: retain this pure validation increment under ADR-087, rather than redesign or imply completed acquisition. `raw_pa` means uncorrected differential; absolute inputs remain unchanged and must be logged by the eventual caller. The offset is externally supplied on every call: immutability and calibration provenance are caller obligations, not properties this stateless helper can enforce. Bounds in the tests are synthetic fixtures, not qualified operating limits. No live acquisition or hardware test was performed.

Next: independent parent review, then integrate two device handles with per-device calibration and CRC, bounded I2C timeouts, synchronized readings and raw/corrected logging. Existing main.c mixes new I2C handle types with legacy API function names; resolve in the driver integration with a real S3 build. Keep pump hardware disabled. Roadmap first item remains incomplete. No deployment/qualification claim.
