#pragma once

#include <stddef.h>
#include <stdint.h>

#include "bridge_protocol.h"

namespace seeed_bridge {

// Only variable packet length is implemented. There is no radio path yet.
static const uint16_t kCapabilities = 0x0008;
static const uint16_t kMaxLoopbackPayload = 255;
static const uint8_t kFirmwareMajor = 0;
static const uint8_t kFirmwareMinor = 1;
static const uint8_t kFirmwarePatch = 0;

// Pure host-testable bridge protocol loopback. It deliberately rejects radio
// configuration: this increment must never look like a working LR2021 bridge.
class LoopbackCore {
public:
    static const size_t kCounterCount = 6;

    LoopbackCore();

    // Consume arbitrary host bytes and append complete response frames.
    // Returns the number of appended bytes, or zero when no response is ready
    // or the output buffer is too small.
    size_t process(const uint8_t* data, size_t len, uint8_t* out, size_t cap);

    // Encode the current counters as a STAT frame.
    size_t encodeStat(uint8_t* out, size_t cap);

    const uint32_t* counters() const { return counters_; }

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

    BridgeDecoder decoder_;
    uint32_t counters_[kCounterCount];
};

}  // namespace seeed_bridge
