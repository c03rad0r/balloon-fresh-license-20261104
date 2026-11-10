# ADR-087 — Differential-pressure rig basis and separate qualification gates

**Status:** ACCEPTED — operator approved 2026-11-10. Implementation and physical qualification remain incomplete.

## Context

The protocol's “1.05 bar” lacked an absolute/gauge reference. The operator could not establish its original intent and approved replacing it with a differential basis, qualifying the measurement chain separately, and retaining balloon-specific limits as unknown. Selecting a >=100 kPa pump to cover both interpretations was unsupported.

## Decision

1. Define positive overpressure as `ΔP = P_internal_absolute - P_ambient_absolute`. Use Pa internally; retain raw absolute readings alongside corrected differential values.
2. Retain ESP32-S3 and two MS5611 sensors, internal and ambient. Qualify each sensor pair against an independent reference; matching sensor models does not transfer calibration. BMP280 remains optional ground instrumentation, not a substitute.
3. Withdraw the 1.05 bar inflation target and >=100 kPa procurement recommendation. Select pump pressure, flow, duty cycle and electrical envelope from the qualified application and relief capacity.
4. Require independent passive relief and verified pump-off protection. Natural leakage is not a safety mechanism; pump-off does not release trapped pressure. A GPIO pull-down alone does not cover a hung output held high or a shorted FET.
5. Separate Gate M (measurement calibration), Gate S (independent protection) and Gate E (envelope/batch qualification). M/S use a rated fixture without a balloon. Gate E establishes numerical balloon-specific bounds; no placeholder or blog example is an approved setting.
6. Keep circumference as the Yokohama stretching process endpoint. Differential pressure governs pressure measurements and ceilings, not a universal pressure-only stretching recipe. Keep flight filling/free-lift separate from prestretch qualification.

## Supersession

This ADR supersedes ADR-147 Decision 5's assertion that natural leakage and pump-off are sufficient protection, and its no-relief consequences. It does not change ADR-147's separate-board decision. It supersedes the ambiguous protocol target and pump recommendation, and the old B1 combined trace-to-cutoff procedure. Historical text retained in other records is not implementation authority where it conflicts with this ADR.

## Evidence and alternatives

SF-HAB reports about 0.5 psi differential for particular clear Chinese balloons, with failures during screening; TT7 describes a particular 12-litre envelope ramp to 7 kPa over ten hours. These support differential measurement and envelope-specific testing, not a universal safe limit.

- https://sf-hab.org/2021/10/12/preparation-of-the-clear-chinese-balloons
- https://tt7hab.blogspot.com/2019/07/the-pre-stretching-rig.html

Rejected: silently choosing absolute pressure (ambient-dependent stress), choosing 1.05 bar gauge (unsupported high differential), transferring a blog's test setting to different envelopes, or inferring a safe ceiling from one non-destructive circumference trace.

## Implementation and acceptance

The detailed contract and required records are in [DIFFERENTIAL-PRESSURE-BASIS](../prestretch/DIFFERENTIAL-PRESSURE-BASIS.md); executable bench steps are in [B1](../prestretch/PRESTRETCH-BENCH-SESSION-B1.md). The [pressure-rig roadmap](../prestretch/ROADMAP.md) owns remaining work and gates.

Documentation checks and existing host software tests are not physical qualification. No pressure setpoint, trip/reset threshold, relief setting or flight approval is authorised by accepting this ADR.

## For future sessions

Pressure reference and sensor choice are settled: do not ask again whether 1.05 bar meant gauge or absolute. Numerical envelope limits remain UNKNOWN until Gate E; Gate M/S can progress independently. Record evidence rather than promoting placeholders to operating limits.
