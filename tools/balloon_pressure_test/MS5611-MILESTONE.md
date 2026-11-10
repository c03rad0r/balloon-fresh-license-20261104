# MS5611 acquisition prerequisite — host verified, NOT paired firmware

Base: live master 72b479b8 (PR537 merged). PR538 pressure_pair remains separate;
this branch does not include or modify it. No hardware access, flashing, autozero,
pump/cutter path, actuation or purchases.

## DECISIONS

Extract and extend the existing main.c MS5611 path instead of introducing a
parallel unused driver. Each ms5611_t owns all eight PROM words and a transport
context. Reset + PROM is atomic; failed reinit removes readiness. Validate all
C1–C6 against zero/ffff, then manufacturer's CRC4 across all eight words. CRC
is corruption detection, NOT chip identity: MS5611 has no unique chip-ID command;
a different compatible device with valid PROM cannot be distinguished by CRC.
Known wrong/blank responses fail, but no universal wrong-device detection claim.

Use OSR4096, >=10ms conversion wait, >=3ms reset wait, and 100ms timeout per
I2C transaction. This is not a 100ms total sample deadline. Full second-order
cold compensation uses int64_t, C11 division toward zero. Failed reads leave
outputs untouched; callers MUST use return status, never stale outputs.

A read-only consultant reviewed extraction hazards before implementation
(served alias tier/delegation, actual family unknown; NOT a cross-family review).

## Verified

`make -C tools/balloon_pressure_test/test check`: driver PASS, interlock 33/33,
analysis 12/12, pressure contract 6/6. Driver also passes AddressSanitizer and
UBSan build. Scripted bus asserts command sequence, sizes, timeouts and waits;
fault injection at all 13 reset/PROM/conversion/ADC transactions; CRC corruption
in every word; blank/ffff PROM; coefficient sentinels; failed reinit; invalid ADC;
two independent states with distinct calibration. Datasheet nominal example:
C1..6=40127,36924,23317,23282,33464,28312; D1=9085466 D2=8569150
=> 100009 Pa, 2007 centi-C. Cold formula reference checks cover below 20C and
below -15C (not additional manufacturer-published measurement vectors).

Test-first initial RED was a missing extracted header/source compile failure,
not a behavioral RED. Subsequent tests and sanitizer execution are real; no
claim that this alone proves strict behavioral TDD. No silicon measurements.

## Concrete target-build blocker

Attempted exactly:
`idf.py -C tools/balloon_pressure_test -D IDF_TARGET=esp32s3 build`
returned exit 127: `idf.py: command not found`. IDF_PATH is unset; neither
~/esp/esp-idf/export.sh nor ~/.espressif exists. Bounded SDK search also checked
/opt, /usr/local and /data. No installed SDK was located; no target binary built.
Host compilation is NOT ESP32S3 compilation. Also inspect Kconfig placement
(project root rather than component) when the SDK becomes available.

## Explicit follow-on dependencies

This milestone is completed driver prerequisite only. main.c still implements
the historical single-sensor logger, now using the extracted driver and correct
ESP-IDF new-master bounded I2C API. It is NOT the new controller's paired app.
Keep its old C3 pin assumptions away from the S3 controller. Before dual runtime:
merge/review this milestone and PR538 separately, then wire two device handles
with fixed internal 0x77 / ambient 0x76 (constants in ms5611.h, matching merged
schematic), both ready, timestamps/skew and invalid propagation into pressure_pair.
No role autodetection, no automatic zero, no interlock arm. Confirm S3 schematic
GPIO mapping and build actual S3 image, then separately authorized bench tests.
Physical pair-offset/manometer qualification and independent relief remain open.
