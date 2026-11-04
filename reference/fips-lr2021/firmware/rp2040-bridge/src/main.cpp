// RP2040 + E80/LR2021 bridge for FIPS over FLRC.
//
// USB CDC carries the binary host protocol; UART1 is human-readable logging.
// The radio is driven from one place only: loop() polls DIO8 and the host TX
// path calls txPacket(). No second task touches the radio state machine.

#include <Arduino.h>
#include <SPI.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#define E80_HOST_RP2040
#include "e80_pinmap.h"

static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(4000000, MSBFIRST, SPI_MODE0);

#define E80_CS_LOW()      do { spiRf.beginTransaction(spiSettings); digitalWrite(PIN_CS, LOW); } while (0)
#define E80_CS_HIGH()     do { digitalWrite(PIN_CS, HIGH); spiRf.endTransaction(); } while (0)
#define E80_SPI_TX(b, n)  spiRf.transfer(const_cast<uint8_t*>(b), nullptr, n)
#define E80_SPI_RX(b, n)  spiRf.transfer(b, n)
#define E80_BUSY_READ()   (digitalRead(PIN_BUSY) == HIGH)
#define E80_IRQ_READ()    (digitalRead(PIN_IRQ) == HIGH)
#define E80_DELAY_US(us)  delayMicroseconds(us)
#define E80_DELAY_MS(ms)  delay(ms)

#include "e80_lr20xx_raw.h"
#include "bridge_protocol.h"

static const uint8_t FW_VERSION[3] = {0, 1, 0};
static const uint16_t CAPS = 0x0001 | 0x0002 | 0x0004;  // LF, HF, relay

static CfgPayload gCfg;
static uint8_t gChipVersion[4] = {0};
static uint32_t gStatsTx = 0;
static uint32_t gStatsRx = 0;
static uint32_t gStatsCrc = 0;
static uint32_t gStatsDrops = 0;
static uint32_t gStatsTimeouts = 0;
static uint32_t gStatsResets = 0;
static uint32_t gLastRadioOkMs = 0;
static uint32_t gLastRadioInitMs = 0;
static uint32_t gLastStatMs = 0;
static bool gRadioOk = false;

static BridgeDecoder gDecoder;

// Last packets repeated by relay mode, to stop an immediate loop.
static const size_t RELAY_CACHE = 16;
static uint32_t gRelayHash[RELAY_CACHE] = {0};
static uint32_t gRelayAt[RELAY_CACHE] = {0};
static size_t gRelayNext = 0;

/* Serial1 logging defaults on (GP12/GP13 free, as on the E80 SPI bypass).
 * Build with -D E80_BRIDGE_UART_LOG=0 on carriers where those pins belong to
 * another peripheral (e.g. the GPS UART on the dual-RP2040 carrier). */
#ifndef E80_BRIDGE_UART_LOG
#define E80_BRIDGE_UART_LOG 1
#endif

/* Poll the radio's IRQ status register over SPI instead of reading the module's
 * DIO line. Needed on carriers where the IRQ is not routed to a usable GPIO
 * (their sweep firmware may use a different DIO, or none at all). */
#ifndef E80_BRIDGE_POLL_IRQ
#define E80_BRIDGE_POLL_IRQ 0
#endif

static void logf(const char* fmt, ...) {
#if E80_BRIDGE_UART_LOG
  char buf[240];
  va_list args;
  va_start(args, fmt);
  vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);
  Serial1.println(buf);
#else
  (void)fmt;
#endif
}

static void sendFrame(uint8_t kind, const uint8_t* payload, uint16_t len) {
  uint8_t out[BRIDGE_MAX_PAYLOAD + 16];
  size_t n = bridgeEncode(kind, payload, len, out, sizeof(out));
  if (n) Serial.write(out, n);
}

static void sendEvent(const char* text) {
  sendFrame(BR_EVT, (const uint8_t*)text, (uint16_t)strlen(text));
}

static void sendStat() {
  uint8_t p[24];
  uint32_t values[6] = {gStatsTx, gStatsRx, gStatsCrc, gStatsDrops,
                        gStatsTimeouts, gStatsResets};
  for (int i = 0; i < 6; i++) {
    p[i * 4 + 0] = (uint8_t)(values[i] & 0xFF);
    p[i * 4 + 1] = (uint8_t)((values[i] >> 8) & 0xFF);
    p[i * 4 + 2] = (uint8_t)((values[i] >> 16) & 0xFF);
    p[i * 4 + 3] = (uint8_t)((values[i] >> 24) & 0xFF);
  }
  sendFrame(BR_STAT, p, sizeof(p));
}

static void rfHardReset() {
  digitalWrite(PIN_RST, LOW);
  delay(20);
  digitalWrite(PIN_RST, HIGH);
  delay(50);
}

static uint8_t powerHalfDb(int8_t dbm) {
  int v = (int)dbm * 2;
  if (v < -20) v = -20;
  if (v > 44) v = 44;  // +22 dBm
  return (uint8_t)v;
}

static void setPaHf() {
  // Proven HF PA config from the ESP32-C3 2.4 GHz bring-up.
  uint8_t p[5] = {0x80, 0x00, 0x60, 0x07, 0x10};
  rfWrite2(OC_SET_PA_CFG, p, 5);
}

static void setSyncWord(const uint8_t sync[4]) {
  uint8_t p[5] = {0x01, sync[0], sync[1], sync[2], sync[3]};
  rfWrite2(OC_FLRC_SYNCWORD, p, 5);
}

static int radioInit(const CfgPayload& cfg) {
  rfHardReset();
  rfGetErrors();
  rfClearErrors();
  rfSetRegModeDcdc();
  rfSetTcxoMode2V2();
  delay(5);
  rfCfgLfClkRc();
  rfCalibrateAll();
  delay(5);
  (void)rfGetErrors();
  rfClearErrors();
  rfSetStandbyXosc();
  delay(5);

  if (rfGetVersion(gChipVersion) == 0) return 2;
  bool all_zero = !gChipVersion[0] && !gChipVersion[1] && !gChipVersion[2] && !gChipVersion[3];
  bool all_ff = gChipVersion[0] == 0xFF && gChipVersion[1] == 0xFF &&
                gChipVersion[2] == 0xFF && gChipVersion[3] == 0xFF;
  if (all_zero || all_ff) return 2;

  rfSetDioIrqFunction();
  rfSetPacketTypeFlrc();
  rfSetRfFreqHz(cfg.frequency_hz);
  rfSetRxPath(cfg.sub_ghz ? 0 : 1);
  if (cfg.sub_ghz) {
    rfSetPaCfgLf();
  } else {
    setPaHf();
  }
  rfSetTxParams(powerHalfDb(cfg.tx_power_dbm));
  rfSetFallbackFs();
  setSyncWord(cfg.sync_word);
  rfFlrcSetModParams(cfg.bitrate_kbps);
  rfFlrcSetPktParams(cfg.radio_payload);
  rfSetDioIrqMask(IRQ_RX_DONE | IRQ_TX_DONE | IRQ_CRC_ERROR);
  rfClearTxFifo();
  rfClearRxFifo();
  rfClearIrq();
  if (!rfWaitBusy()) return 1;
  rfSetRx();
  return 0;
}

static bool radioApply(const CfgPayload& cfg) {
  int rc = radioInit(cfg);
  gLastRadioInitMs = millis();
  gRadioOk = (rc == 0);
  if (gRadioOk) {
    gLastRadioOkMs = millis();
  } else {
    gStatsResets++;
    logf("radio init failed rc=%d ver=%02X%02X%02X%02X", rc, gChipVersion[0],
         gChipVersion[1], gChipVersion[2], gChipVersion[3]);
    sendEvent("radio init failed");
  }
  return gRadioOk;
}

static void radioRearm() {
  rfClearErrors();
  rfClearIrq();
  rfSetRx();
}

// The radio is configured fixed-length, so trim the padded packet to the link
// frame's declared length before handing it to the host. This is the same fix
// the old PTY bridge needed; it keeps the host parser strict.
static size_t frameLength(const uint8_t* data, size_t len) {
  if (len < 20) return len;
  if (data[0] != 0xF1 || data[1] != 0x50) return len;
  if ((data[2] >> 4) != 1) return len;
  size_t payload = (size_t)data[18] | ((size_t)data[19] << 8);
  size_t total = 20 + payload + 4;
  return total <= len ? total : len;
}

static bool relayDuplicate(const uint8_t* data, size_t len) {
  uint32_t h = 2166136261u;
  for (size_t i = 0; i < len; i++) {
    h ^= data[i];
    h *= 16777619u;
  }
  uint32_t now = millis();
  for (size_t i = 0; i < RELAY_CACHE; i++) {
    if (gRelayHash[i] == h && (now - gRelayAt[i]) < 2000) return true;
  }
  gRelayHash[gRelayNext] = h;
  gRelayAt[gRelayNext] = now;
  gRelayNext = (gRelayNext + 1) % RELAY_CACHE;
  return false;
}

static void txPacket(const uint8_t* data, size_t len) {
  if (!gRadioOk || len == 0 || len > gCfg.radio_payload) return;
  rfClearErrors();
  rfClearIrq();
  rfClearTxFifo();
  rfWriteTxFifo(data, len);
  rfSetTx();
  gStatsTx++;

  uint32_t start = millis();
  bool done = false;
  while ((millis() - start) < 60) {
#if E80_BRIDGE_POLL_IRQ
    uint32_t irq = rfGetIrqStatus();
#else
    if (!rfIrq()) continue;
    uint32_t irq = rfGetIrqStatus();
#endif
    if (irq & IRQ_TX_DONE) {
      done = true;
      break;
    }
    if (irq & IRQ_CRC_ERROR) {
      break;
    }
  }
  if (!done) gStatsTimeouts++;
  gLastRadioOkMs = millis();
  rfClearIrq();
  radioRearm();
}

static void handleRx() {
#if E80_BRIDGE_POLL_IRQ
  uint32_t irq = rfGetIrqStatus();
  if (!(irq & (IRQ_RX_DONE | IRQ_CRC_ERROR))) return;
#else
  if (!rfIrq()) return;
  uint32_t irq = rfGetIrqStatus();
#endif
  if (irq & IRQ_CRC_ERROR) {
    gStatsCrc++;
    rfClearRxFifo();
    rfClearIrq();
    radioRearm();
    return;
  }
  if (!(irq & IRQ_RX_DONE)) {
    rfClearIrq();
    radioRearm();
    return;
  }

  FlrcPktStatus status;
  rfFlrcGetPktStatus(&status);
  uint8_t buf[255];
  size_t want = status.len ? status.len : gCfg.radio_payload;
  if (want > sizeof(buf)) want = sizeof(buf);
  rfReadRxFifo(buf, want);
  size_t len = frameLength(buf, want);

  if (len > 0) {
    uint8_t payload[6 + 255];
    payload[0] = (uint8_t)(status.rssi_avg_dbm & 0xFF);
    payload[1] = (uint8_t)((status.rssi_avg_dbm >> 8) & 0xFF);
    payload[2] = 0;  // FLRC SNR is not exposed by this status frame
    payload[3] = 1;  // CRC already checked above
    payload[4] = (uint8_t)(len & 0xFF);
    payload[5] = (uint8_t)(len >> 8);
    memcpy(payload + 6, buf, len);
    sendFrame(BR_RX, payload, (uint16_t)(6 + len));
    gStatsRx++;
    gLastRadioOkMs = millis();

    if (gCfg.relay && !relayDuplicate(buf, len)) {
      delayMicroseconds(1200);
      txPacket(buf, len);
    }
  } else {
    gStatsDrops++;
  }

  rfClearRxFifo();
  rfClearIrq();
  radioRearm();
}

static void handleHello() {
  uint8_t p[8];
  p[0] = 1;  // protocol
  p[1] = FW_VERSION[0];
  p[2] = FW_VERSION[1];
  p[3] = FW_VERSION[2];
  p[4] = gChipVersion[0];
  p[5] = gChipVersion[1];
  p[6] = (uint8_t)(CAPS & 0xFF);
  p[7] = (uint8_t)(CAPS >> 8);
  sendFrame(BR_HELLO_ACK, p, sizeof(p));
}

static void handleCfg(const BridgeFrame& frame) {
  CfgPayload cfg;
  if (!cfgDecode(frame.payload, frame.len, cfg)) {
    uint8_t ack[10];
    cfgAckEncode(3, gCfg, ack);
    sendFrame(BR_CFG_ACK, ack, sizeof(ack));
    return;
  }
  if (cfg.frequency_hz < 150000000UL || cfg.frequency_hz > 2500000000UL ||
      cfg.radio_payload < 32 || cfg.radio_payload > 255 ||
      (cfg.bitrate_kbps != 2600 && cfg.bitrate_kbps != 2080 &&
       cfg.bitrate_kbps != 1300 && cfg.bitrate_kbps != 650 &&
       cfg.bitrate_kbps != 325)) {
    uint8_t ack[10];
    cfgAckEncode(2, cfg, ack);
    sendFrame(BR_CFG_ACK, ack, sizeof(ack));
    return;
  }
  gCfg = cfg;
  bool ok = radioApply(gCfg);
  uint8_t ack[10];
  cfgAckEncode(ok ? 0 : 1, gCfg, ack);
  sendFrame(BR_CFG_ACK, ack, sizeof(ack));
  logf("cfg band=%u freq=%lu kbps=%u pwr=%d payload=%u relay=%d subghz=%d ok=%d",
       gCfg.band, (unsigned long)gCfg.frequency_hz, gCfg.bitrate_kbps,
       gCfg.tx_power_dbm, gCfg.radio_payload, gCfg.relay ? 1 : 0,
       gCfg.sub_ghz ? 1 : 0, ok ? 1 : 0);
}

static void handleFrame(const BridgeFrame& frame) {
  switch (frame.kind) {
    case BR_HELLO:
      handleHello();
      break;
    case BR_CFG:
      handleCfg(frame);
      break;
    case BR_TX:
      txPacket(frame.payload, frame.len);
      break;
    case BR_PING:
      sendFrame(BR_PONG, nullptr, 0);
      sendStat();
      break;
    default:
      break;
  }
}

static void pollBridge() {
  uint8_t buf[128];
  while (Serial.available()) {
    int avail = Serial.available();
    size_t want = (size_t)avail;
    if (want > sizeof(buf)) want = sizeof(buf);
    size_t n = Serial.readBytes(buf, want);
    if (n == 0) break;
    if (!gDecoder.push(buf, n)) {
      sendEvent("host frame overflow");
      continue;
    }
    BridgeFrame frame;
    while (gDecoder.next(frame)) handleFrame(frame);
  }
}

static void watchdog() {
  uint32_t now = millis();
  if (gRadioOk && (now - gLastRadioOkMs) > 15000 &&
      (now - gLastRadioInitMs) > 60000) {
    gStatsResets++;
    sendEvent("watchdog reinit");
    radioApply(gCfg);
  }
  if ((now - gLastStatMs) > 5000) {
    gLastStatMs = now;
    sendStat();
  }
}

void setup() {
  Serial.begin(2000000);
#if E80_BRIDGE_UART_LOG
  Serial1.setTX(12);
  Serial1.setRX(13);
  Serial1.begin(115200);
#endif
  delay(1500);

  pinMode(PIN_CS, OUTPUT);
  pinMode(PIN_RST, OUTPUT);
  pinMode(PIN_BUSY, INPUT);
  pinMode(PIN_IRQ, INPUT);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_CS, HIGH);
  digitalWrite(PIN_LED, LOW);
  spiRf.begin();

  gCfg.band = 2;
  gCfg.frequency_hz = 915000000;
  gCfg.bitrate_kbps = 1300;
  gCfg.tx_power_dbm = 22;
  gCfg.radio_payload = 255;
  gCfg.relay = false;
  gCfg.sub_ghz = true;
  static const uint8_t default_sync[4] = {0x12, 0xAD, 0x10, 0x1B};
  memcpy(gCfg.sync_word, default_sync, 4);

  logf("E80 LR2021 bridge fw=%u.%u.%u pins SCK=%d MOSI=%d MISO=%d CS=%d BUSY=%d IRQ=%d RST=%d",
       FW_VERSION[0], FW_VERSION[1], FW_VERSION[2], PIN_SCK, PIN_MOSI, PIN_MISO,
       PIN_CS, PIN_BUSY, PIN_IRQ, PIN_RST);
  if (!radioApply(gCfg)) {
    logf("radio not ready; waiting for CFG");
  } else {
    logf("radio ok chip=%02X%02X%02X%02X", gChipVersion[0], gChipVersion[1],
         gChipVersion[2], gChipVersion[3]);
  }
  gLastRadioOkMs = millis();
  gLastRadioInitMs = millis();
  gLastStatMs = millis();
}

void loop() {
  pollBridge();
  handleRx();
  watchdog();
  digitalWrite(PIN_LED, (millis() / 500) & 1);
}
