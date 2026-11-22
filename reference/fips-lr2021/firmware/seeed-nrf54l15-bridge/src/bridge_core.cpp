#include "bridge_core.h"

#include <string.h>

namespace seeed_bridge {

BridgeCore::BridgeCore()
    : radio_(NULL), decoder_(), counters_{0}, last_cfg_status_(1) {}

BridgeCore::BridgeCore(const RadioBackend* radio)
    : radio_(radio), decoder_(), counters_{0}, last_cfg_status_(1) {}

bool BridgeCore::append(uint8_t kind, const uint8_t* payload, uint16_t len,
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

size_t BridgeCore::encodeStat(uint8_t* out, size_t cap) {
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

size_t BridgeCore::encodeEvent(const char* text, uint8_t* out, size_t cap) {
    if (text == NULL) {
        return 0;
    }
    size_t len = strlen(text);
    if (len > 200) {
        len = 200;
    }
    size_t written =
        bridgeEncode(BR_EVT, reinterpret_cast<const uint8_t*>(text),
                     static_cast<uint16_t>(len), out, cap);
    if (written == 0) {
        counters_[Drops]++;
    }
    return written;
}

size_t BridgeCore::encodeRx(int16_t rssi_dbm, int8_t snr_db,                            const uint8_t* data, uint16_t len, uint8_t* out,
                            size_t cap) {
    if (len > kMaxRadioPayload || (len > 0 && data == NULL)) {
        counters_[Drops]++;
        return 0;
    }
    uint8_t rx[6 + kMaxRadioPayload];
    rx[0] = static_cast<uint8_t>(rssi_dbm & 0xFF);
    rx[1] = static_cast<uint8_t>((rssi_dbm >> 8) & 0xFF);
    rx[2] = static_cast<uint8_t>(snr_db);
    rx[3] = 1;  // The radio CRC passed before we got an RX_PACKET callback.
    rx[4] = static_cast<uint8_t>(len & 0xFF);
    rx[5] = static_cast<uint8_t>(len >> 8);
    if (len > 0) {
        memcpy(rx + 6, data, len);
    }
    size_t written = bridgeEncode(BR_RX, rx, static_cast<uint16_t>(6 + len), out,
                                  cap);
    if (written == 0) {
        counters_[Drops]++;
        return 0;
    }
    counters_[RxPackets]++;
    return written;
}

void BridgeCore::noteTxDone() { counters_[TxPackets]++; }

void BridgeCore::noteCrcError() { counters_[CrcErrors]++; }

void BridgeCore::noteTxTimeout() { counters_[TxTimeouts]++; }

void BridgeCore::noteDrop() { counters_[Drops]++; }

void BridgeCore::noteBootCount(uint32_t resets) { counters_[Resets] = resets; }

void BridgeCore::handleHello(uint8_t* out, size_t cap, size_t* used) {
    uint16_t chip_id = 0;
    uint16_t capabilities = kCapabilitiesLoopback;
    if (radio_ != NULL) {
        if (radio_->chip_id != NULL) {
            chip_id = radio_->chip_id(radio_->context);
        }
        if (radio_->capabilities != NULL) {
            capabilities = radio_->capabilities(radio_->context);
        }
    }
    const uint8_t ack[8] = {
        1,
        kFirmwareMajor,
        kFirmwareMinor,
        kFirmwarePatch,
        static_cast<uint8_t>(chip_id & 0xFF),
        static_cast<uint8_t>(chip_id >> 8),
        static_cast<uint8_t>(capabilities & 0xFF),
        static_cast<uint8_t>(capabilities >> 8),
    };
    (void)append(BR_HELLO_ACK, ack, sizeof(ack), out, cap, used);
}

void BridgeCore::handleCfg(const BridgeFrame& frame, uint8_t* out, size_t cap,
                           size_t* used) {
    CfgPayload cfg;
    uint8_t status = 3;  // malformed
    if (cfgDecode(frame.payload, frame.len, cfg)) {
        if (radio_ != NULL && radio_->configure != NULL) {
            status = 2;
            if (!radio_->configure(radio_->context, cfg, &status)) {
                if (status == 0) {
                    status = 2;
                }
            } else {
                status = 0;
            }
        } else {
            status = 1;  // radio backend unavailable
        }
    }

    last_cfg_status_ = status;
    uint8_t ack[10];
    cfgAckEncode(status, cfg, ack);
    if (status != 0) {
        counters_[Drops]++;
    }
    (void)append(BR_CFG_ACK, ack, sizeof(ack), out, cap, used);
}

void BridgeCore::handleTx(const BridgeFrame& frame, uint8_t* out, size_t cap,
                          size_t* used) {
    if (frame.len == 0 || frame.len > kMaxRadioPayload) {
        counters_[Drops]++;
        return;
    }

    if (radio_ != NULL) {
        if (radio_->send == NULL ||
            !radio_->send(radio_->context, frame.payload, frame.len)) {
            counters_[Drops]++;
        }
        // TX completion arrives asynchronously through noteTxDone(); RX comes
        // back through encodeRx(). Never echo here: that would be loopback.
        return;
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
}

void BridgeCore::handleDiag(uint8_t* out, size_t cap, size_t* used) {
    char text[512];
    size_t len = 0;
    if (radio_ != NULL && radio_->diagnostics != NULL) {
        len = radio_->diagnostics(radio_->context, text, sizeof(text));
    }
    if (len == 0) {
        const char* fallback = "radio=none\n";
        len = strlen(fallback);
        if (len > sizeof(text)) {
            len = sizeof(text);
        }
        memcpy(text, fallback, len);
    }
    (void)append(BR_DIAG_ACK, reinterpret_cast<const uint8_t*>(text),
                 static_cast<uint16_t>(len), out, cap, used);
}

void BridgeCore::handle(const BridgeFrame& frame, uint8_t* out, size_t cap,
                        size_t* used) {
    switch (frame.kind) {
    case BR_HELLO:
        handleHello(out, cap, used);
        break;
    case BR_CFG:
        handleCfg(frame, out, cap, used);
        break;
    case BR_TX:
        handleTx(frame, out, cap, used);
        break;
    case BR_DIAG:
        handleDiag(out, cap, used);
        break;
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

size_t BridgeCore::process(const uint8_t* data, size_t len, uint8_t* out,
                           size_t cap) {
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
