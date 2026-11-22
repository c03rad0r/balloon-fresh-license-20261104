#pragma once

#include <stddef.h>
#include <stdint.h>

#include "bridge_protocol.h"

namespace seeed_bridge {

// Capability bits from docs/BRIDGE-PROTOCOL.md.
static const uint16_t kCapabilitySubGhz = 0x0001;
static const uint16_t kCapability2G4 = 0x0002;
static const uint16_t kCapabilityRelay = 0x0004;
static const uint16_t kCapabilityVariableLength = 0x0008;

// Loopback advertises only what it can do without a radio.
static const uint16_t kCapabilitiesLoopback = kCapabilityVariableLength;
// The FLRC backend implements both front-end paths but this build is only
// verified on 2.4 GHz; the sub-GHz bit is added after that gate passes.
static const uint16_t kCapabilitiesFlrc = kCapability2G4 | kCapabilityVariableLength;

static const uint16_t kMaxLoopbackPayload = 255;
static const uint16_t kMaxRadioPayload = 255;
static const uint8_t kFirmwareMajor = 0;
static const uint8_t kFirmwareMinor = 2;
static const uint8_t kFirmwarePatch = 0;

// Firmware-side radio adapter. The core stays free of Zephyr/USP headers so it
// can be compiled and unit-tested on the host.
struct RadioBackend {
    void* context;
    // Apply one CFG payload. Return true only when the requested profile was
    // actually programmed; status receives the CFG_ACK status byte.
    bool (*configure)(void* context, const CfgPayload& cfg, uint8_t* status);
    // Queue one raw radio packet. Return false when the radio is unavailable
    // or its bounded queue is full.
    bool (*send)(void* context, const uint8_t* data, uint16_t len);
    // LR2021 version as (major << 8) | minor, or zero when not yet read.
    uint16_t (*chip_id)(void* context);
    // Capability bits implemented by this build.
    uint16_t (*capabilities)(void* context);
    // Optional radio event notifications. The core turns each into one STAT
    // counter when the firmware wires these callbacks.
    void (*on_tx_done)(void* context);
    void (*on_crc_error)(void* context);
    void (*on_tx_timeout)(void* context);
    void (*on_drop)(void* context);
};

// Host-protocol bridge core. With no RadioBackend it reproduces the previous
// loopback behavior; with one it programs the radio and reports RX packets
// supplied by the firmware.
class BridgeCore {
public:
    static const size_t kCounterCount = 6;

    BridgeCore();
    explicit BridgeCore(const RadioBackend* radio);

    void setRadio(const RadioBackend* radio) { radio_ = radio; }
    const RadioBackend* radio() const { return radio_; }

    // Consume arbitrary host bytes and append complete response frames.
    // Returns the number of appended bytes, or zero when no response is ready
    // or the output buffer is too small.
    size_t process(const uint8_t* data, size_t len, uint8_t* out, size_t cap);

    // Encode the current counters as a STAT frame.
    size_t encodeStat(uint8_t* out, size_t cap);

    // Encode a UTF-8 diagnostic event. Not used on the throughput path.
    size_t encodeEvent(const char* text, uint8_t* out, size_t cap);

    // Encode one valid received radio packet as a BR_RX frame and count it.
    size_t encodeRx(int16_t rssi_dbm, int8_t snr_db, const uint8_t* data,
                    uint16_t len, uint8_t* out, size_t cap);

    // Radio event notifications. Each maps directly to one STAT counter.
    void noteTxDone();
    void noteCrcError();
    void noteTxTimeout();
    void noteDrop();

    const uint32_t* counters() const { return counters_; }
    uint8_t lastCfgStatus() const { return last_cfg_status_; }

private:
    enum Counter {
        TxPackets = 0,
        RxPackets = 1,
        CrcErrors = 2,
        Drops = 3,
        TxTimeouts = 4,
        Resets = 5,
    };

    bool append(uint8_t kind, const uint8_t* payload, uint16_t len,
                uint8_t* out, size_t cap, size_t* used);
    void handle(const BridgeFrame& frame, uint8_t* out, size_t cap, size_t* used);
    void handleHello(uint8_t* out, size_t cap, size_t* used);
    void handleCfg(const BridgeFrame& frame, uint8_t* out, size_t cap,
                   size_t* used);
    void handleTx(const BridgeFrame& frame, uint8_t* out, size_t cap,
                  size_t* used);

    const RadioBackend* radio_;
    BridgeDecoder decoder_;
    uint32_t counters_[kCounterCount];
    uint8_t last_cfg_status_;
};

// Preserve the original type name used by the existing host tests.
using LoopbackCore = BridgeCore;

}  // namespace seeed_bridge
