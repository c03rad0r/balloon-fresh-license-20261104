/*
 * e80_pinmap.h — host GPIO maps for E80-900MBL-02 SPI-bypass (ADR: E80 bypass)
 *
 * Single source of truth for host pin assignments, shared by:
 *   - firmware/e80-bypass/rp2040/    (PlatformIO, earlephilhower core)
 *   - firmware/e80-bypass/esp32c3/   (ESP-IDF)
 *   - tests/test_e80_bypass.py       (native compile: static_asserts run there too)
 *
 * Ground truth: docs/e80-900mbl-02-eval/E80-SPI-BYPASS-WIRING.md §6 tables.
 *   Host1 RP2040  : SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ(DIO8)=GP7 RST=GP8
 *                   (mirrors firmware/rp2040/src/multi_radio_sweep.cpp:49-56)
 *   Host2 ESP32-C3: SCK=6 MOSI=7 MISO=2 NSS=10 BUSY=4 IRQ(DIO8)=5 RST=3
 *                   (mirrors mesh-stack/flrc-bench-espidf/main/esp32_raw_tx.cpp:27-33)
 * On the E80 side, IRQ is DIO8 on J2-10 and radio NRST is J2-5 (wiring doc §2).
 *
 * The static_asserts below fail the BUILD if a pin ever drifts from the wiring
 * doc — they also fire in the native unit test (tests/test_e80_bypass.py).
 *
 * Host selection (define exactly one before including):
 *   E80_HOST_RP2040  /  E80_HOST_ESP32C3
 * For native tests neither is defined and only the checks compile.
 */
#pragma once

#include <stdint.h>

// ─── Wiring-doc constants (E80-SPI-BYPASS-WIRING.md §6, final wiring tables) ───
#define E80_DOC_RP2040_SCK    2    // J2-13 SCK   ↔ GP2
#define E80_DOC_RP2040_MOSI   3    // J2-11 MOSI  ↔ GP3
#define E80_DOC_RP2040_MISO   4    // J2-9  MISO  ↔ GP4
#define E80_DOC_RP2040_CS     5    // J2-15 NSS   ↔ GP5
#define E80_DOC_RP2040_BUSY   6    // J2-7  BUSY  ↔ GP6
#define E80_DOC_RP2040_IRQ    7    // J2-10 DIO8  ↔ GP7
#define E80_DOC_RP2040_RST    8    // J2-5  NRST  ↔ GP8

#define E80_DOC_ESP32C3_SCK   6    // J2-13 SCK   ↔ GPIO6
#define E80_DOC_ESP32C3_MOSI  7    // J2-11 MOSI  ↔ GPIO7
#define E80_DOC_ESP32C3_MISO  2    // J2-9  MISO  ↔ GPIO2
#define E80_DOC_ESP32C3_CS    10   // J2-15 NSS   ↔ GPIO10
#define E80_DOC_ESP32C3_BUSY  4    // J2-7  BUSY  ↔ GPIO4
#define E80_DOC_ESP32C3_IRQ   5    // J2-10 DIO8  ↔ GPIO5
#define E80_DOC_ESP32C3_RST   3    // J2-5  NRST  ↔ GPIO3

// DIO line the E80 module uses for IRQ (demo firmware primary; wiring doc §7.4)
#ifndef E80_RADIO_IRQ_DIO
#define E80_RADIO_IRQ_DIO     8    // DIO8 — SET_DIO_FUNCTION dio index
#endif

#if defined(E80_HOST_RP2040)

  #define PIN_SCK   2
  #define PIN_MOSI  3
  #define PIN_MISO  4
  #define PIN_CS    5
  #define PIN_BUSY  6
  #define PIN_IRQ   7
  #define PIN_RST   8
  #define PIN_LED   25     // Pico onboard LED (host-local, not in wiring doc)
  #define PIN_ROLE   15    // role strap: input pullup; GND = RX, open = TX (host-local)

  static_assert(PIN_SCK  == E80_DOC_RP2040_SCK,  "RP2040 SCK must be GP2  (wiring doc §6 host1)");
  static_assert(PIN_MOSI == E80_DOC_RP2040_MOSI, "RP2040 MOSI must be GP3 (wiring doc §6 host1)");
  static_assert(PIN_MISO == E80_DOC_RP2040_MISO, "RP2040 MISO must be GP4 (wiring doc §6 host1)");
  static_assert(PIN_CS   == E80_DOC_RP2040_CS,   "RP2040 CS must be GP5  (wiring doc §6 host1)");
  static_assert(PIN_BUSY == E80_DOC_RP2040_BUSY, "RP2040 BUSY must be GP6 (wiring doc §6 host1)");
  static_assert(PIN_IRQ  == E80_DOC_RP2040_IRQ,  "RP2040 IRQ must be GP7 (wiring doc §6 host1: J2-10 DIO8)");
  static_assert(PIN_RST  == E80_DOC_RP2040_RST,  "RP2040 RST must be GP8 (wiring doc §6 host1: J2-5 NRST)");

  #define E80_HOST_NAME "RP2040-Pico"

#elif defined(E80_HOST_ESP32C3)

  #define PIN_SCK   6
  #define PIN_MOSI  7
  #define PIN_MISO  2
  #define PIN_CS    10
  #define PIN_BUSY  4
  #define PIN_IRQ   5
  #define PIN_RST   3
  #define PIN_LED   8      // dev-board LED (host-local, not in wiring doc)
  #define PIN_ROLE  9      // role strap: BOOT button; pressed (LOW) = RX, released = TX

  static_assert(PIN_SCK  == E80_DOC_ESP32C3_SCK,  "ESP32-C3 SCK must be GPIO6  (wiring doc §6 host2)");
  static_assert(PIN_MOSI == E80_DOC_ESP32C3_MOSI, "ESP32-C3 MOSI must be GPIO7 (wiring doc §6 host2)");
  static_assert(PIN_MISO == E80_DOC_ESP32C3_MISO, "ESP32-C3 MISO must be GPIO2 (wiring doc §6 host2)");
  static_assert(PIN_CS   == E80_DOC_ESP32C3_CS,   "ESP32-C3 NSS must be GPIO10 (wiring doc §6 host2)");
  static_assert(PIN_BUSY == E80_DOC_ESP32C3_BUSY, "ESP32-C3 BUSY must be GPIO4 (wiring doc §6 host2)");
  static_assert(PIN_IRQ  == E80_DOC_ESP32C3_IRQ,  "ESP32-C3 IRQ must be GPIO5 (wiring doc §6 host2: J2-10 DIO8)");
  static_assert(PIN_RST  == E80_DOC_ESP32C3_RST,  "ESP32-C3 RST must be GPIO3 (wiring doc §6 host2: J2-5 NRST)");

  #define E80_HOST_NAME "ESP32-C3"

#elif defined(E80_HOST_NATIVE)

  // Native test build: only the doc constants above are visible; the test
  // re-includes this header with a host defined to exercise the asserts.

#else
  #error "Define E80_HOST_RP2040, E80_HOST_ESP32C3 (or E80_HOST_NATIVE for tests) before e80_pinmap.h"
#endif
