#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>

#include "bridge_core.h"

namespace {

struct DecodedFrame {
    uint8_t kind;
    std::vector<uint8_t> payload;
};

std::vector<uint8_t> encode(uint8_t kind, const uint8_t* payload, uint16_t len) {
    std::vector<uint8_t> out(7 + len);
    const size_t n = bridgeEncode(kind, payload, len, out.data(), out.size());
    assert(n == out.size());
    return out;
}

std::vector<DecodedFrame> decode(const uint8_t* data, size_t len) {
    BridgeDecoder decoder;
    assert(decoder.push(data, len));
    std::vector<DecodedFrame> frames;
    BridgeFrame frame;
    while (decoder.next(frame)) {
        DecodedFrame decoded;
        decoded.kind = frame.kind;
        decoded.payload.assign(frame.payload, frame.payload + frame.len);
        frames.push_back(decoded);
    }
    return frames;
}

std::vector<uint8_t> makeCfg() {
    std::vector<uint8_t> cfg(15, 0);
    cfg[0] = 4;  // eu2400
    cfg[1] = 0x00;
    cfg[2] = 0x72;
    cfg[3] = 0x6F;
    cfg[4] = 0x91;  // 2440000000 Hz, little-endian
    cfg[5] = 0x28;
    cfg[6] = 0x0A;  // 2600 kbps
    cfg[7] = 12;    // 12 dBm
    cfg[8] = 0x2D;
    cfg[9] = 0xD4;
    cfg[10] = 0xD4;
    cfg[11] = 0xB2;
    cfg[12] = 0xFF;
    cfg[13] = 0x00;  // 255-byte payload
    cfg[14] = 0x02;  // sub-GHz path flag (still rejected without radio)
    return cfg;
}

void testHello() {
    seeed_bridge::LoopbackCore core;
    const uint8_t version = 1;
    const auto request = encode(BR_HELLO, &version, 1);
    uint8_t out[256];
    const size_t n = core.process(request.data(), request.size(), out, sizeof(out));
    assert(n > 0);
    const auto frames = decode(out, n);
    assert(frames.size() == 1);
    assert(frames[0].kind == BR_HELLO_ACK);
    assert(frames[0].payload.size() == 8);
    assert(frames[0].payload[0] == 1);
    assert(frames[0].payload[1] == 0 && frames[0].payload[2] == 2 &&
           frames[0].payload[3] == 0);
    assert(frames[0].payload[4] == 0 && frames[0].payload[5] == 0);
    assert(frames[0].payload[6] == 0x08 && frames[0].payload[7] == 0x00);
    for (size_t i = 0; i < seeed_bridge::LoopbackCore::kCounterCount; i++) {
        assert(core.counters()[i] == 0);
    }
}

struct FakeRadio {
    int configured;
    int sent;
    bool configure_ok;
    bool send_ok;
    uint16_t chip_id;
    uint16_t capabilities;
    uint8_t last_payload[256];
    uint16_t last_len;
};

bool fakeConfigure(void* context, const CfgPayload& cfg,
                   uint8_t* status) {
    FakeRadio* radio = static_cast<FakeRadio*>(context);
    radio->configured++;
    radio->last_len = cfg.radio_payload;
    *status = radio->configure_ok ? 0 : 7;
    return radio->configure_ok;
}

bool fakeSend(void* context, const uint8_t* data, uint16_t len) {
    FakeRadio* radio = static_cast<FakeRadio*>(context);
    radio->sent++;
    radio->last_len = len;
    std::memcpy(radio->last_payload, data, len);
    return radio->send_ok;
}

uint16_t fakeChipId(void* context) {
    return static_cast<FakeRadio*>(context)->chip_id;
}

uint16_t fakeCapabilities(void* context) {
    return static_cast<FakeRadio*>(context)->capabilities;
}

void testRadioBackend() {
    FakeRadio fake = {};
    fake.configure_ok = true;
    fake.send_ok = true;
    fake.chip_id = 0x0118;
    fake.capabilities = seeed_bridge::kCapabilitiesFlrc;
    seeed_bridge::RadioBackend backend = {
        &fake, fakeConfigure, fakeSend, fakeChipId, fakeCapabilities,
        NULL, NULL, NULL, NULL};
    seeed_bridge::BridgeCore core(&backend);

    const uint8_t version = 1;
    const auto hello = encode(BR_HELLO, &version, 1);
    uint8_t out[512];
    size_t n = core.process(hello.data(), hello.size(), out, sizeof(out));
    auto frames = decode(out, n);
    assert(frames.size() == 1 && frames[0].kind == BR_HELLO_ACK);
    assert(frames[0].payload[4] == 0x18 && frames[0].payload[5] == 0x01);
    assert(frames[0].payload[6] == 0x0A && frames[0].payload[7] == 0x00);

    const auto cfg = makeCfg();
    const auto cfg_frame = encode(BR_CFG, cfg.data(), cfg.size());
    n = core.process(cfg_frame.data(), cfg_frame.size(), out, sizeof(out));
    frames = decode(out, n);
    assert(frames.size() == 1 && frames[0].kind == BR_CFG_ACK);
    assert(frames[0].payload[0] == 0);
    assert(fake.configured == 1);
    assert(core.counters()[3] == 0);

    const uint8_t payload[] = {'r', 'a', 'd', 'i', 'o'};
    const auto tx = encode(BR_TX, payload, sizeof(payload));
    n = core.process(tx.data(), tx.size(), out, sizeof(out));
    assert(n == 0);  // no synchronous echo in radio mode
    assert(fake.sent == 1 && fake.last_len == sizeof(payload));
    assert(std::memcmp(fake.last_payload, payload, sizeof(payload)) == 0);
    assert(core.counters()[0] == 0);  // TX done not confirmed yet

    core.noteTxDone();
    assert(core.counters()[0] == 1);

    const uint8_t rx_data[] = {1, 2, 3, 4};
    n = core.encodeRx(-77, 9, rx_data, sizeof(rx_data), out, sizeof(out));
    frames = decode(out, n);
    assert(frames.size() == 1 && frames[0].kind == BR_RX);
    assert(frames[0].payload.size() == 6 + sizeof(rx_data));
    assert(frames[0].payload[0] == 0xB3 && frames[0].payload[1] == 0xFF);
    assert(frames[0].payload[2] == 9 && frames[0].payload[3] == 1);
    assert(frames[0].payload[4] == sizeof(rx_data) &&
           frames[0].payload[5] == 0);
    assert(std::memcmp(frames[0].payload.data() + 6, rx_data,
                       sizeof(rx_data)) == 0);
    assert(core.counters()[1] == 1);

    core.noteCrcError();
    core.noteTxTimeout();
    core.noteDrop();
    assert(core.counters()[2] == 1 && core.counters()[4] == 1 &&
           core.counters()[3] == 1);

    fake.send_ok = false;
    n = core.process(tx.data(), tx.size(), out, sizeof(out));
    assert(n == 0 && fake.sent == 2 && core.counters()[3] == 2);

    fake.configure_ok = false;
    n = core.process(cfg_frame.data(), cfg_frame.size(), out, sizeof(out));
    frames = decode(out, n);
    assert(frames.size() == 1 && frames[0].payload[0] == 7);
    assert(core.lastCfgStatus() == 7);
    assert(core.counters()[3] == 3);
}

void testCfgRejected() {
    seeed_bridge::LoopbackCore core;
    const auto cfg = makeCfg();
    const auto request = encode(BR_CFG, cfg.data(), cfg.size());
    uint8_t out[256];
    const size_t n = core.process(request.data(), request.size(), out, sizeof(out));
    const auto frames = decode(out, n);
    assert(frames.size() == 1);
    assert(frames[0].kind == BR_CFG_ACK);
    assert(frames[0].payload.size() == 10);
    assert(frames[0].payload[0] != 0);  // radio unavailable, not false success
    assert(std::memcmp(frames[0].payload.data() + 1, cfg.data() + 1, 7) == 0);
    assert(std::memcmp(frames[0].payload.data() + 8, cfg.data() + 12, 2) == 0);
    assert(core.counters()[2] == 0);  // no fake CRC/radio error
    assert(core.counters()[3] == 1);  // rejection is visible as a dropped CFG

    const uint8_t malformed[3] = {0};
    const auto bad = encode(BR_CFG, malformed, sizeof(malformed));
    const size_t bad_n = core.process(bad.data(), bad.size(), out, sizeof(out));
    const auto bad_frames = decode(out, bad_n);
    assert(bad_frames.size() == 1 && bad_frames[0].payload[0] == 3);
}

void testTxLoopback() {
    seeed_bridge::LoopbackCore core;
    const uint8_t payload[] = {'h', 'e', 'l', 'l', 'o'};
    const auto request = encode(BR_TX, payload, sizeof(payload));
    uint8_t out[256];
    const size_t n = core.process(request.data(), request.size(), out, sizeof(out));
    const auto frames = decode(out, n);
    assert(frames.size() == 1);
    assert(frames[0].kind == BR_RX);
    assert(frames[0].payload.size() == 6 + sizeof(payload));
    assert(frames[0].payload[0] == 0 && frames[0].payload[1] == 0);
    assert(frames[0].payload[2] == 0 && frames[0].payload[3] == 1);
    assert(frames[0].payload[4] == sizeof(payload) && frames[0].payload[5] == 0);
    assert(std::memcmp(frames[0].payload.data() + 6, payload, sizeof(payload)) == 0);
    assert(core.counters()[0] == 1 && core.counters()[1] == 1);
    assert(core.counters()[3] == 0);

    const uint8_t empty = 0;
    const auto empty_frame = encode(BR_TX, &empty, 0);
    assert(core.process(empty_frame.data(), empty_frame.size(), out, sizeof(out)) == 0);
    assert(core.counters()[3] == 1);
    assert(core.counters()[0] == 1 && core.counters()[1] == 1);

    std::vector<uint8_t> too_big(256, 0x42);
    const auto oversize = encode(BR_TX, too_big.data(), too_big.size());
    assert(core.process(oversize.data(), oversize.size(), out, sizeof(out)) == 0);
    assert(core.counters()[3] == 2);
    assert(core.counters()[0] == 1 && core.counters()[1] == 1);
}

void testPingAndStat() {
    seeed_bridge::LoopbackCore core;
    const auto request = encode(BR_PING, NULL, 0);
    uint8_t out[256];
    const size_t n = core.process(request.data(), request.size(), out, sizeof(out));
    const auto frames = decode(out, n);
    assert(frames.size() == 2);
    assert(frames[0].kind == BR_PONG && frames[0].payload.empty());
    assert(frames[1].kind == BR_STAT && frames[1].payload.size() == 24);

    uint8_t stat[64];
    const size_t stat_len = core.encodeStat(stat, sizeof(stat));
    const auto standalone = decode(stat, stat_len);
    assert(standalone.size() == 1 && standalone[0].kind == BR_STAT);
    assert(standalone[0].payload == frames[1].payload);
}

void testChunkingAndCoalescing() {
    seeed_bridge::LoopbackCore core;
    const uint8_t version = 1;
    const auto request = encode(BR_HELLO, &version, 1);
    uint8_t out[512];
    assert(core.process(request.data(), 3, out, sizeof(out)) == 0);
    const size_t n = core.process(request.data() + 3, request.size() - 3, out, sizeof(out));
    assert(decode(out, n).size() == 1);

    auto twice = request;
    twice.insert(twice.end(), request.begin(), request.end());
    const size_t twice_n = core.process(twice.data(), twice.size(), out, sizeof(out));
    assert(decode(out, twice_n).size() == 2);

    const auto ping = encode(BR_PING, NULL, 0);
    auto pings = ping;
    pings.insert(pings.end(), ping.begin(), ping.end());
    const size_t pings_n = core.process(pings.data(), pings.size(), out, sizeof(out));
    assert(decode(out, pings_n).size() == 4);
}

void testCrcRecoveryAndUnknown() {
    seeed_bridge::LoopbackCore core;
    uint8_t out[256];
    const uint8_t version = 1;
    auto request = encode(BR_HELLO, &version, 1);
    request.back() ^= 0xFF;
    assert(core.process(request.data(), request.size(), out, sizeof(out)) == 0);
    const auto valid = encode(BR_HELLO, &version, 1);
    const size_t n = core.process(valid.data(), valid.size(), out, sizeof(out));
    assert(decode(out, n).size() == 1);

    const auto unknown = encode(0xFE, NULL, 0);
    assert(core.process(unknown.data(), unknown.size(), out, sizeof(out)) == 0);
    assert(core.counters()[3] == 1);
}

void testPingOutputBounds() {
    seeed_bridge::LoopbackCore core;
    const auto ping = encode(BR_PING, NULL, 0);
    uint8_t out[31];  // Room for PONG but not PONG plus STAT.
    assert(core.process(ping.data(), ping.size(), out, sizeof(out)) == 0);
    assert(core.counters()[3] == 1);
}

void testOutputBounds() {
    seeed_bridge::LoopbackCore core;
    const uint8_t version = 1;
    const auto request = encode(BR_HELLO, &version, 1);
    uint8_t out[5];
    assert(core.process(request.data(), request.size(), out, sizeof(out)) == 0);
    assert(core.counters()[3] == 1);
    assert(core.process(NULL, 1, out, sizeof(out)) == 0);
    assert(core.counters()[3] == 2);
    assert(core.process(request.data(), request.size(), out, 0) == 0);
    assert(core.counters()[3] == 3);
}

}  // namespace

int main() {
    testHello();
    testCfgRejected();
    testTxLoopback();
    testPingAndStat();
    testChunkingAndCoalescing();
    testCrcRecoveryAndUnknown();
    testPingOutputBounds();
    testOutputBounds();
    testRadioBackend();
    std::printf("Seeed bridge loopback host tests passed\n");
    return 0;
}
