# Ordering channel: always use JLCONE desktop

**Status:** standing convention, recorded 2026-11-09 at the operator's request.

> *"please put it on the roadmap to make sure we use it for future orders without me needing to remind you"*

## The rule

**Every JLCPCB order for this project goes through the JLCONE desktop app**
(`https://jlcone.com/download`), not the website checkout.

## Why

Measured from JLCPCB's own published terms, 2026-11-09:

| benefit | detail |
|---|---|
| **Random instant discount** | **$1–$20 off, automatically applied at checkout**, every order, during the current promotion. No eligibility criteria stated. |
| **$104 coupon pack** | credited automatically on first install. Multiple coupons cannot stack on one order, so treat the full $104 as an upper bound, not a discount. |
| **$2 PCB deal** | moved **off the website entirely** — app-only now. Applies to small 2-layer prototypes, not our 4-layer 72x80 boards. |
| **Exclusive shipping rates** | special routes also moved to the app. |

On a typical v10-class order (~$25 assembly setup + ~$40 components + PCB + shipping, order total
roughly $150), the instant discount is a **1-13 % saving** for zero extra work.

The operator placed the first v10 order on the website before this was decided. That order is
placed; this rule governs **future** orders.

## Provenance — this is not a lookalike domain

`jlcone.com` is JLCPCB's own, confirmed three ways:

- `jlcpcb.com/help/article/jlcone-desktop-app` — JLCPCB's own FAQ about the app
- `jlcpcb.com/news/jlcpcb-jlcone-desktop-app` — JLCPCB press release, 2026-08-22
- Homebrew cask `jlcone` resolves to the same site

**Install only from `jlcone.com/download` or `brew install --cask jlcone`** — never from a search
result. JLCPCB's own stated reason for building the app is that phishing sites impersonating them
are common.

## What does NOT change

JLCONE is an ordering front-end — a "dedicated browser shell" per JLCPCB's privacy FAQ. The files
are identical:

- upload the same `v10-jlcpcb-upload.zip` (gerbers + drill + BOM + CPL)
- the same verification still applies: checksum the zip, then checksum the **extracted
  `cpl-jlc.csv`** (`0bd05492…` for the current v10 top-only bundle) because the zip container
  changes on every rebuild while the payload does not
- same order settings: 4 layers, 1.6 mm, 1 oz, ENIG, castellated YES, edge plating No,
  substitutions OFF
- same preview checks: headers upright with the crosshair on the pin array, bottom-side parts on the
  bottom, DNP parts absent

## Fraud note

JLCPCB never asks for payment outside their own checkout. A discount requiring card details on a
third-party site is fraud, regardless of how official the page looks.

## Related

- `docs/fab/v10-order-top-only/README.md` — the order this convention was first considered for
- ADR-146 — the v11 layout changes deferred from that order
