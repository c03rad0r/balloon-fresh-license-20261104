# HIERARCHY ROLE: SUB-PROJECT MANAGER

You are the isolated manager of balloon-tollgate only. You report to the balloon-hermes orchestrator group.

## CRITICAL BOUNDARIES (ANTI-COLLAPSE GUARDRAILS)

- You are a SUB-MANAGER, not a coordinator. You do NOT coordinate other balloon tracks.
- You have ZERO visibility into other tracks' kanban boards, status, or plans.
- You are FORBIDDEN from: maintaining cross-track plans, building dependency graphs, reading other tracks' assessments, nudging other tracks, or acting as an orchestrator.
- Your ONLY external duty is: provide status reports to balloon-hermes when asked, using the STATUS-REQUEST-PROMPT.md template.
- Do NOT read ~/repos/balloon-fresh/docs/coordination/ files (INDEX.md, DECISIONS-AND-BLOCKERS.md, COORDINATOR-TRACKING.md, TRACKS-REGISTRY.yaml) — those are orchestrator-only files.
- Do NOT read ~/.hermes/profiles/manager/state/session-notes.md — that contains coordinator context.

## YOUR SCOPE
- Your worktree: this directory only
- Your kanban: your board only (if configured)
- Your assessment: docs/INTEGRATION-ASSESSMENT.md in this worktree
- Your status file: docs/STATUS-balloon-tollgate.md in this worktree

## DELEGATION EXPECTATIONS (POSITIVE COLLABORATION)

You are part of a hierarchy. The orchestrator (balloon-hermes group) DELEGATES work to you. Your responsibilities:

1. **EXPECT DELEGATION.** When the orchestrator sends you a task, it is YOUR responsibility. Execute it, do not bounce it back. The orchestrator chose you because this is your domain expertise.
2. **RESPOND PROMPTLY.** When asked for status or a task update, respond in the SAME turn. Use the STATUS-REQUEST-PROMPT.md template if one was sent.
3. **PROACTIVELY REPORT cross-track findings.** If you discover something relevant to another track's domain (e.g., a hardware issue, a protocol mismatch, a shared resource conflict), tell the orchestrator: "ORCHESTRATOR: Forward this to [track-name]: [finding]". The orchestrator routes it — you do NOT contact other tracks directly.
4. **SHARE BLOCKERS EARLY.** If you are blocked on something another track owns (shared hardware, dependency, protocol), tell the orchestrator immediately. Do NOT silently wait or try to work around it yourself.
5. **YOUR STATUS IS VISIBILITY.** Commit and push regularly. The orchestrator monitors your worktree via session_search and git log. Uncommitted work is invisible work.

These complement your anti-collapse guardrails above: you collaborate THROUGH the orchestrator, never directly with other tracks.

## BOARD ACCESS — HARD MUTEX LOCK (v3)

All 3 ESP32-S3 boards are shared resources across balloon tracks. Access is
enforced by a **hard device lock** (chmod 000 on /dev/ttyACMx), not just an
advisory flock. When another track holds a board lock, raw tool access is
physically blocked:

- `cat /dev/ttyACMx` → Permission denied
- `esptool.py --port /dev/ttyACMx ...` → Permission denied
- `idf.py -p /dev/ttyACMx flash` → Permission denied

Tool: `~/repos/balloon-fresh/tools/balloon-board-lock.py` (v3)

### Flash Queue — Orchestrator Approval REQUIRED

**NO flashing without orchestrator (balloon-hermes) approval.** Before
flashing ANY board, add a row to `~/repos/balloon-fresh/docs/coordination/FLASH-QUEUE.md`
and wait for approval. This prevents firmware mismatch during coordinated tests.

### Flash Procedure

```bash
# 1. Get orchestrator approval (add row to FLASH-QUEUE.md)

# 2. Acquire hard lock (blocks other tracks at OS level):
BALLOON_TRACK=tollgate python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire board-a \
    --purpose "approved flash: C3 stripped build" --timeout 120

# 3. Flash with idf.py (lock holder's sentinel keeps fd open → access works):
idf.py -p /dev/ttyACM0 flash monitor

# 4. ALWAYS release when done (restores chmod 666):
BALLOON_TRACK=tollgate python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release board-a

# 5. Update FLASH-QUEUE.md status to DONE
```

### Verify Lock Before Board Work

```bash
# Exit 0 = you hold the lock; Exit 1 = another track holds it
BALLOON_TRACK=tollgate python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py check board-a
```

### Serial Wrapper for Python Test Scripts

Any Python script that opens a serial port MUST use BoardSerial instead of
raw `serial.Serial()`:

```python
from board_serial import BoardSerial
# NOT: ser = serial.Serial('/dev/ttyACM0', 115200)
ser = BoardSerial('/dev/ttyACM0', 115200)
```

Tool: `~/repos/balloon-fresh/tools/board-serial.py`

Board mapping:
- board-a: ESP32-S3, MAC 94:a9:90:2e:37:7c, /dev/ttyACM0, TollGate-B96D80
- board-b: ESP32-S3, MAC fc:01:2c:c5:50:50, /dev/ttyACM1, TollGate-C0E9CA
- board-c: ESP32-S3, MAC 20:6e:f1:98:d7:08, /dev/ttyACM3, display board

Skipping the lock is a bug. Concurrent flashing corrupts boards. The hard
device lock (chmod 000) ensures that even if a sub-manager bypasses the lock
script, raw tools fail with "Permission denied".

### Discovery Sync Notes (2026-07-24)

Adopted independently from cross-track findings (no coordination):
- **Hard device locking (v3)**: from balloon-hermes commit 35b292c + balloon-speed-tests commit ef60a51
- **Flash queue protocol**: from balloon-hermes FLASH-QUEUE.md
- **Serial wrapper mandate**: from balloon-range-tests commit 171387d
- **FLRC byte alignment**: from balloon-range-tests commit 9b740aa — informational only, tollgate has no LR2021 radio

When the orchestrator (balloon-hermes) asks for a status update, fill the template from STATUS-REQUEST-PROMPT.md and reply with the filled template only. No commentary, no cross-track opinions.

---

## DECISION RECORDS — READ BEFORE CHANGING ANYTHING (added 2026-10-08)

This repo is **ADR-first**: a design change without a landed ADR is a draft, not a decision.

- **`docs/adr/INDEX.md`** — every architecture decision, numbered. If two records disagree, the one
  that explicitly supersedes wins. **A contradiction that names no winner is a DEFECT, not an
  ambiguity** — fix the record; never pick a side silently.
- **`docs/analysis/`** — findings and measurements, not decisions. Each must state its method and
  the command that reproduces it. An analysis with no re-verification path is a claim, not evidence.
- **Single-source-of-truth parameter registry** (`docs/`, when present) — owns the ONE authoritative
  value for each contested parameter (outline, land size, flash size, band split, wing orientation,
  cell class). A record asserting a different value for a registered parameter is **stale by
  definition**: fix the record, never the registry.
- ADRs carrying a **"For future sessions"** section state the one-line rule, the file paths and the
  reproduce command. Read that section first.

**Known defect class — FOUR instances measured on 2026-10-07/08.** Two records asserting different
values for the same parameter, with nothing surfacing it: hub outline (22x22 vs 55x45 vs 103 mm);
ESP32-S3 flash (16 MB vs 8 MB); "2.4 GHz RX on the F33" (vs the bare LoRa2021); wing plane
orientation (ADR-049 vertical vs WING-TO-HUB-SOCKET-SPEC sec 1 "horizontal"). **When you assert a
parameter, grep the repo for a competing value and cite the record that owns it.**

## STANDING AUTHORITY — MAKE THE DECISION, RECORD THE REASONING (added 2026-10-18)

The operator (c08r4d0r) has granted **standing authority to make technical and design decisions on his
behalf**, without asking first. This supersedes the previous habit of stopping at every fork to ask.

**The rule:**

1. **Decide.** When a decision is needed — placement, routing strategy, pin assignment, ADR content, which
   trade-off to take — make it. Do not park the work waiting for approval. The operator reviews outcomes,
   not every step.
2. **Consult BEFORE deciding, not after.** Every non-trivial decision gets a consultant pass. For spatial,
   geometric, layout, or fabrication-visibility questions that is **Astra** (`gpt-6-astra`, via
   `ask_astra.py`). For cross-family checking use a **different family** — a reviewer from the same family as
   the author is not a review.
3. **Record every decision with its reasoning**, in a DECISIONS block in the deliverable (and in the
   commit message). Each entry: the decision, the evidence it rests on (paths, hashes, numbers), the
   alternatives rejected and why, and what would change the answer.
4. **Surface the end result, not the deliberation.** The operator asked to see the finished state plus the
   decision record. Do not stream "shall I proceed?" questions.
5. **He corrects what he disagrees with.** A decision made under this authority is a **first pass**, not a
   verdict. State disagreements plainly so a second pass is cheap.
6. **This does NOT extend to:** placing a purchase order, spending money, publishing to a public host,
   rotating credentials, or rewriting git history. Those remain explicit-approval-only.

**Why this exists.** Measured 2026-10-18: the operator was asked to adjudicate a design fork ("move `U4` 2 mm
or reassign pins") and answered from a summary that was **wrong three times over** — the direction was
inverted, the move collided with `U1`, and the move would not have freed the pads at all because the
blocking copper belonged to `U4`'s own neighbours. **Asking a human to choose between options that have not
been measured is worse than deciding with a consultant**, because it transfers an unmeasured premise into a
decision that then looks authorised. Measure, consult, decide, record.

**Consultants are oracles, not actors.** Astra is read-only by design. It reasons about an artefact you send
it; it does not edit files, and it never replaces a tool that computes. Ask it a question that CAN be
answered wrongly, send the artefact rather than a description, and record the **served** model id — an alias
is not a model, and a router that substitutes a different family has not given you the review you asked for.

**Environment gotchas — measured, each cost real time:**
- KiCad's Python bindings (`pcbnew`) live in the **distro** python's site-packages, not the venv the
  test suite runs in. **CORRECTED 2026-10-25:** this note used to name `/usr/bin/python3.14`, which
  **does not exist on this host** — measured, `ls /usr/bin/python3*` returns only `python3` and
  `python3.12`. Importing `pcbnew` under the WRONG interpreter can **segfault** and kill the whole
  pytest run, so still probe it in a subprocess, never in-process. The working invocations are:

  ```
  /usr/bin/python3 -c 'import pcbnew; print(pcbnew.Version())'     -> 9.0.9
  PYTHONPATH=/usr/lib/python3/dist-packages python3 -m pytest ...  # project pytest + pcbnew
  ```
- **3D models — corrected 2026-10-11.** The earlier note here ("`KICAD9_3DMODEL_DIR` is **unset** and
  no 3D model library is installed, so renders are substrate+copper+silkscreen only") was **wrong on
  its first two clauses** and is superseded: `kicad-packages3d 9.0.7-1` **is** installed (14,043
  `.step`/`.wrl` files, 4.6 GB at `/usr/share/kicad/3dmodels`), and KiCad 9 substitutes its own
  compiled-in default for `KICAD9_3DMODEL_DIR`, so the env var being empty in the shell does **not**
  matter — the hub render *does* contain component bodies (measured; setting the env var changes the
  render by zero bytes). The real and still-true hazard is in the third clause: **`kicad-cli pcb
  render` exits 0 and prints no warning when a footprint's model does not resolve** — the part is
  silently absent. So never infer component bodies from a render, and never trust a vision
  description of one; ask the machine instead:
  `/usr/bin/python3 scripts/model_resolution_census.py --check --require-refs U1,U2,U3,U4,U5,ANT3 <board>.kicad_pcb`
  (text parse, no `pcbnew`, exit 1 on any unresolved reference or missing required model). Measured
  2026-10-11: wing **12/12 resolved, 0 unresolved** (15 fp; H1–H3 mounting holes carry no model, which
  is legitimate); hub **25/32 resolved, 7 unresolved** (model-less U2/U4 + missing LoRa2021, ESP32-S3,
  U.FL, ublox_MAX files) — the hub is **not** ready for a spatial review. Details:
  `docs/analysis/pcb-render-pipeline.md` and `docs/3d-model-coverage-wing.md`.
- The suite is green (`python3 -m pytest tests/ -q --continue-on-collection-errors`). Under load,
  `tests/test_board_lock.py::test_lock_status` can flake on a 10 s lock timeout — that is
  **contention, not a regression**; re-run the single file to check.
- **Before pruning worktrees, run `python3 scripts/worktree_unpushed_sweep.py`** — it exits 2 if any
  worktree holds unpushed commits or uncommitted edits. `/tmp` is tmpfs; worktrees there are lost on
  reboot. Keep worktrees in `~/worktrees/`.

---
# AGENTS.md — Instructions for AI Coding Agents

## Project Overview

TollGate ESP32 firmware: captive portal WiFi hotspot with Cashu e-cash payments, on-device wallet, Nostr identity derivation, wifistr service discovery, ContextVM (MCP over Nostr) server, and **local Nostr relay** with relay selection and sync. Runs on three ESP32-S3 boards.

## Technology Stack

- **Framework:** ESP-IDF v5.4.1 (C/C++)
- **Target:** ESP32-S3, 16MB flash, 8MB PSRAM (OCT mode)
- **Wallet:** nucula library (libsecp256k1) via git submodule
- **Identity:** Nostr nsec → HMAC-SHA512 → deterministic MAC/SSID/IP
- **Service discovery:** wifistr (Nostr kind 38787) via WebSocket
- **ContextVM:** MCP over Nostr (kind 25910), CEP-6 announcements, 10 MCP tools
- **Local relay:** wisp-esp32 (adapted), NIP-01 server on port 4869, LittleFS 4MB storage
- **Relay selection:** NIP-11 HTTP probing, latency + NIP-77 scoring, auto-failover
- **Sync:** REQ-diff with primary (30min) and fallback (6h) relays
- **Testing:** Host C unit tests (gcc), Node.js integration tests (live board), Playwright E2E

## Board Configuration

| Board | Port | Factory MAC | SSID | AP IP | Notes |
|-------|------|-------------|------|-------|-------|
| A | `/dev/ttyACM0` | `94:a9:90:2e:37:7c` | `TollGate-B96D80` | `10.185.47.1` | Primary test target |
| B | `/dev/ttyACM1` | `fc:01:2c:c5:50:50` | `TollGate-C0E9CA` | `10.192.45.1` | Secondary |
| C | `/dev/ttyACM3` | `20:6e:f1:98:d7:08` | (TBD) | (TBD) | Display board |

**IMPORTANT:** Board ports change on every USB replug. Always verify with `esptool.py --port <port> chip_id` before flashing.

Identity (SSID, IP, MAC) is derived from `nsec` in config.json. Each board gets a unique nsec.

## Boot Sequence

```
nvs_flash_init()
  → tollgate_config_init()          // loads config.json with nsec from SPIFFS
  → identity_init(nsec)             // derives npub, STA/AP MAC, SSID, IP via HMAC-SHA512
  → tollgate_config_derive_unique() // copies derived values into config struct
  → esp_netif_init() + esp_event_loop_create_default()
  → wifi_init_sta() + wifi_create_ap_netif()  // AP netif with derived IP
  → esp_wifi_init()
  → esp_wifi_set_mac(STA/AP)        // sets derived MACs
  → esp_wifi_set_mode(APSTA)
  → esp_wifi_set_country_code("DE") // EU regulatory domain (channels 1-13, 20dBm)
  → wifi_configure_ap()             // uses derived SSID
  → esp_wifi_start()
  → [on STA got IP] start_services():
      sntp_init, firewall_init, session_init, wallet_init, dns_server, captive_portal, api,
      local_relay_init+start, relay_selector_init+probe, sync_manager_start, wifistr_publish, cvm_server_start
```

## Key Files

### Source (main/)
- `tollgate_main.c` — entry point, WiFi AP+STA, event loop, service lifecycle
- `config.c/h` — SPIFFS config.json parsing, nsec/nostr/wifi/mint settings
- `identity.c/h` — HMAC-SHA512 derivation from nsec, npub/MAC/SSID/IP
- `nostr_event.c/h` — NIP-01 event serialization + BIP-340 Schnorr signing
- `geohash.c/h` — lat/lon to geohash encoding
- `wifistr.c/h` — kind 38787 event builder + local-first publish (local relay then public)
- `captive_portal.c/h` — HTTP :80 portal, captive detection, grant/reset
- `dns_server.c/h` — DNS hijack/forward per-client, DoT reject
- `firewall.c/h` — per-client NAT filter via LWIP_HOOK_IP4_CANFORWARD, MAC resolution
- `session.c/h` — time-based sessions, MAC tracking
- `cashu.c/h` — Cashu token decode, checkstate, allotment calc
- `tollgate_api.c/h` — HTTP :2121, payment endpoints, wallet endpoints
- `cvm_server.c/h` — ContextVM: persistent WS relay listener, kind 25910 subscription, MCP protocol handlers, CEP-6 announcements
- `mcp_handler.c/h` — 10 MCP tool handlers (get_config, set_config, get_balance, wallet_send, get_sessions, get_usage, set_payout, set_metric, set_price, wallet_melt)
- `local_relay.c/h` — Thin wrapper: inits wisp_relay storage/sub/rate-limiter on port 4869, publishes events to LittleFS + broadcasts to WS subscribers
- `relay_selector.c/h` — NIP-11 HTTP probing of seed relays, latency + NIP-77 scoring, auto-failover after 3 disconnects, 6h re-probe cycle
- `sync_manager.c/h` — REQ-diff sync: primary every 30min, fallback every 6h, reconciles local events vs remote, dedicated FreeRTOS task
- `display.c/h` — QSPI TFT display (JC3248W535/AXS15231B): boot/ready/payment/error states, Wi-Fi and portal URL QR cycling every 5s, `escape_wifi_field()` for special chars
- `font.c/h` — Bitmap font rendering for display text output

### Components
- `nucula_lib/` — C++ bridge to nucula::Wallet (C API in nucula_wallet.h)
- `secp256k1/` — symlink to nucula_src/components/secp256k1/
- `wisp_relay/` — Local Nostr relay (NIP-01): ws_server, storage_engine (LittleFS), sub_manager, broadcaster, router, handlers, relay_validator (Schnorr+SHA256), rate_limiter, nip11, deletion, flash_monitor
- `esp_littlefs/` — LittleFS VFS integration for relay storage partition (git submodule)
- `negentropy/` — Negentropy set-reconciliation library (git submodule, for future NIP-77)
- `axs15231b/` — QSPI TFT display driver (JC3248W535)
- `qrcode/` — QR code generator

### Config Format (config.json on SPIFFS)
```json
{
  "nsec": "<64-char hex>",
  "wifi_networks": [{"ssid":"...", "password":"..."}],
  "ap_password": "",
  "mint_url": "https://testnut-nutshell.mints.orangesync.tech",
  "price_per_step": 21,
  "step_size_ms": 60000,
  "nostr_geohash": "u281w0dfz",
  "nostr_relays": ["wss://relay.damus.io", "wss://nos.lol", "wss://relay.anzenkodo.workers.dev", "wss://nostr.koning-degraaf.nl"],
  "nostr_publish_interval_s": 21600,
  "nostr_seed_relays": [
    "wss://relay.orangesync.tech",
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.nostr.band",
    "wss://relay.anzenkodo.workers.dev",
    "wss://nostr.koning-degraaf.nl",
    "wss://knostr.neutrine.com",
    "wss://nostr.einundzwanzig.space"
  ],
  "nostr_sync_interval_s": 1800,
  "nostr_fallback_sync_interval_s": 21600,
  "cvm_enabled": true
}
```

## Testing Rules — MANDATORY

### Rule 1: Every new C source file MUST have unit tests
- Place test in `tests/unit/test_<module>.c`
- Test pure-logic functions with known input/output vectors
- Compile with host gcc via `make -C tests/unit`
- Source files remain untouched — stubs in `tests/unit/stubs/` provide ESP-IDF types
- **Run `make test-unit` after any code change. Must pass before commit.**

### Rule 2: Every new HTTP endpoint MUST have integration tests
- Place in `tests/integration/phase<N>.mjs`
- Test against live board using curl + `TOLLGATE_IP` env var
- Never hardcode IP addresses — always use `process.env.TOLLGATE_IP`

### Rule 3: Every new browser-visible feature MUST have Playwright E2E tests
- Place in `tests/e2e/<feature>.spec.mjs`
- Test the full user-visible flow in a browser

### Rule 4: All tests must pass before commit
- `make test-unit` — host unit tests (no hardware needed)
- `make test-integration` — against live Board A (needs hardware)
- `make test-e2e` — Playwright browser tests (needs hardware)

### Rule 5: Test naming conventions
| Test type | Location | Naming | Run command |
|-----------|----------|--------|-------------|
| Host unit | `tests/unit/` | `test_<module>.c` | `make test-unit` |
| Integration | `tests/integration/` | `phase<N>.mjs` or `<feature>.mjs` | `make test-integration` |
| E2E | `tests/e2e/` | `<feature>.spec.mjs` | `make test-e2e` |

### Rule 6: Coverage requirements by code type
| Code type | Required test type | Examples |
|-----------|-------------------|----------|
| Pure math/logic | Unit test | geohash, allotment calc, derivation |
| Crypto operations | Unit test with known vectors | HMAC derivation, Schnorr signing, SHA-256 |
| Token parsing | Unit test with known tokens | Cashu token decode |
| State management | Unit test with mocks | Session lifecycle, firewall client list |
| HTTP endpoints | Integration test | GET /wallet, POST /, POST /wallet/send |
| HTML pages | Playwright E2E | Portal rendering, payment flow |
| Network behavior | Integration test | DNS hijack, NAT, connectivity |

## How to Run Tests

```bash
# Host unit tests (no hardware needed)
make test-unit

# Integration tests (needs Board A connected and flashed)
export TOLLGATE_IP=10.192.45.1
export TOLLGATE_SSID=TollGate-C0E9CA
make test-integration

# E2E tests (needs Board A + browser)
make test-e2e

# All tests
make test-all

# Quick smoke (30s, needs hardware)
make smoke

# Local relay tests (needs board)
make test-local-relay
make test-relay-nip11

# CVM MCP roundtrip (needs board + internet)
make test-cvm-roundtrip
```

## Single-Source-of-Truth Parameter Registry (READ BEFORE CITING A VALUE)

This repo has repeatedly carried **two records asserting different values for the
same physical parameter, with nothing surfacing the disagreement** — four cases in
one day (hub outline, ESP32-S3 flash size, the 2.4 GHz RX radio, the wing plane
orientation), plus the F33 castellation land size.

The list is machine-readable and lives in **`docs/ssot/parameters.json`** — one
entry per contested parameter: the single record that OWNS it, the canonical
value, an anchor that proves the owner still asserts it, the records that
historically asserted something else, and a `forbid` regex for the conflicting
value.

**Before you write a dimension/part/size into a record, check the registry. If a
value is genuinely open, register it as open rather than picking one.** When you
find a second record asserting a different value, add the entry (or the
conflicting record) the same day; do NOT resolve it by editing the losing
record's body — append a `CORRECTION` block citing the registry (the repo's
convention, see ADR-042/ADR-056 and the 2026-10-08 corrections in
ADR-048 / `WING-TO-HUB-SOCKET-SPEC.md` / ADR-040 / `hardware-design.md`).

```bash
# the gate — FAIL-CLOSED (exit 0 pass / 1 conflict / 2 cannot determine)
python3 scripts/param_ssot_check.py
python3 scripts/param_ssot_check.py --json
python3 scripts/param_ssot_check.py --list      # show the registry

# its test (also collected by `pytest tests/`)
python3 -m pytest tests/test_param_ssot.py -q
```

A conflicting value is allowed only when it is **annotated history**: the matched
line carries a marker (`was`, `stale`, `superseded`, `guess`, `TODO(unverified)`,
`→` …) or the file carries an appended **CORRECTION** block / cites
`docs/ssot/parameters.json`. An UN-annotated conflicting assertion fails the gate.

## Build & Flash

```bash
source ~/esp/esp-idf/export.sh
make flash          # build + flash to Board A
make flash-a        # same
make flash-b        # flash to Board B
```

## Test Infrastructure

### Host Unit Tests (`tests/unit/`)
- Compile with system gcc, link against `libmbedcrypto` + `libcjson` + secp256k1
- ESP-IDF types provided by stubs in `tests/unit/stubs/`
- Each test file is a standalone binary that returns 0 on success, 1 on failure
- Uses a minimal assert macro: `ASSERT(cond, msg)`
- Golden test vectors: known nsec → expected npub/MAC/SSID/IP

### Integration Tests (`tests/integration/`)
- Node.js scripts that run curl/ping/nmcli against a live ESP32 board
- Require `TOLLGATE_IP` env var (default: auto-detect or error)
- Token generation via nutshell CLI: `cashu -h https://testnut-nutshell.mints.orangesync.tech send --legacy 21`

### E2E Tests (`tests/e2e/`)
- Playwright browser tests
- Config in `tests/e2e/playwright.config.mjs`
- Test the captive portal UI and payment flow

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `TOLLGATE_IP` | (none, must set) | Board A's AP IP (e.g., `10.192.45.1`) |
| `TOLLGATE_SSID` | `TollGate-C0E9CA` | Board A's AP SSID |
| `TEST_TOKEN` | (none) | Cashu token for payment tests |
| `SUDO_PW` | `RETRIEVE_FROM_VAULT` | sudo password for route management |

## External Dependencies

- **Test mint:** `testnut-nutshell.mints.orangesync.tech` — Nutshell/0.20.0, works with cashu CLI
- **Nostr relays:** `relay.damus.io`, `nos.lol`, `relay.anzenkodo.workers.dev`, `nostr.koning-degraaf.nl` — for wifistr events
- **Seed relays:** `relay.orangesync.tech` (NIP-77), `relay.damus.io`, `nos.lol`, `relay.nostr.band`, `relay.anzenkodo.workers.dev`, `nostr.koning-degraaf.nl`, `knostr.neutrine.com`, `nostr.einundzwanzig.space` — for relay selection and sync
- **CVM relay:** `relay.primal.net` — for ContextVM kind 25910 events and CEP-6 announcements
- **Local relay:** Port 4869, LittleFS 4MB partition at 0x500000, max 5000 events, 21-day TTL
- **Nutshell CLI:** `cashu` command for token generation
- **ESP-IDF:** `source ~/esp/esp-idf/export.sh` before `idf.py` commands
- **System libs for unit tests:** `libmbedtls-dev`, `libcjson-dev`

## Reminders

- **Commit + push every time a test passes that previously didn't pass.** Green tests = checkpoint. Don't batch multiple test fixes into one commit.
- Commit + push after each working change
- Board A is at `/dev/ttyACM0`, Board B at `/dev/ttyACM1`, Board C at `/dev/ttyACM3`
- **Per-board locks required** before hardware access: `make lock-a PHASE="desc"`, lock files in `physical-router-test-automation/locks/`
- `sudo` password: `RETRIEVE_FROM_VAULT`
- SPIFFS is at offset `0x410000`, size `0xF0000` — erase with `esptool.py erase_region 0x410000 0xF0000` if config is stale
- NVS stores wallet proofs — erasing NVS clears wallet balance
- **Relay storage** LittleFS at offset `0x500000`, size `0x400000` (4MB) — auto-formatted on first boot
- The `nostr_event.c` `created_at` field uses `gettimeofday()` — mock this in unit tests
- Wifistr event signing uses `secp256k1_schnorrsig_sign32()` — verify with `_verify()` in tests
- relay_validator.c does Schnorr verify + SHA-256 event ID — test with `test_relay_validator`
- relay_selector scoring: NIP-77 bonus (1000pts) + latency + failure penalty (100pts each) — test with `test_relay_selector`
- Portal HTML has server-side template substitution (`__AP_IP__`, `__PRICE__`, `__MINT_URL__`) — no JS fetch
- **WiFi country code:** Must set `esp_wifi_set_country_code("DE")` before `esp_wifi_start()` — defaults to CN which causes auth failures on EU APs
- Default nsec: `a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2`

## Git Remotes & Repositories

Full details in `REMOTES.md`. Key facts:

- **This repo** (`esp32-tollgate`): `nostr://npub12m5.../git.orangesync.tech/esp32-tollgate`
- **GRASP server:** `git.orangesync.tech` (git smart HTTP)
- **Nostr relay:** `wss://ngit.orangesync.tech` (state events)
- **GitWorkshop:** `workshop.orangesync.tech` (web UI)
- **NerdQAxePlus fork:** `nostr://npub12m5.../git.orangesync.tech/esp-miner-nerdqaxeplus-tollgate`
- **Worktrees:** `esp32-miner-integration` (feature/miner-integration), `esp32-tollgate-arch` (feature/tollgate-core-component)
- **Push commands:** `git push orangesync --all` (esp32-tollgate), `git push ngit-origin develop` (NerdQAxePlus)
- **Backup bundles:** `/home/c03rad0r/mining-work-backup/`
- Board A nsec: `9af47906b45aca5e238390f3d03c8274e154198e81aa2095065627d1e61ca968`

---

## Cross-Board Harmonized Bench (HARM chain)

Before touching any E80 / ESP32 / RP2040 board for a bench measurement, read
[`docs/harmonized/HARMONIZED-BENCH-PACKAGE.md`](docs/harmonized/HARMONIZED-BENCH-PACKAGE.md). It is the
single entry point and it is deliberately self-contained.

- **Repos and branches:** the plan names `balloon-e80bench` and
  `balloon-range-tests`, but **neither is a GitHub repository** — the former is a
  local directory name for a clone of `balloon-fresh`, the latter is the
  `range-tests` branch of `balloon-fresh`. The bench console and the HARM chain
  live on `balloon-fresh` branch `main` (not `master`; the two have diverged).
  The ESP32 family is `esp32-balloon-integration-fresh` (private, default branch
  `harm/t3-radiolib-fork`), whose RadioLib LR2021 driver is a **git submodule** —
  run `git submodule update --init --recursive` before building there.
- **Run the session:** `python3 tools/balloon_sweep.py --tx <e80|esp32|rp2040>
  --rx <e80|esp32|rp2040> --session <yymmddHHMM>`; add `--dry-run` for a
  pre-hardware spec check, `--only IDX...` to re-run a subset.
- **Never work around a refusal.** `REFUSED (pre-hardware, spec enforcement): …`
  means the plan violates `BENCH-CONSOLE-SPEC.md` (§6 LEN cap, §7 GAP for
  LEN > 256, §9 frequency pair). Fix the plan.
- **Never mix bands.** 868 MHz and 2.4 GHz rows go in separate tables and are
  never compared; 2.4 GHz cross-board work is legal only on
  `ESP32BENCH ↔ RP2040BENCH`. See `docs/harmonized/HARMONIZED-RESULTS.md`.
- **Reporting:** write the run up from
  [`docs/harmonized/HARMONIZED-RUN-REPORT-TEMPLATE.md`](docs/harmonized/HARMONIZED-RUN-REPORT-TEMPLATE.md)
  into `docs/runs/<run-id>.md`, then add the rows to
  [`docs/harmonized/HARMONIZED-RESULTS.md`](docs/harmonized/HARMONIZED-RESULTS.md). Commit the report
  and the CSVs in one commit.
- **No data is better than invented data.** Unrun configs are written `not run`.
  The E80↔E80 sweeps from 2026-08-21/22 are the *regression baseline* only; the
  cross-board pairs (E80↔ESP32, E80↔RP2040, ESP32↔RP2040) have no measurements
  yet.

## Cross-Board Harmonized Bench (HARM chain) — `range-tests` branch
This branch is the range-test lane of the harmonized cross-board bench
(E80 / ESP32 / RP2040). Entry point:
`docs/harmonized/HARMONIZED-BENCH-PACKAGE.md` on branch **`main`** of this same repo
(`https://github.com/felixfelix-bot/balloon-fresh.git`), together with
`docs/harmonized/HARMONIZED-RESULTS.md` and `docs/harmonized/HARMONIZED-RUN-REPORT-TEMPLATE.md`.
**The harmonized bench console is not on this branch.** `tools/balloon_sweep.py`,
`docs/BENCH-CONSOLE-SPEC.md` and the harmonized docs exist only on `main`
(HARM chain, `harm/t5-bench-console`); on this branch `tools/balloon_sweep.py`
does not exist. Check out `main`, or merge it into this branch, before trying to
drive a harmonized session. What this branch *does* carry is the legacy RP2040
sweep path below.
### Bench console / RP2040 build + flash
cd firmware/rp2040
make build-tx | build-rx | build-both      # firmware
make flash-tx | flash-rx | flash-both      # via picotool / BOOTSEL
make monitor-tx | monitor-rx
make ports                                  # re-detect ports; never guess
Legacy sweep drive (this branch):
BALLOON_TRACK=range-tests python3 tools/balloon-board-lock.py acquire board-a \
    --purpose "range sweep" --timeout 120      # lock is mandatory before flashing
python3 tools/sweep_flash.py
python3 tools/sweep_capture.py 480             # >= 2 full cycles
BALLOON_TRACK=range-tests python3 tools/balloon-board-lock.py release board-a
Harmonized session (after switching to `main`):
python3 tools/balloon_sweep.py --tx rp2040 --rx esp32 --session <yymmddHHMM> --dry-run
Rules:
- Never flash without the board lock; never work around a
  `REFUSED (pre-hardware, spec enforcement): …` result — it means the plan
  violates the spec (LEN cap 255/511, GAP >= 40 000 us for LEN > 256, frequency
  pair).
- 868 MHz and 2.4 GHz results are never mixed; 2.4 GHz cross-board is legal only
  on RP2040 ↔ ESP32.
- Report runs from `docs/harmonized/HARMONIZED-RUN-REPORT-TEMPLATE.md`; record unrun configs
  as `not run`. Data-handover convention for this branch:
  `docs/data-handover/DATA-HANDOVER-2026-08-17.md`.


## FLIGHT BOARD v10 — OPERATOR DIRECTIVES (2026-10-20) — BINDING
### ADR-118 (umbrella) · ADR-119 (radio sites) · ADR-120 (placement process + gates)

1. **Two-sided population is the default.** Parts go on both sides; the outline shrinks to
   what the two-sided placement needs. The 70x70 v9 outline is not a v10 constraint.
2. **Four RF sites:** LoRa2021F33 (HP) + TWO bare LoRa2021 LP + **E28-2G4M27SX module**
   (SX1280+PA+LNA+matching on-module; datasheet at `docs/modules/e28-2g4m27sx/`).
   The bare-chip SX1280 + self-built match network is ABANDONED (measured fatal scatter,
   `docs/fab/SX1280-MODULE-DECISION.md`).
3. **HUMAN PLACEMENT GATE (ADR-120 R3):** placement is rendered from MEASURED courtyard
   sizes, checked programmatically (overlap/bounds/wing seats), shown to the operator in
   Signal, and SIGNED OFF before ANY routing starts. Routing begun on an ungated placement
   is DISCARDED and the gate re-run. Gate verdicts are logged (date, operator, outcome).
4. **VISUAL-FIRST REPORTING (ADR-120 R4):** every substantive board claim ships with a
   rendered image (3D / copper / annotated crop) IN THE SAME MESSAGE, in Signal. Text-only
   board reports are a process violation. Committed renders must match the board on disk
   (image-freshness pre-commit hook, PR #250).
5. The E28 module's keep-out rules (nothing under the module but the digital corner; keep
   away from high-frequency/power traces) apply to BOTH sides of the board at its site.

## FLIGHT BOARD v10 — ROUTING (2026-10-21) — BINDING

6. **ADR-126: grid A* routing with via support is the ONLY permitted routing method.**
   All copper is placed by `tracker/hardware/route_v10_astar.py`. The straight/L router
   (`route_v10_phase1.py`) is BANNED and kept only as a negative reference. It has no model
   of obstacles and can only work by luck: measured on this board it produced a lane at
   0.000 mm over `U_C.9`, two dead-end stubs, and 21.66 mm of copper through the F33's body.
   With the corrected gates it could place 0 legal nets.
7. **No copper ships unless all four routing gates pass on the resulting board:**
   `check_lane_clearance.py` (track vs every foreign pad — **unnamed pads are metal**),
   `check_lane_integrity.py` (dead ends, copper touching a foreign net),
   `check_copper_under_body.py` (copper traversing a module body; own-pad entry exempt),
   `check_lane_isolation.py` (**different nets must not touch** — track vs track, track vs
   via, via vs via, all same-layer pairs; this is the class the operator flagged first and
   NO gate covered it until 2026-10-21),
   `check_hole_clearance.py` (holes vs pads, lanes, vias, zones, edge).
   A run with any violation is NOT committed. Nets that cannot be placed are REPORTED, never
   forced. Hand-drawn copper requires a `ROUTE-EXCEPTION` entry in `docs/fab/v10/GATE-LOG.md`
   naming the nets and the reason.
8. **Every routing run is followed by a rendered image in the same Signal message** (ADR-120
   R4), and the board's routed/unrouted counts are stated as measured numbers.
9. **Pin→net truth lives in ONE registry:** `tracker/hardware/connectivity/v10_pinmap.reg`,
   one line per pin, in git, with the deciding ADR as the authority column.
   `registry.py check` FAILS on drift between board and registry. A pin that is UNASSIGNED
   must be justified in `connectivity/OPEN-ITEMS.md` — an unassigned pad with no OPEN-ITEMS
   entry is a test failure. Never hand-type pin maps in a builder; assign from the registry.
10. **Regression tests bind every gate:** `tests/test_v10_connectivity.py` runs each gate
   TWICE — against a clean board (must pass) and against a poisoned board carrying the defect
   (must fail). A gate that cannot fail is not a gate. Any new gate needs both halves.

## FLIGHT BOARD v10 — SCHEMATIC IS THE SOURCE OF TRUTH (2026-10-22) — BINDING

Operator directive: *"I want the board to be derived from a schematic at all times."*
Operator directive: *"Please include it in your git hooks and run it before showing me the
images in future so that you catch and fix such errors before showing me your progress."*

11. **ADR-128: the schematic defines connectivity; the board is DERIVED from it.**
    Direction is one-way: `schematic → ERC → netlist → board → DRC`. A Python builder may
    PLACE components and ROUTE copper, but it may NOT invent connectivity. `build_hub_board_v10.py`
    assigns nets from `connectivity/v10_pinmap.reg`; that is legal **only** because
    `check_schematic_parity.py` proves the registry equals the schematic. If they disagree, the
    schematic wins and the builder is wrong.
    **Measured 2026-10-22: v10 had NO schematic.** It was derived by transforming v9's NETLIST
    (`make_v10_netlist.py`), so the E28, U_C, the ADR-123 bus split and J_PROG never went
    through ERC. ADR-028 banned this workflow on 2026-08-05 — with this exact diagnosis ("No
    schematic = no ERC = netlist errors propagate undetected into PCB layout", after 527 DRC
    violations) — but was left status *Proposed* and never enforced. ADR-128 makes it binding.
12. **Every board commit must pass `check_schematic_parity.py`:** G1 schematic exists,
    G2 `kicad-cli sch erc` clean, G3 net parity BOTH WAYS, G4 node parity per net,
    G5 registry agreement, G6 REFUSAL (missing schematic / missing kicad-cli = non-zero,
    never green). A gate that cannot run must not look green.
13. **Every board commit must pass `check_drc.py`:** `kicad-cli pcb drc`, classified by type.
    `clearance` and `shorting_items` are HARD failures — **this is the short check the operator
    asked for on 2026-10-22**, and it was missing: the eight custom gates reported all-zero while
    kicad-cli found 48 violations on the same board.
    Allow-lists must be **SCOPED and justified in writing**, never blanket. Current entries:
    `silk_over_copper` / `silk_overlap` (cosmetic), and `copper_edge_clearance` scoped to
    `J_W1..J_W4` **pads only** (the wing seats are edge connectors sitting on Edge.Cuts by
    design; measured 16 items, all J_W* pads, ZERO tracks) — a TRACK near the edge still fails,
    which is exactly why the scope exists rather than a blanket allow.
14. **KiCad's DRC is the authority for copper-vs-copper, copper-vs-edge, silk and parity.**
    The custom gates encode project-specific rules (registry, E28 keep-out, layer semantics).
    BOTH must pass; neither replaces the other. When a custom gate and kicad-cli DISAGREE, that
    disagreement is a bug in the custom gate until proven otherwise — it was 4 times on
    2026-10-22 (B34/B37/B38/B40), and a 5th time in `check_lane_crossing.py` (B42a/B42b), where
    the custom check invented 165 crossings and 2948 via-near hits against a board with ZERO
    clearance violations.
15. **Same-layer crossings are checked explicitly:** `check_lane_crossing.py` reports CROSSING /
    OVERLAP / TOUCH / NEAR / VIA-NEAR between DIFFERENT nets on the SAME layer. Same-net
    self-crossings are legal and counted separately. `tests/poison_lane_crossing.py` must keep
    passing: it plants a real same-layer crossing and requires exit 1 (verified clean rc=0,
    poisoned rc=1). A gate that once reported 165 FALSE defects must be able to report a REAL one.
16. **Gates run BEFORE any render is shown to the operator.** Pipeline order:
    route → 8 custom gates → `check_drc.py` → `check_schematic_parity.py` →
    `check_socket_edge_tracks.py` → render → Signal.
    Showing an image of a board that fails a gate is a process defect.
17. **Renders must make LAYER IDENTITY unambiguous.** The operator flagged two same-coloured
    lanes crossing and could not tell whether it was a short — because the old renderer drew ONE
    layer at a time in ONE colour, so a front-over-back crossing looked identical to a
    front-front one. Use `tracker/hardware/tmp_probes/render_layers_distinct.py`: FRONT = SOLID
    ORANGE, BACK = DASHED CYAN,
    VIA = white circle, and any same-layer different-net crossing drawn in RED with the verdict
    and crossing count printed ON the image. A render is evidence only if it can show the defect
    it is used to rule out.
18. **Hooks enforce 12 + 13:** `scripts/git-hooks/pre-commit-board-gates.py` (wired into the
    fleet global `~/.git-hooks/pre-commit`) runs both gates whenever a `.kicad_pcb` /
    `.kicad_sch` / `.kicad_mod` / the registry / `OPEN-ITEMS.md` is staged, so ordinary commits
    pay nothing. Verified both ways: a non-board commit passes through, a real board commit is
    BLOCKED with both gates naming their failures and the change left unstaged. Bypass only with
    `--no-verify` AND a stated reason in the commit message. A gate that cannot run REFUSES
    (exit non-zero) rather than passing silently.

## FLIGHT BOARD v10 — SCHEMATIC FIRST, PROVEN TESTED (2026-10-22) — BINDING

Operator directive: *"please make sure the schematic always exists and is fully tested before we
make the board. Please make sure its part of the git hooks and agents.md."*

19. **ORDER IS ENFORCED, NOT ADVISED.** A commit that stages a `.kicad_pcb` is REFUSED unless
    `tracker/hardware/schematics/flight_board/v10_flight.kicad_sch` exists. This is the mechanical
    form of "schematic before board". It is not a convention: it is a hook that exits non-zero.
    Rationale — v10 reached a state with 16 routed nets and **no schematic at all**, because the
    board could be rebuilt and re-routed freely while nothing checked that a schematic stood
    behind it.
20. **"EXISTS" IS NOT "TESTED".** An empty file satisfies existence, so the hook additionally
    requires `kicad-cli sch erc` to have **actually run and returned zero violations**, with the
    report parsed to prove it. 21 errors do NOT pass because the file is present. A missing
    kicad-cli, a missing report, or an unparseable report all **REFUSE** (non-zero) rather than
    pass — a gate that cannot prove it ran must never look green.
21. **The full pre-board sequence, in this order:**
    `schematic → ERC 0 violations → netlist → board → kicad-cli DRC 0 → 9 custom gates → render`.
    A board commit is legitimate only when every step BEFORE it is green. Rendering or routing
    ahead of a clean schematic is how connectivity gets invented.
22. **When a gate fires on correct input, the GATE is wrong — fix the gate, never the input.**
    Measured 2026-10-22: G3 flagged 8 `UNCONNECTED-(U1-IOxx-PADnn)` nets as "schematic nets
    missing from the board", while G4 (per-net pin sets) and G5 (registry agreement) both passed.
    Those names are KiCad's **auto-generated** labels for deliberately unconnected pins — the
    absence of a net, not a net. G3 now excludes synthetic single-pin names and REPORTS how many
    it ignored. A gate that cries wolf on correct input trains everyone to ignore it, which is
    worse than no gate.

## FLIGHT BOARD v10 — SILKSCREEN LEGIBILITY (2026-10-22) — BINDING

Operator directive, verbatim: *"please make sure that the silk screen is legible and doesn't
overlap with parts or other silk screens before you start routing the board. Please make sure this
is part of the quality gates that have git hooks and please make sure its part of agents.md so that
it gets checked & enforced automatically in future."*

23. **THE SILKSCREEN MUST BE LEGIBLE, AND IT IS A HARD GATE.** `check_silk.py` runs in
    `scripts/git-hooks/pre-commit-board-gates.py` and must report **zero** of:
    `silk_overlap`, `silk_over_copper`, `silk_edge_clearance`.
    **There is no allow-list, and that is deliberate.** Every other gate in this repo has a scoped
    allow-list because copper sometimes has a legitimate reason to sit close. Silk does not: two
    designators printed on top of each other is never correct, and ink clipped by a mask opening
    means the marking is absent exactly where it is needed. A designator the assembler cannot read
    is how a part gets fitted in the wrong place.
    A gate that cannot run must not look green: missing `kicad-cli`, missing report, or an
    unparseable report all **REFUSE** (rc=2) rather than pass.

24. **SILK IS PRE-ROUTING WORK.** Per §23 the operator's instruction is explicitly *"before you
    start routing"*. Do not begin routing on a board whose silkscreen fails the gate — the fix may
    move parts, and moving a part invalidates routing done before it. Sequence:
    `build → fix_silk → check_silk 0 → placement gate → route`.

25. **THE SILK REPAIR IS A SEPARATE STEP FROM THE BUILDER, ON PURPOSE.** `build_hub_board_v10.py`
    must stay a pure function of its spec: same spec in, byte-identical board out. Folding silk
    repair into it broke that (measured: two consecutive builds differed by 12,242 lines) because
    the repair needs `kicad-cli` feedback, making the builder's output a function of a DRC run
    instead of its spec. The pipeline is therefore three commands:
    `build_hub_board_v10.py` → `fix_silk.py` → `check_silk.py`.
    `fix_silk.py` itself must be deterministic: it sorts the DRC report before acting on it,
    because `kicad-cli` runs DRC multi-threaded and the violation ORDER in the report is not
    stable between runs (measured: that alone changed designator positions for 3 refs).

26. **WHAT THE SILK FIX MAY AND MAY NOT TOUCH.** It may move **reference text** and move
    **silk graphics to the Fab layer**. It must never touch pads, tracks, vias, zones, courtyards,
    the board outline, or connectivity. The Fab layer is the correct home for a component body
    outline (that is what F.Fab/B.Fab exist for), so moving an outline there is **lossless** —
    preferred over trimming it, which was measured to make things WORSE (9 → 12 violations,
    because each trim creates a new crossing at the cut).
    Designators are rendered at **0.80mm height / 0.15mm line width** — the JLCPCB silkscreen
    minimum. That is the smallest text that still prints legibly, not a cosmetic shrink; the board
    is dense enough (45 parts on 72×80mm) that a free-space sweep found only the left/right
    margins empty, so the fab minimum is what makes the labels fit at all.

27. **A ROUTER CHANGE MUST PROVE SEARCH/VALIDATOR AGREEMENT BEFORE IT LANDS.** The pre-commit hook
    runs `tests/test_router_grid_validator_agreement.py` whenever a staged file touches
    `route_v10_astar.py` / `route_escalating.sh` / `route_priority.sh`, and **refuses** on failure.
    This exists because **16 bugs in one session** (B34, B37, B44, B46, B47, B48, B55, B56 and the
    earlier eight) shared ONE shape: the A* grid, or the `--append` loader, permitted a move that
    `validate_plan` then refused, or that `kicad-cli` flagged. Every board gate was green while all
    16 were live.
    The gate had to fire on the **router file**, not on a board: patching the router does not touch
    any `.kicad_pcb`, so a board-triggered hook never ran on the commits that introduced them.
    The tests are **geometric, not textual** — one of them builds the real grid from the committed
    board and asserts a cell inside the edge keep-out is blocked, which is the exact check that
    catches B48. A comment-matching test was tried first and a poison test proved it did NOT fail
    when the bug was reintroduced; it was replaced.
    **Never relax these tests to make a commit pass.** If a test fails, the router is wrong.

## WING-SOCKET EDGE RULE (2026-11-03) — BINDING, ADR-142

13a. **THE `J_W` EDGE EXEMPTION IS PAD-ONLY. A TRACK MUST NEVER CROSS A SOCKET CAVITY.**
    The wing sockets are edge-launched, so their pads sit on `Edge.Cuts` on purpose and
    are exempted from the 0.50 mm edge rule. A **track** is not. Each `J_W` carries four
    `Edge.Cuts` graphics forming a 6.0 × 0.5 mm cavity cut into the board edge, and the
    pads sit on the **far** side of it — so reaching a land from the board interior
    requires crossing the cavity, which is copper physically cut by a board edge.
    Measured crossing pairs: `/W1_SOLAR_N` −0.092, `/W2_SOLAR_N` −0.100 and −0.096,
    `/W3_SOLAR_N` −0.096 mm.

    **Do not try to fix this in `.kicad_dru`.** ADR-142 §2 swept seven condition forms
    (`tracker/hardware/dru_edge_form_sweep.py`) and **no form reaches a track — not even a
    conditionless `edge_clearance (min 0.00mm)` waiver**, which removes all 16 pad items
    (20 → 4) and leaves every track item standing. The limit is the rule engine, not the
    condition syntax; there is no tighter scoping that would work either.

    Enforced by `tracker/hardware/check_socket_edge_tracks.py`, wired into
    `scripts/git-hooks/pre-commit-board-gates.py` and `tests/test_adr142_socket_edge_tracks.py`
    (which includes a **positive control** that plants a crossing track and requires exit 1).
    Pairs 3, 6 and 7 complete in **assembly** via the two-face tab (ADR-120 R1,
    `WING-TO-HUB-SOCKET-SPEC.md` §2) — that is what the two-land interface exists for.

## REPOSITORY ROOT LAYOUT (2026-10-25) — BINDING

Operator directive: *"there are still too many files on the top level directory of the repo.
Please organize these files in subdirectories."* The root had **23** loose files: 19 v10
probe/render one-offs, a poisoned test board and a KiCad scratch project. Two of them
(`render_layers_distinct.py`) were **invoked by path** from `tracker/hardware/`, so the clutter
was load-bearing — a move that ignores the callers breaks renders.

28. **ROOT IS ALLOW-LISTED, AND IT IS A HOOK.** The repository root may contain **only** these
    entry points: `.gitignore`, `.gitmodules`, `.secret-patterns.txt`, `AGENTS.md`, `README.md`,
    `PROGRESS.md`, `Makefile`, `pyproject.toml`, `pytest.ini`, `uv.lock`.
    Everything else must live in a subdirectory. Enforced by `tests/test_root_layout.py`, run from
    `scripts/git-hooks/pre-commit-board-gates.py` on **every** commit (it needs no board and no
    kicad). A gate that cannot run REFUSES (non-zero) rather than passing.
    **Allow-listed, not deny-listed, on purpose** — a deny-list lets the next stray through, which
    is exactly how 23 accumulated. Adding a name to the allow-list is the ONE way to add a root
    file, and the reason must be "repo-wide entry point", never "it was convenient".

29. **WHERE THINGS GO.**
    - one-off debug / probe / render scripts → `tracker/hardware/tmp_probes/`
      (read its `README.md` first — those probes have clobbered the real board before)
    - board scratch: poisoned `.kicad_pcb` copies, scratch `.kicad_pro` → same directory
    - documentation → `docs/` (clustered; see its own conventions)
    - reusable tooling → `tools/` or `scripts/`, **not** root

30. **A MOVE MUST FIX ITS CALLERS, AND MUST NOT DELETE WORK.** When relocating a script, grep the
    repo for invocations and repairs them in the same commit; and file the script, never drop it —
    the probes document *how* each defect was measured. `tests/test_root_layout.py` asserts both:
    that the 19 former root probes still exist under `tmp_probes/`, and that the two known callers
    point at the new path.

31. **THE PRE-EXISTING HAZARD THIS DID NOT FIX (recorded, not hidden).** **64 of 65** scripts in
    `tracker/hardware/tmp_probes/` hardcode `/home/c08r4d0r/worktrees/master-check/...`, so they
    only run in one worktree. Fixing that is a 64-file change and is **out of scope** for a layout
    PR; it is recorded here so the next person does not assume the directory is portable.
