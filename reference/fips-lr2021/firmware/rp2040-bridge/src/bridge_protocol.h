// Host <-> bridge protocol, shared shape with the Rust crate.
#pragma once

#include <stdint.h>
#include <stddef.h>
#include <string.h>

static const uint8_t BRIDGE_MAGIC0 = 0xA5;
static const uint8_t BRIDGE_MAGIC1 = 0x5A;
static const uint16_t BRIDGE_MAX_PAYLOAD = 2048;
static const size_t BRIDGE_BUF_SIZE = 4096;

enum BridgeKind : uint8_t {
  BR_HELLO = 1,
  BR_HELLO_ACK = 2,
  BR_CFG = 3,
  BR_CFG_ACK = 4,
  BR_TX = 5,
  BR_RX = 6,
  BR_STAT = 7,
  BR_EVT = 8,
  BR_PING = 9,
  BR_PONG = 10,
  BR_CFG_EXT = 11, // optional slot-role/clock extension; old bridges ignore it
};

struct BridgeFrame {
  uint8_t kind = 0;
  uint16_t len = 0;
  uint8_t payload[BRIDGE_MAX_PAYLOAD] = {0};
};

static inline uint16_t bridgeCrc16(const uint8_t* data, size_t len) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < len; i++) {
    crc ^= (uint16_t)data[i] << 8;
    for (int b = 0; b < 8; b++) {
      crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
  }
  return crc;
}

// Returns the encoded size, or 0 if it does not fit.
static inline size_t bridgeEncode(uint8_t kind, const uint8_t* payload, uint16_t len,
                                  uint8_t* out, size_t cap) {
  size_t total = 7 + len;
  if (total > cap || len > BRIDGE_MAX_PAYLOAD) return 0;
  out[0] = BRIDGE_MAGIC0;
  out[1] = BRIDGE_MAGIC1;
  out[2] = kind;
  out[3] = (uint8_t)(len & 0xFF);
  out[4] = (uint8_t)(len >> 8);
  if (len) memcpy(out + 5, payload, len);
  uint16_t crc = bridgeCrc16(out + 2, 3 + len);
  out[5 + len] = (uint8_t)(crc & 0xFF);
  out[6 + len] = (uint8_t)(crc >> 8);
  return total;
}

class BridgeDecoder {
 public:
  bool push(const uint8_t* data, size_t n) {
    if (n > sizeof(buf_) - len_) {
      len_ = 0;  // overflow: resynchronize on the next frame
      return false;
    }
    memcpy(buf_ + len_, data, n);
    len_ += n;
    return true;
  }

  bool next(BridgeFrame& out) {
    while (len_ >= 5) {
      if (buf_[0] != BRIDGE_MAGIC0 || buf_[1] != BRIDGE_MAGIC1) {
        size_t i = 1;
        while (i + 1 < len_ && !(buf_[i] == BRIDGE_MAGIC0 && buf_[i + 1] == BRIDGE_MAGIC1)) i++;
        drop(i);
        continue;
      }
      uint16_t plen = (uint16_t)buf_[3] | ((uint16_t)buf_[4] << 8);
      if (plen > BRIDGE_MAX_PAYLOAD) {
        drop(1);
        continue;
      }
      size_t total = 7 + plen;
      if (len_ < total) return false;
      uint16_t expected = (uint16_t)buf_[total - 2] | ((uint16_t)buf_[total - 1] << 8);
      uint16_t actual = bridgeCrc16(buf_ + 2, 3 + plen);
      if (expected != actual) {
        drop(1);
        continue;
      }
      out.kind = buf_[2];
      out.len = plen;
      if (plen) memcpy(out.payload, buf_ + 5, plen);
      drop(total);
      return true;
    }
    return false;
  }

 private:
  void drop(size_t n) {
    if (n >= len_) {
      len_ = 0;
      return;
    }
    memmove(buf_, buf_ + n, len_ - n);
    len_ -= n;
  }

  uint8_t buf_[BRIDGE_BUF_SIZE] = {0};
  size_t len_ = 0;
};

struct CfgPayload {
  uint8_t band = 2;  // us915
  uint32_t frequency_hz = 915000000;
  uint16_t bitrate_kbps = 1300;
  int8_t tx_power_dbm = 22;
  uint8_t sync_word[4] = {0x12, 0xAD, 0x10, 0x1B};
  uint16_t radio_payload = 255;
  bool relay = false;
  bool sub_ghz = true;
};

// Optional frame sent before BR_CFG by newer hosts. The node ID selects the
// TX slot (id & 1); epoch_ms is the host's Unix time and establishes a shared
// slot phase across machines. Old bridges ignore the unknown frame kind.
struct CfgExtPayload {
  uint32_t local_id = 0;
  uint64_t epoch_ms = 0;
};

static inline bool cfgExtDecode(const uint8_t* p, uint16_t len, CfgExtPayload& out) {
  if (len != 12) return false;
  out.local_id = (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
                 ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
  out.epoch_ms = 0;
  for (int i = 0; i < 8; i++) {
    out.epoch_ms |= ((uint64_t)p[4 + i]) << (8 * i);
  }
  return true;
}

static inline bool cfgDecode(const uint8_t* p, uint16_t len, CfgPayload& out) {
  if (len != 15) return false;
  out.band = p[0];
  out.frequency_hz = (uint32_t)p[1] | ((uint32_t)p[2] << 8) |
                     ((uint32_t)p[3] << 16) | ((uint32_t)p[4] << 24);
  out.bitrate_kbps = (uint16_t)p[5] | ((uint16_t)p[6] << 8);
  out.tx_power_dbm = (int8_t)p[7];
  memcpy(out.sync_word, p + 8, 4);
  out.radio_payload = (uint16_t)p[12] | ((uint16_t)p[13] << 8);
  out.relay = (p[14] & 0x01) != 0;
  out.sub_ghz = (p[14] & 0x02) != 0;
  return true;
}

static inline void cfgAckEncode(uint8_t status, const CfgPayload& cfg, uint8_t out[10]) {
  out[0] = status;
  out[1] = (uint8_t)(cfg.frequency_hz & 0xFF);
  out[2] = (uint8_t)((cfg.frequency_hz >> 8) & 0xFF);
  out[3] = (uint8_t)((cfg.frequency_hz >> 16) & 0xFF);
  out[4] = (uint8_t)((cfg.frequency_hz >> 24) & 0xFF);
  out[5] = (uint8_t)(cfg.bitrate_kbps & 0xFF);
  out[6] = (uint8_t)(cfg.bitrate_kbps >> 8);
  out[7] = (uint8_t)cfg.tx_power_dbm;
  out[8] = (uint8_t)(cfg.radio_payload & 0xFF);
  out[9] = (uint8_t)(cfg.radio_payload >> 8);
}
