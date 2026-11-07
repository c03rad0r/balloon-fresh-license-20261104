/*
 * e80_lr20xx_raw.h — raw 2-byte-opcode SPI driver for LR2021 on E80-900MBL-02
 *
 * Opcodes and payload formats verified against BOTH sources:
 *   [A] our proven ADR-020 layer (firmware/rp2040/src/multi_radio_sweep.cpp,
 *       git tag rp2040-baseline-1377kbps — proven 1377 kbps E2E FLRC) for the
 *       TX/RX hot-loop command set, IRQ bits, FLRC parameter bytes and timings;
 *   [B] Semtech lr20xx driver v1.3.1 shipped in the E80 demo
 *       (E80_DEMO/E80/Radio/lr20xx_driver + user_radio.c radio_init) for the
 *       E80-module-specific bring-up: TCXO supply config, DC-DC regulator,
 *       SetRfFreq in plain Hz, 3-byte Semtech SetPaCfg form, LF PA tuning,
 *       READ_RX_FIFO framing (0x0001, data immediate, no dummy bytes).
 *
 * SPI framing (Semtech lr20xx_hal.c):
 *   write : wait BUSY low -> NSS low -> opcode+payload -> NSS high
 *   read  : opcode frame -> NSS high -> wait BUSY -> NSS low ->
 *           2 dummy bytes -> payload bytes -> NSS high
 *   fifo  : READ_RX_FIFO is ONE transaction: NSS low -> opcode -> data -> NSS high
 *
 * HOST GLUE — the including translation unit must define these macros BEFORE
 * including this header:
 *   E80_CS_LOW() / E80_CS_HIGH()        — assert/deassert NSS (bit-banged)
 *   E80_SPI_TX(buf, len)                — send only, one CS frame (caller does CS)
 *   E80_SPI_RX(buf, len)                — clock len bytes out, receive into buf
 *                                         (MOSI content ignored; caller does CS)
 *   E80_BUSY_READ()            -> bool  — BUSY pin level (true = busy)
 *   E80_IRQ_READ()             -> bool  — IRQ pin level (true = asserted)
 *   E80_DELAY_US(us) / E80_DELAY_MS(ms)
 *
 * All functions are static inline; no RadioLib, no host SDK types in here.
 */
#pragma once

#include <stdint.h>
#include <string.h>
#include "e80_pinmap.h"

// ─── LR20xx opcodes (Semtech lr20xx v1.3.1 + ADR-020 cross-verified) ──────
enum : uint16_t {
  OC_GET_STATUS      = 0x0100,  // [B] lr20xx_system.c
  OC_GET_VERSION     = 0x0101,  // [B]
  OC_GET_ERRORS      = 0x0110,  // [B]
  OC_CLEAR_ERRORS    = 0x0111,  // [A/B]
  OC_SET_DIO_FUNC    = 0x0112,  // [A/B]
  OC_SET_DIO_IRQ_CFG = 0x0115,  // [A/B]
  OC_CLEAR_IRQ       = 0x0116,  // [A/B]
  OC_GET_IRQ_STATUS  = 0x0117,  // [A/B]
  OC_CFG_LFCLK       = 0x0118,  // [B]
  OC_SET_TCXO_MODE   = 0x0120,  // [B]  E80 CRITICAL (module has TCXO fitted)
  OC_SET_REG_MODE    = 0x0121,  // [B]  E80: DC-DC (demo pairs it with TCXO)
  OC_CALIBRATE       = 0x0122,  // [A/B]
  OC_SET_STANDBY     = 0x0128,  // [A/B]
  OC_CLEAR_RX_FIFO   = 0x011E,  // [B]
  OC_CLEAR_TX_FIFO   = 0x011F,  // [A/B]
  OC_SET_RF_FREQ     = 0x0200,  // [A/B]
  OC_SET_RX_PATH     = 0x0201,  // [A/B]
  OC_SET_PA_CFG      = 0x0202,  // [A/B]
  OC_SET_TX_PARAMS   = 0x0203,  // [A/B]
  OC_SET_FALLBACK    = 0x0206,  // [A/B]
  OC_SET_PKT_TYPE    = 0x0207,  // [A/B]
  OC_SET_RX          = 0x020C,  // [A/B]
  OC_SET_TX          = 0x020D,  // [A/B]
  OC_READ_RX_FIFO    = 0x0001,  // [B] direct_read_fifo framing
  OC_WRITE_TX_FIFO   = 0x0002,  // [A/B]
  OC_FLRC_MOD_PARAMS = 0x0248,  // [A/B]
  OC_FLRC_PKT_PARAMS = 0x0249,  // [A/B]
  OC_FLRC_GET_STATUS = 0x024B,  // [A/B]
  OC_FLRC_SYNCWORD   = 0x024C,  // [A/B]
};

#define PKT_TYPE_FLRC   0x05   // [A] multi_radio_sweep.cpp:64 == [B] LR20XX_PKT_TYPE_FLRC
#define FLRC_PAYLOAD_SZ 255

// IRQ bits (lr20xx_system_types.h, bit positions used by proven firmware)
#define IRQ_RX_DONE    (1UL << 18)
#define IRQ_TX_DONE    (1UL << 19)
#define IRQ_TIMEOUT    (1UL << 21)
#define IRQ_CRC_ERROR  (1UL << 22)

// TCXO / regulator constants (E80 demo user_radio.c radio_init, TXCO path)
#define TCXO_VOLT_2_2V        0x03      // LR20XX_SYSTEM_TCXO_CTRL_2_2V
#define TCXO_STARTUP_RTC_STEPS 64000UL  // demo value for ~2 ms TCXO startup
#define REG_MODE_DCDC         0x02      // LR20XX_SYSTEM_REG_MODE_DCDC

// ─── BUSY / low-level ────────────────────────────────────────────────────
static inline bool rfBusy() { return E80_BUSY_READ(); }
static inline bool rfIrq()  { return E80_IRQ_READ(); }

// Returns true if BUSY went low within timeout, false = timeout (wire fault /
// radio held in reset). Proven spin count from multi_radio_sweep.cpp:110-114.
static inline bool rfWaitBusy(uint32_t spin_limit = 100000) {
  uint32_t n = spin_limit;
  while (E80_BUSY_READ() && --n) E80_DELAY_US(1);
  return n > 0;
}

// ─── SPI primitives (Semtech lr20xx_hal framing) ──────────────────────────
// Write: one CS frame, opcode+payload together (lr20xx_hal_write).
static inline void rfWriteCmd(const uint8_t* buf, size_t len) {
  rfWaitBusy();
  E80_CS_LOW();
  E80_SPI_TX(buf, len);
  E80_CS_HIGH();
}

// Read: opcode frame, then separate data frame preceded by 2 dummy bytes
// (lr20xx_hal_read). `out` receives ONLY payload (dummies stripped).
static inline void rfReadCmd(const uint8_t* cmd, size_t clen, uint8_t* out, size_t rlen) {
  rfWaitBusy();
  E80_CS_LOW();
  E80_SPI_TX(cmd, clen);
  E80_CS_HIGH();

  rfWaitBusy();
  uint8_t tmp[64];  // 2 dummies + max payload we read here
  size_t n = 2 + rlen;
  if (n > sizeof(tmp)) n = sizeof(tmp);
  memset(tmp, 0, sizeof(tmp));
  E80_CS_LOW();
  E80_SPI_RX(tmp, n);
  E80_CS_HIGH();
  if (rlen > n - 2) rlen = n - 2;
  memcpy(out, tmp + 2, rlen);
}

static inline void rfWrite2(uint16_t oc, const uint8_t* payload, size_t plen) {
  uint8_t b[16];
  b[0] = (uint8_t)(oc >> 8);
  b[1] = (uint8_t)(oc & 0xFF);
  if (plen) memcpy(b + 2, payload, plen);
  rfWriteCmd(b, 2 + plen);
}

// ─── System commands ──────────────────────────────────────────────────────
// GET_VERSION 0x0101 → 2 payload bytes [major, minor] (lr20xx_system.c:230-248)
static inline uint16_t rfGetVersion(uint8_t* raw4) {
  uint8_t cmd[2] = {0x01, 0x01};
  uint8_t out[4] = {0, 0, 0, 0};
  rfReadCmd(cmd, 2, out, 4);              // 4th byte kept for scope/debug
  if (raw4) memcpy(raw4, out, 4);
  return (uint16_t)((out[0] << 8) | out[1]);
}

// GET_ERRORS 0x0110 → 2-byte BE error bitmap
static inline uint16_t rfGetErrors() {
  uint8_t cmd[2] = {0x01, 0x10};
  uint8_t out[2] = {0, 0};
  rfReadCmd(cmd, 2, out, 2);
  return (uint16_t)((out[0] << 8) | out[1]);
}

// CLEAR_ERRORS — proven ADR-020 form {0x01,0x11,0x00,0x00}
static inline void rfClearErrors() {
  uint8_t p[2] = {0x00, 0x00};
  rfWrite2(OC_CLEAR_ERRORS, p, 2);
}

// GET_IRQ_STATUS 0x0117 → 4-byte BE irq flags (read frame: 2 dummies + 4)
static inline uint32_t rfGetIrqStatus() {
  uint8_t cmd[2] = {0x01, 0x17};
  uint8_t out[4] = {0, 0, 0, 0};
  rfReadCmd(cmd, 2, out, 4);
  return ((uint32_t)out[0] << 24) | ((uint32_t)out[1] << 16) |
         ((uint32_t)out[2] << 8)  | (uint32_t)out[3];
}

static inline void rfClearIrq() {          // 0x0116 + all-ones mask (proven)
  uint8_t p[4] = {0xFF, 0xFF, 0xFF, 0xFF};
  rfWrite2(OC_CLEAR_IRQ, p, 4);
}

// ─── THE E80 module-specific fix: TCXO bring-up ───────────────────────────
// Ports E80_DEMO user_radio.c radio_init() TXCO branch verbatim:
//   set_reg_mode(DCDC) then set_tcxo_mode(2.2V, 64000 RTC steps).
// Without this the radio never sees its 32 MHz clock (module has a TCXO, our
// custom boards had a plain crystal and never sent these commands).
static inline void rfSetRegModeDcdc() {
  uint8_t p = REG_MODE_DCDC;
  rfWrite2(OC_SET_REG_MODE, &p, 1);
}

static inline void rfSetTcxoMode2V2() {
  uint8_t p[5] = { TCXO_VOLT_2_2V,
                   (uint8_t)(TCXO_STARTUP_RTC_STEPS >> 24),
                   (uint8_t)(TCXO_STARTUP_RTC_STEPS >> 16),
                   (uint8_t)(TCXO_STARTUP_RTC_STEPS >> 8),
                   (uint8_t)(TCXO_STARTUP_RTC_STEPS & 0xFF) };
  rfWrite2(OC_SET_TCXO_MODE, p, 5);
}

static inline void rfCfgLfClkRc() {         // 0x0118, LFCLK_RC = 0x00
  uint8_t p = 0x00;
  rfWrite2(OC_CFG_LFCLK, &p, 1);
}

static inline void rfCalibrateAll() {       // demo mask 0x7F (all blocks)
  uint8_t p = 0x7F;
  rfWrite2(OC_CALIBRATE, &p, 1);
}

static inline void rfSetStandbyXosc() {     // 0x0128 param 0x01 (proven)
  uint8_t p = 0x01;
  rfWrite2(OC_SET_STANDBY, &p, 1);
}

// SET_DIO_FUNCTION 0x0112: {dio, (func<<4)|drive} — E80 uses DIO8 as IRQ
// with pull-down (demo: DIO_8/DIO_FUNC_IRQ/DRIVE_PULL_DOWN == 0x08,0x11).
static inline void rfSetDioIrqFunction() {
  uint8_t p[2] = { (uint8_t)E80_RADIO_IRQ_DIO, 0x11 };
  rfWrite2(OC_SET_DIO_FUNC, p, 2);
}

// SET_DIO_IRQ_CFG 0x0115: {dio, irq_mask BE32} (proven ADR-020 form)
static inline void rfSetDioIrqMask(uint32_t mask) {
  uint8_t p[5] = { (uint8_t)E80_RADIO_IRQ_DIO,
                   (uint8_t)(mask >> 24), (uint8_t)(mask >> 16),
                   (uint8_t)(mask >> 8),  (uint8_t)(mask & 0xFF) };
  rfWrite2(OC_SET_DIO_IRQ_CFG, p, 5);
}

static inline void rfClearRxFifo() { rfWrite2(OC_CLEAR_RX_FIFO, nullptr, 0); }
static inline void rfClearTxFifo() { rfWrite2(OC_CLEAR_TX_FIFO, nullptr, 0); }

// ─── Radio commands ───────────────────────────────────────────────────────
// SetRfFreq 0x0200 — E80/demo form: 4-byte big-endian plain Hz
// (lr20xx_radio_common.c:238-249). Our custom boards used an SX1280-style
// frf value; that is NOT what the E80 demo sends — kept as compile-time
// selectable so a bench can A/B if frequency verification misbehaves.
#ifndef E80_RFREQ_FRF
#define E80_RFREQ_FRF 0
#endif

static inline void rfSetRfFreqHz(uint32_t hz) {
#if E80_RFREQ_FRF
  // legacy custom-board form: frf = f * 2^18 / 52 MHz, 3 payload bytes
  uint32_t frf = (uint32_t)(((uint64_t)hz << 18) / 52000000ULL);
  uint8_t p[3] = { (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF) };
  rfWrite2(OC_SET_RF_FREQ, p, 3);
#else
  uint8_t p[4] = { (uint8_t)(hz >> 24), (uint8_t)(hz >> 16),
                   (uint8_t)(hz >> 8),  (uint8_t)(hz & 0xFF) };
  rfWrite2(OC_SET_RF_FREQ, p, 4);
#endif
}

// SetRxPath 0x0201: {path, boost} — LF=0x00/HF=0x01, boost none=0x00 (demo)
static inline void rfSetRxPath(uint8_t hf) {
  uint8_t p[2] = { (uint8_t)(hf ? 0x01 : 0x00), 0x00 };
  rfWrite2(OC_SET_RX_PATH, p, 2);
}

// SetPaCfg 0x0202 — Semtech 3-byte form for the E80 LF PA
// (user_radio.c 900 MHz branch: sel=LF, FSM, duty=7, slices=6, hf_duty=16
//  → bytes {0x00, 0x76, 0x10}). Our custom-board 5-byte form does NOT apply.
static inline void rfSetPaCfgLf() {
  uint8_t p[3] = { 0x00, 0x76, 0x10 };
  rfWrite2(OC_SET_PA_CFG, p, 3);
}

// SetTxParams 0x0203: {power_half_db, ramp} — ramp 0x04 (~20 µs, proven)
// LF clamp per demo: max 0x2C (=+22 dBm)
static inline void rfSetTxParams(uint8_t power_half_db) {
  if (power_half_db > 0x2C) power_half_db = 0x2C;
  uint8_t p[2] = { power_half_db, 0x04 };
  rfWrite2(OC_SET_TX_PARAMS, p, 2);
}

// SetRxTxFallbackMode 0x0206 — 0x03 = FS mode (fast re-arm, proven hot loop)
static inline void rfSetFallbackFs() {
  uint8_t p = 0x03;
  rfWrite2(OC_SET_FALLBACK, &p, 1);
}

static inline void rfSetPacketTypeFlrc() {
  uint8_t p = PKT_TYPE_FLRC;
  rfWrite2(OC_SET_PKT_TYPE, &p, 1);
}

static inline void rfSetRx() {              // 0x020C, max timeout (proven)
  uint8_t p[3] = {0xFF, 0xFF, 0xFF};
  rfWrite2(OC_SET_RX, p, 3);
}

static inline void rfSetTx() {              // 0x020D, no timeout (proven)
  uint8_t p[3] = {0x00, 0x00, 0x00};
  rfWrite2(OC_SET_TX, p, 3);
}

// WRITE_TX_FIFO 0x0002 — one CS frame, opcode+payload (proven batched form)
static inline void rfWriteTxFifo(const uint8_t* data, size_t len) {
  rfWaitBusy();
  uint8_t hdr[2] = { (uint8_t)(OC_WRITE_TX_FIFO >> 8), (uint8_t)(OC_WRITE_TX_FIFO & 0xFF) };
  E80_CS_LOW();
  E80_SPI_TX(hdr, 2);
  E80_SPI_TX(data, len);
  E80_CS_HIGH();
}

// READ_RX_FIFO 0x0001 — ONE CS frame, opcode then payload immediately, no
// dummy bytes (lr20xx_hal_direct_read_fifo; NOT the command-read framing).
static inline void rfReadRxFifo(uint8_t* out, size_t len) {
  rfWaitBusy();
  uint8_t hdr[2] = { (uint8_t)(OC_READ_RX_FIFO >> 8), (uint8_t)(OC_READ_RX_FIFO & 0xFF) };
  size_t chunk, done = 0;
  E80_CS_LOW();
  E80_SPI_TX(hdr, 2);
  while (done < len) {                       // chunked to bound scratch size
    chunk = len - done;
    if (chunk > 64) chunk = 64;
    E80_SPI_RX(out + done, chunk);
    done += chunk;
  }
  E80_CS_HIGH();
}

// ─── FLRC ─────────────────────────────────────────────────────────────────
// br_bw codes — [A]==[B] (650 kbps/BW740k = 0x04)
static inline uint8_t rfFlrcBrCode(uint32_t kbps) {
  switch (kbps) {
    case 2600: return 0x00;
    case 2080: return 0x01;
    case 1300: return 0x02;
    case 1040: return 0x03;
    case 650:  return 0x04;
    case 520:  return 0x05;
    case 325:  return 0x06;
    case 260:  return 0x07;
    default:   return 0x04;
  }
}

// SET_FLRC_MODULATION_PARAMS 0x0248 {br_bw, (cr<<4)|bt} — proven bytes 0x25
// (cr code 2, BT 1.0 == multi_radio_sweep.cpp:350)
#ifndef E80_MOD_BYTE1
#define E80_MOD_BYTE1 0x25
#endif

static inline void rfFlrcSetModParams(uint32_t kbps) {
  uint8_t p[2] = { rfFlrcBrCode(kbps), (uint8_t)E80_MOD_BYTE1 };
  rfWrite2(OC_FLRC_MOD_PARAMS, p, 2);
}

// SET_FLRC_SYNC_WORD 0x024C {index, w0..w3} — proven sync 0x12AD101B, index 1
static inline void rfFlrcSetSyncWord() {
  uint8_t p[5] = { 0x01, 0x12, 0xAD, 0x10, 0x1B };
  rfWrite2(OC_FLRC_SYNCWORD, p, 5);
}

// SET_FLRC_PACKET_PARAMS 0x0249 — proven bytes {0x0C, 0x4C, lenHi, lenLo}
// (multi_radio_sweep.cpp:358; layout == lr20xx_radio_flrc.c:192-205)
#ifndef E80_PKT_BYTE0
#define E80_PKT_BYTE0 0x0C
#endif
#ifndef E80_PKT_BYTE1
#define E80_PKT_BYTE1 0x4C
#endif

static inline void rfFlrcSetPktParams(uint16_t payload_len) {
  uint8_t p[4] = { (uint8_t)E80_PKT_BYTE0, (uint8_t)E80_PKT_BYTE1,
                   (uint8_t)(payload_len >> 8), (uint8_t)(payload_len & 0xFF) };
  rfWrite2(OC_FLRC_PKT_PARAMS, p, 4);
}

// GET_FLRC_PACKET_STATUS 0x024B → [lenHi lenLo rssiAvg rssiSync flags]
// (lr20xx_radio_flrc.c:230-255). rssi bytes: dBm = -byte (half-dB lsb in flags)
struct FlrcPktStatus {
  uint16_t len;
  int16_t  rssi_avg_dbm;
  int16_t  rssi_sync_dbm;
  uint8_t  flags;   // bit0 = sync half-dB, bit2 = avg half-dB, hi nibble sw idx
  uint8_t  raw[5];
};

static inline void rfFlrcGetPktStatus(FlrcPktStatus* st) {
  uint8_t cmd[2] = { (uint8_t)(OC_FLRC_GET_STATUS >> 8), (uint8_t)(OC_FLRC_GET_STATUS & 0xFF) };
  uint8_t out[5] = {0};
  rfReadCmd(cmd, 2, out, 5);
  memcpy(st->raw, out, 5);
  st->len          = (uint16_t)((out[0] << 8) | out[1]);
  st->rssi_avg_dbm  = (int16_t)(-(int16_t)out[2]);
  st->rssi_sync_dbm = (int16_t)(-(int16_t)out[3]);
  st->flags         = out[4];
}

// ─── Full E80 bring-up (TCXO path) ────────────────────────────────────────
// Sequence merges the E80 demo radio_init() (TCXO/regulator/LFCLK/calibrate)
// with our proven FLRC config ordering. Caller must have configured host pins
// and performed the hard reset (rfHardReset) first.
//   rfHardReset: NRST low ≥10 ms → high → wait 50 ms (demo hal_reset budget)
//
// Returns 0 on success; nonzero = first failing step (1=BUSY stuck, 2=chip
// identity bad). `init_errors` (optional) receives the error bitmap observed
// right after TCXO+calibration — the demo prints-but-clears these; nonzero
// there is informational, not fatal.
static inline int rfInitE80Flrc(uint32_t freq_hz, uint32_t flrc_kbps,
                                uint8_t tx_power_half_db, uint32_t irq_mask,
                                uint8_t* version_raw4, uint16_t* init_errors) {
  // -- TCXO module bring-up (E80 demo user_radio.c radio_init, TXCO branch) --
  rfGetErrors();
  rfClearErrors();
  rfSetRegModeDcdc();                       // 0x0121 DC-DC (demo pairs w/TCXO)
  rfSetTcxoMode2V2();                       // 0x0120 2.2V, 64000 RTC steps
  E80_DELAY_MS(5);
  rfCfgLfClkRc();                           // 0x0118 RC
  rfCalibrateAll();                         // 0x0122 mask 0x7F
  E80_DELAY_MS(5);
  uint16_t errs = rfGetErrors();            // demo re-checks errors here
  if (init_errors) *init_errors = errs;
  rfClearErrors();
  rfSetStandbyXosc();                       // 0x0128 XOSC (=TCXO source now)
  E80_DELAY_MS(5);

  // -- identity: GET_VERSION must return plausible bytes (not 00/FF pattern) --
  uint16_t ver = rfGetVersion(version_raw4);
  if (version_raw4) {
    bool allZero = version_raw4[0] == 0 && version_raw4[1] == 0 &&
                   version_raw4[2] == 0 && version_raw4[3] == 0;
    bool allFF   = version_raw4[0] == 0xFF && version_raw4[1] == 0xFF &&
                   version_raw4[2] == 0xFF && version_raw4[3] == 0xFF;
    if (allZero || allFF) return 2;         // MISO stuck low/high → wiring
  }

  // -- FLRC radio config (proven ordering from multi_radio_sweep init) --
  rfSetDioIrqFunction();                    // DIO8 = IRQ, pull-down
  rfSetPacketTypeFlrc();                    // 0x0207 = 0x05
  rfSetRfFreqHz(freq_hz);                   // 0x0200 plain Hz (E80 form)
  rfSetRxPath(0 /*LF*/);                    // 0x0201
  rfSetPaCfgLf();                           // 0x0202 {0x00,0x76,0x10}
  rfSetTxParams(tx_power_half_db);          // 0x0203
  rfSetFallbackFs();                        // 0x0206 = 0x03
  rfFlrcSetSyncWord();                      // 0x024C
  rfFlrcSetModParams(flrc_kbps);            // 0x0248
  rfFlrcSetPktParams(FLRC_PAYLOAD_SZ);      // 0x0249
  rfSetDioIrqMask(irq_mask);                // 0x0115 DIO8
  rfClearTxFifo();
  rfClearRxFifo();
  rfClearIrq();

  // -- liveness: IRQ status register must read back (BUSY protocol working) --
  if (!rfWaitBusy()) return 1;
  (void)ver;
  return 0;
}
