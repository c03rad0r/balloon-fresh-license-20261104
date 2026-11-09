#include "bridge_core.h"

#include <string.h>

namespace seeed_bridge {

LoopbackCore::LoopbackCore() : decoder_(), counters_{0} {}

bool LoopbackCore::append(uint8_t kind, const uint8_t* payload, uint16_t len,
                          uint8_t* out, size_t cap, size_t* used) {
    if (*used > cap) {
        return false;
    }
    size_t written = bridgeEncode(kind, payload, len, out + *used, cap - *used);
    if (written == 0) {
        counters_[Drops]++;
        return false;
    }
    *used += written;
    return true;
}

size_t LoopbackCore::encodeStat(uint8_t* out, size_t cap) {
    uint8_t payload[24];
    for (size_t i = 0; i < kCounterCount; i++) {
        payload[i * 4 + 0] = static_cast<uint8_t>(counters_[i] & 0xFF);
        payload[i * 4 + 1] = static_cast<uint8_t>((counters_[i] >> 8) & 0xFF);
        payload[i * 4 + 2] = static_cast<uint8_t>((counters_[i] >> 16) & 0xFF);
        payload[i * 4 + 3] = static_cast<uint8_t>((counters_[i] >> 24) & 0xFF);
    }
    size_t written = bridgeEncode(BR_STAT, payload, sizeof(payload), out, cap);
    if (written == 0) {
        counters_[Drops]++;
    }
    return written;
}

void LoopbackCore::handle(const BridgeFrame& frame, uint8_t* out, size_t cap,
                          size_t* used) {
    switch (frame.kind) {
    case BR_HELLO: {
        const uint8_t ack[8] = {
            1,
            kFirmwareMajor,
            kFirmwareMinor,
            kFirmwarePatch,
            0,
            0,
            static_cast<uint8_t>(kCapabilities & 0xFF),
            static_cast<uint8_t>(kCapabilities >> 8),
        };
        (void)append(BR_HELLO_ACK, ack, sizeof(ack), out, cap, used);
        break;
    }
    case BR_CFG: {
        CfgPayload cfg;
        uint8_t status = cfgDecode(frame.payload, frame.len, cfg) ? 1 : 3;
        uint8_t ack[10];
        cfgAckEncode(status, cfg, ack);
        counters_[Drops]++;
        (void)append(BR_CFG_ACK, ack, sizeof(ack), out, cap, used);
        break;
    }
    case BR_TX: {
        if (frame.len == 0 || frame.len > kMaxLoopbackPayload) {
            counters_[Drops]++;
            break;
        }
        uint8_t rx[6 + kMaxLoopbackPayload];
        rx[0] = 0;  // RSSI dBm, int16 LE: loopback has no RF measurement.
        rx[1] = 0;
        rx[2] = 0;  // SNR dB.
        rx[3] = 1;  // CRC OK for an in-process loopback.
        rx[4] = static_cast<uint8_t>(frame.len & 0xFF);
        rx[5] = static_cast<uint8_t>(frame.len >> 8);
        memcpy(rx + 6, frame.payload, frame.len);
        if (append(BR_RX, rx, static_cast<uint16_t>(6 + frame.len), out, cap, used)) {
            counters_[TxPackets]++;
            counters_[RxPackets]++;
        }
        break;
    }
    case BR_PING: {
        const size_t before = *used;
        if (!append(BR_PONG, NULL, 0, out, cap, used)) {
            break;
        }
        uint8_t stat[64];
        size_t n = encodeStat(stat, sizeof(stat));
        if (n == 0 || *used + n > cap) {
            *used = before;
            counters_[Drops]++;
        } else {
            memcpy(out + *used, stat, n);
            *used += n;
        }
        break;
    }
    default:
        counters_[Drops]++;
        break;
    }
}

size_t LoopbackCore::process(const uint8_t* data, size_t len, uint8_t* out, size_t cap) {
    size_t used = 0;
    if (len == 0) {
        return 0;
    }
    if (data == NULL || out == NULL || cap == 0) {
        counters_[Drops]++;
        return 0;
    }
    if (!decoder_.push(data, len)) {
        counters_[Drops]++;
        return 0;
    }

    BridgeFrame frame;
    while (decoder_.next(frame)) {
        handle(frame, out, cap, &used);
    }
    return used;
}

}  // namespace seeed_bridge
