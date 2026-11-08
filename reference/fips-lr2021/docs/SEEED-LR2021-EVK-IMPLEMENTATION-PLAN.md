# Seeed LR2021 EVK onboarding — implementation plan and checklist

**Status:** host implementation and all four sample builds complete; awaiting
commit approval. Hardware measurements and FIPS-on-EVK are not verified.
**Target:** `reference/fips-lr2021/` in `felixfelix-bot/balloon-fresh`.
**Last updated:** 2026-11-08

This is the working checklist for the official Semtech LR2021 LoRa Plus
Evaluation Kit onboarding guide and its Make targets. It is intentionally
separate from the colleague-facing runbook,
[`SEEED-LR2021-EVK-FIPS-ONBOARDING.md`](SEEED-LR2021-EVK-FIPS-ONBOARDING.md).
Update the boxes and evidence only when the corresponding work has actually been
completed. An upstream example is not evidence that the command has run on our
boards.

## Decisions and evidence

1. **Target current upstream master.** Keep this PR independent of other local
   branches and unrelated generated artefacts. The worktree was created from
   `origin/master` at `70183172` after fetching on 2026-11-07.
2. **Use Semtech USP rather than importing another LR2021 driver.** The official
   kit is supported by `Lora-net/usp_zephyr`, board
   `xiao_nrf54l15/nrf54l15/cpuapp`, shields
   `semtech_loraplus_expansion_board` and `semtech_wio_lr2021`. Use the stable
   v1.2.1 source at an immutable commit, Zephyr 4.4.0 and SDK 1.0.1, as named by
   the upstream v1.2.1 README and `west.yml`.
3. **Reuse the existing FIPS transport; do not claim EVK support yet.** The
   existing datapath, framing and tests remain authoritative. A future
   nRF54L15 bridge must implement `docs/BRIDGE-PROTOCOL.md`; the stock samples
   do not implement it. FLRP is a bulk-transfer benchmark, not a drop-in FIPS
   packet transport or payload-encryption layer.
4. **Separate RF and host-link measurements.** The stock EVK console is UART20
   at 115200 baud through the SAMD11 CMSIS-DAP interface. USB-C therefore does
   not imply direct SPI access or high-speed PC-to-radio streaming. Measure the
   host path before interpreting end-to-end throughput as an RF limit.
5. **Treat PER and FLRP as different baselines.** The FLRC PER example checks
   packet integrity. Its pinned implementation has fixed 255-byte buffers and a
   200 ms exchange interval despite broader README wording. FLRP is the vendor
   bulk-transfer reference. Measure delivered goodput; never substitute the
   2.6 Mbps PHY rate or Semtech's gross-burst figures for application results.
6. **Start without soldering or custom firmware.** Use the vendor samples first,
   keep independent build directories for compile-time roles, and require an
   explicit CMSIS-DAP probe selector for every flash. Keep third-party source
   and generated logs outside Git under the existing ignored `build/` tree.
7. **Leave parameter automation gated by baseline evidence.** Expose only source
   options verified in the pinned code. A reproducible vendor patch is required
   before automating PER delay/size or FLRP radio-parameter sweeps. Do not
   present unsupported `EXTRA_CFLAGS` as working controls.

## Implementation checklist

### PR scope and documentation

- [x] Inspect the existing E80/FIPS reference and its host bridge protocol.
- [x] Read the official EVK, USP, FLRC PER and FLRP documentation and source.
- [x] Fetch current upstream master and create an isolated feature worktree.
- [x] Record this implementation plan and decision evidence.
- [x] Add the colleague-facing `SEEED-LR2021-EVK-FIPS-ONBOARDING.md` runbook.
- [x] Include the implementation status table: documented, host-tested,
      board-tested, RF-tested and FIPS-tested are separate milestones.
- [x] Include antenna/regulatory cautions, no-US915 default, exact board/shield
      names, stable port/probe identification and troubleshooting.
- [x] Link the new runbook from the reference README and layout table.
- [x] Add a results template without inventing measurements.

### Reproducible tooling

- [x] Add `scripts/seeed-usp.sh` as the single setup/build/flash implementation.
- [x] Extend the reference Makefile with `seeed-setup` and `seeed-doctor`.
- [x] Add separate PER receiver/transmitter build and flash targets.
- [x] Add separate FLRP initiator/slave build and flash targets.
- [x] Add a monitor target with mandatory, explicit port selection.
- [x] Keep workspace/toolchain/build output below the local ignored `build/`
      directory; do not install globally or use `/tmp` as persistent storage.
- [x] Validate required variables before west, flash or monitor commands.
- [x] Preserve existing E80, RP2040, host-test and mock-E2E behaviour.
- [x] Ensure commands work with paths containing spaces and use fixed build
      directories for each role.

### Static and host-side validation

- [x] Run `bash -n` and available shell lint checks on the new helper.
- [x] Dry-run every Make target, including expected missing-variable failures.
- [x] Check documentation links, target names and examples against the helper.
- [x] Build both PER roles and both FLRP roles if the isolated toolchain can be
      installed in this environment; record precisely what was or was not run.
- [x] Run the existing host and mock-E2E tests, or record any dependency blocker
      without presenting it as a hardware problem.
- [x] Review the final diff for unrelated changes, secrets and generated files.

### Bench work for the colleague (not claimed by this PR)

- [ ] Record exact SKU, board revision, antennas, host OS, USB/probe identity and
      stock firmware console output before reflashing.
- [ ] Confirm pyOCD/CMSIS-DAP detection and controlled flashing of both boards.
- [ ] Run repeated unmodified FLRC PER series and save complete TX/RX logs.
- [ ] Run FLRP transfers at the default 20 KiB size in both directions.
- [ ] Compare sub-GHz and 2.4 GHz as separate result tables; obey local EIRP,
      duty-cycle and antenna rules rather than treating vendor defaults as a
      regulatory approval.
- [ ] Measure whole-transfer goodput and, where timestamps permit, data-phase
      goodput independently of PHY and gross-burst rates.
- [ ] Sweep FLRP MIC/CRC, packet size and carefully paired radio timing settings
      only after the baseline works and the controls are reproducible.
- [ ] Measure actual UART/USB host goodput at gradually increased rates with
      error checking; determine whether a different host link is necessary.
- [ ] Feed measured summaries and raw log paths back into `docs/RESULTS.md`.

### FIPS follow-up, deliberately outside this first PR

- [ ] Implement a small nRF54L15 bridge exposing the existing bridge protocol
      through Semtech's direct FLRC API; do not substitute FLRP session/file
      semantics for raw packets.
- [ ] Verify host loopback before RF, then bridge-to-bridge packets before FIPS.
- [ ] Reuse `fips-lr2021ctl`, existing PER/soak tools and patched FIPS configs.
- [ ] Prove distinct-node Noise handshake, IPv6 ping, SSH and an iperf3 rate
      ramp, reporting delivered goodput and link-layer loss separately.

### Publication gates

- [ ] Rebase only with explicit approval; do not rewrite shared history.
- [x] Review status and diff one final time.
- [x] Commit only after explicit approval.
- [ ] Push only after explicit approval.
- [ ] Open the PR only after explicit approval, with host evidence and hardware
      limitations stated accurately.

## Validation log

| Date | Check | Result / evidence |
|---|---|---|
| 2026-11-07 | Upstream source and plan research | Completed; no hardware claims |
| 2026-11-07 | Worktree from `origin/master` | `70183172`, clean at creation |
| 2026-11-07 | Helper static checks | `bash -n scripts/seeed-usp.sh` and preinstalled `shellcheck scripts/seeed-usp.sh`: PASS |
| 2026-11-07 | All 11 new targets | Per-target `make -n`: PASS; default `all`, `host-test` and `mock-e2e` recipes unchanged; Seeed work not added to `all` |
| 2026-11-07 | Required-variable and option guards | All four flash targets reject missing `PROBE`; monitor rejects missing `PORT`; invalid FLRP size/booleans and non-commit `USP_ZEPHYR_REF=main` rejected before west/hardware: PASS |
| 2026-11-07 | Reviewed early host-prerequisite guard | `make seeed-setup SEED_USP_WORKSPACE=<new ignored path>` failed on missing host `gperf` with the host-prerequisite message before creating the workspace or starting downloads: PASS. `bash -n`, ShellCheck, all 11 `make -n` checks and missing `PROBE`/`PORT` guards were rerun successfully |
| 2026-11-07 | Host command-construction mocks | Ignored-build fake west/Git invoked all four build roles and all four flash roles, including a workspace path containing spaces, stock/alternate FLRP flags and `west flash --runner pyocd --dev-id`: PASS. This compiled and flashed nothing |
| 2026-11-07 | Documentation consistency | Local relative links in the new plan/runbook/README resolve; runbook contains all exactly 11 new target names; all are phony: PASS |
| 2026-11-07 | Real PER/FLRP compilation (before the isolated host-build attempt) | **Not run at that checkpoint.** No local West workspace/SDK existed; host `west` and `pyocd` were absent and `gperf`/`dtc` were missing. Only command-construction mocks had run. Superseded by the real setup/build results below |
| 2026-11-07 | Existing `make host-test` / `make mock-e2e` | **Not run: dependency absent.** `build/fips` (including its `.git` and `Cargo.toml`) does not exist. The existing bootstrap was not run, per task constraints; this is a host-source prerequisite limitation, not a hardware failure |
| 2026-11-07 | Zephyr SDK installer source check | [Zephyr v4.4.0 `scripts/west_commands/sdk.py`](https://github.com/zephyrproject-rtos/zephyr/blob/v4.4.0/scripts/west_commands/sdk.py): `--install-dir` is the renamed exact destination; `--gnu-toolchains arm-zephyr-eabi` and `--no-hosttools` are valid. Existing root `sdk_version` and `gnu/arm-zephyr-eabi/bin/arm-zephyr-eabi-gcc` checks match that layout |
| 2026-11-08 | Local test-only host prerequisites | PASS. SHA256-verified Ubuntu resolute packages for `gperf` 3.3-1, `device-tree-compiler` 1.7.2-2ubuntu1 and `libfdt1` were extracted with `dpkg-deb` under ignored `build/local-host-tools/` (23 MiB including package indexes). Only local `PATH`/`LD_LIBRARY_PATH` were prepended for this test harness. No system installation, sudo, global pip or weakening of the helper prerequisite checks |
| 2026-11-08 | Real `make seeed-setup` | PASS on the helper-supported retry. The first attempt completed the pinned clone, West init/update and West Python packages, then failed during SDK release discovery because the shared GitHub API quota returned HTTP 403. Retrying after the advertised reset installed SDK 1.0.1 and its ARM GNU toolchain. Verified USP HEAD `64f416bddd5c95ec4504b00627aa932eb88c7bd5`, Zephyr `v4.4.0`, West 1.5.0 and compiler 14.3.0; no helper or upstream edit was needed |
| 2026-11-08 | Real PER/FLRP compilation | PASS: `make seeed-per-build-rx`, `make seeed-per-build-tx`, `make seeed-flrp-build-initiator` and `make seeed-flrp-build-slave` each exited 0 with no compiler/linker warnings or errors. Stock FLRP defaults were used. Raw binary sizes are respectively 118568, 118540, 150428 and 150360 bytes. ELF/HEX/BIN paths, hashes and logs are recorded in ignored `build/seeed-build-validation.log`; workspace footprint after all four builds is about 12 GiB. Compilation only, not hardware validation |
| 2026-11-08 | Post-build helper checks | `bash -n scripts/seeed-usp.sh`, preinstalled `shellcheck scripts/seeed-usp.sh` and `make -n` for setup plus all four build targets: PASS. Real setup/builds exposed no tracked implementation defect requiring a fix |
| 2026-11-08 | Final lead review | PASS: independently reran `bash -n`, ShellCheck, all 11 `make -n` targets and all five missing-`PROBE`/`PORT` guards; checked executable mode, `git diff --check`, scoped status, validation-log artifact hashes and absence of old filenames. No unrelated or generated files are included |
| 2026-11-08 | Hardware/Radio/FIPS | No probe, serial device or board accessed; no flash, RF, host-throughput or FIPS test performed; checklist bench/FIPS items remain open |
