/*
 * ESP32 bridge for FIPS over LR2021/FLRC.
 *
 * Radio side reuses the PROVEN driver from
 * tracker/firmware/components/lr2021_transport (EspIdfLr2021Radio). That driver
 * already encodes every carrier quirk we hit while reimplementing it:
 *   - SET_STANDBY_XOSC (TCXO module, RC standby leaves it unclocked)
 *   - hardware CS; full-duplex transfers with dummy TX on reads
 *   - FLRC packet type 0x05
 *   - E80 build: DIO8 IRQ, 32-bit frequency in Hz, LF PA, Semtech bitrates
 *   - 2.4 GHz carrier build: poll DIO9 as its IRQ status reads back zero
 *
 * This file only implements the host protocol on top, so an ESP32-hosted LR2021
 * looks identical to the RP2040 and STM32 bridges and works with
 * fips-lr2021ctl / fips-lr2021d / the FIPS lr2021 transport unchanged.
 */
#include <stdio.h>
#include <string.h>

#include "driver/usb_serial_jtag.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "lr2021_spi.h"
#include "bridge_protocol.h"

#ifndef LR2021_E80_COMPAT
#define LR2021_E80_COMPAT 0
#endif
#ifndef LR2021_NICERF_C3
#define LR2021_NICERF_C3 0
#endif
#ifndef LR2021_ENABLE_TDMA
#define LR2021_ENABLE_TDMA 0
#endif

#if LR2021_NICERF_C3
static const uint8_t FW_VERSION[3] = {0, 5, 13};
#else
static const uint8_t FW_VERSION[3] = {0, 4, 23};
#endif
static const uint16_t CAPS = 0x0007;
static constexpr size_t RADIO_MAX_PAYLOAD = 511;
static_assert(6 + RADIO_MAX_PAYLOAD <= BRIDGE_MAX_PAYLOAD,
              "RX payload must fit the host bridge frame");

#if LR2021_E80_COMPAT
static constexpr uint32_t E80_IRQ_RX_DONE = 1UL << 18;
static constexpr uint32_t E80_IRQ_TX_DONE = 1UL << 19;
static constexpr uint32_t E80_IRQ_CRC_ERROR = 1UL << 22;
static constexpr uint32_t E80_RX_IN_PROGRESS =
    (1UL << 5) | (1UL << 6); // LR20XX preamble / syncword-header valid
#endif

static uint32_t gCcaDeferrals, gCcaTimeouts, gCcaLastGuardUs;
static bool gSlotConfigured;
static uint8_t gSlotRole;
static uint64_t gHostEpochOffsetMs;
static uint32_t gSlotWaitMs;

static EspIdfLr2021Radio gRadio;
static Lr2021Config gRadioCfg;
static CfgPayload gCfg;
static uint8_t gChipVersion[4] = {0};
static BridgeDecoder gDecoder;

static uint32_t gTx, gRx, gCrc, gDrops, gTimeouts, gResets, gUsbShortWrites;
static uint32_t gLastOkMs, gLastInitMs;
static bool gRadioOk;

static uint32_t now_ms(void) { return (uint32_t)(esp_timer_get_time() / 1000); }
static uint64_t local_ms(void) { return (uint64_t)(esp_timer_get_time() / 1000); }
static uint64_t wall_ms(void) { return local_ms() + gHostEpochOffsetMs; }

static void sendFrame(uint8_t kind, const uint8_t *payload, uint16_t len)
{
    static uint8_t out[BRIDGE_MAX_PAYLOAD + 16];
    size_t n = bridgeEncode(kind, payload, len, out, sizeof(out));
    if (n) {
        size_t sent = usb_serial_jtag_write_bytes(out, n, pdMS_TO_TICKS(10));
        if (sent != n) gUsbShortWrites++;
    }
}

static void sendStat(void)
{
    uint8_t p[24];
    uint32_t v[6] = {gTx, gRx, gCrc, gDrops, gTimeouts, gResets};
    for (int i = 0; i < 6; i++) {
        p[i * 4 + 0] = (uint8_t)(v[i] & 0xFF);
        p[i * 4 + 1] = (uint8_t)((v[i] >> 8) & 0xFF);
        p[i * 4 + 2] = (uint8_t)((v[i] >> 16) & 0xFF);
        p[i * 4 + 3] = (uint8_t)((v[i] >> 24) & 0xFF);
    }
    sendFrame(BR_STAT, p, sizeof(p));
}

static bool radioApply(const CfgPayload &cfg)
{
    if (cfg.radio_payload < 6 || cfg.radio_payload > RADIO_MAX_PAYLOAD) {
        return false;
    }
    gRadioCfg.freq_mhz = (float)cfg.frequency_hz / 1000000.0f;
    gRadioCfg.bitrate_kbps = cfg.bitrate_kbps;
    gRadioCfg.tx_power_dbm = cfg.tx_power_dbm;
    gRadioCfg.crc_enabled = true;
    gRadioCfg.payload_length = cfg.radio_payload;
    memcpy(gRadioCfg.sync_word, cfg.sync_word, 4);

    Lr2021Error err = Lr2021Error::WrongState;
    for (int attempt = 1; attempt <= 5; attempt++) {
        err = gRadio.init(gRadioCfg);
        if (err == Lr2021Error::Ok) break;
        char msg[48];
        snprintf(msg, sizeof(msg), "radio init attempt=%d err=%d",
                 attempt, (int)err);
        sendFrame(BR_EVT, (const uint8_t *)msg, (uint16_t)strlen(msg));
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    gLastInitMs = now_ms();
    gRadioOk = (err == Lr2021Error::Ok);
    if (gRadioOk) {
        uint8_t ver[4] = {0, 0, 0, 0};
        Lr2021Error verr = gRadio.get_version(ver);
        memcpy(gChipVersion, ver, 4);
        {
            char msg[48];
            snprintf(msg, sizeof(msg), "ver %02X %02X %02X %02X err=%d",
                     ver[0], ver[1], ver[2], ver[3], (int)verr);
            sendFrame(BR_EVT, (const uint8_t *)msg, (uint16_t)strlen(msg));
        }
        gRadio.start_rx();
        gLastOkMs = now_ms();
    } else {
        gResets++;
        gRadioOk = false;
    }
    return gRadioOk;
}

static void handleRx(void);

/* Best-effort CSMA/CA for one half-duplex radio per endpoint. The
 * radio tells us about an incoming preamble/sync/header before a full packet
 * arrives. Defer to that reception, then jitter our own TX so overlapping
 * retries from two nodes do not occupy the same slots. If the status read
 * fails, apply the guard anyway instead of permanently blocking the link. */
static void channelGuard(void)
{
#if LR2021_E80_COMPAT
    bool exceeded = true;
    for (int iteration = 0; iteration < 20; iteration++) {
        uint32_t irq = 0;
        if (!lr2021_ok(gRadio.get_irq_status(irq))) break;
        if (!(irq & (E80_RX_IN_PROGRESS | E80_IRQ_RX_DONE | E80_IRQ_CRC_ERROR))) {
            exceeded = false;
            break;
        }

        gCcaDeferrals++;
        if (irq & (E80_IRQ_RX_DONE | E80_IRQ_CRC_ERROR)) {
            /* Deliver a completed RX before entering TX. This also clears
             * latched progress/complete bits before the next check. */
            handleRx();
        } else {
            vTaskDelay(pdMS_TO_TICKS(1));
        }
    }
    if (exceeded) gCcaTimeouts++;
#else
    vTaskDelay(pdMS_TO_TICKS(1));
#endif

    /* Fixed-slot fallback for a repeated two-node collision regime. The host
     * epoch provides a common coarse phase; the LR2021 oscillator remains the
     * only RF-timing clock. Opposite link-ID parity selects the 40 ms window. */
    gSlotWaitMs = 0;
    if (gSlotConfigured) {
        constexpr uint64_t SLOT_MS = 40;
        constexpr uint64_t CYCLE_MS = SLOT_MS * 2;
        constexpr uint64_t EDGE_MS = 5;
        uint64_t phase = wall_ms() % CYCLE_MS;
        uint64_t start = (uint64_t)gSlotRole * SLOT_MS + EDGE_MS;
        uint64_t wait = 0;
        if (phase < start) {
            wait = start - phase;
        } else if (phase >= (uint64_t)gSlotRole * SLOT_MS + SLOT_MS - EDGE_MS) {
            wait = CYCLE_MS - phase + start;
        }
        gSlotWaitMs = (uint32_t)wait;
        /* Serve RX while waiting. Sleeping through another node's slot can
         * otherwise leave RX_DONE latched and let the following TX clear it. */
        for (uint32_t elapsed = 0; elapsed < gSlotWaitMs; elapsed++) {
            handleRx();
            vTaskDelay(pdMS_TO_TICKS(1));
        }
        uint32_t irq = 0;
        if (lr2021_ok(gRadio.get_irq_status(irq)) &&
            (irq & (E80_RX_IN_PROGRESS | E80_IRQ_RX_DONE | E80_IRQ_CRC_ERROR))) {
            handleRx();
            for (int drain = 0; drain < 8; drain++) {
                if (!lr2021_ok(gRadio.get_irq_status(irq)) ||
                    !(irq & E80_RX_IN_PROGRESS)) break;
                vTaskDelay(pdMS_TO_TICKS(1));
            }
            handleRx();
        }
    }

    /* Different seeds on S3 and C3 plus xorshift state prevent identical
     * retry epochs. With fixed slots this is only a small intra-slot guard;
     * without the extension keep the wider standalone CSMA guard. */
    static uint32_t seed =
#if LR2021_NICERF_C3
        0xC3A1105Eu;
#else
        0x53B14A11u;
#endif
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    gCcaLastGuardUs = gSlotConfigured ? 500 + (seed % 1001)
                                     : 8000 + (seed % 8001);
    esp_rom_delay_us(gCcaLastGuardUs);
}

static void txPacket(const uint8_t *data, size_t len)
{
    if (!gRadioOk || len == 0 || len > gCfg.radio_payload) return;

    /* Take turns on the air before asking the radio to transmit. */
    channelGuard();

    gRadio.send_packet(data, len);
    gTx++;

    bool asserted = false;
    bool done = false;
    uint32_t start = now_ms();
    while ((now_ms() - start) < 60) {
#if LR2021_NICERF_C3
        /* NiceRF's established carrier driver polls DIO9 because the status
         * register is unreliable on this chip. */
        if (lr2021_ok(gRadio.check_irq(asserted)) && asserted) {
            done = true;
            break;
        }
#elif LR2021_E80_COMPAT
        /* Poll the status register directly. This also works if DIO8 is not
         * routed to the host, and is the method used by the RP2040 bridge. */
        uint32_t irq = 0;
        if (lr2021_ok(gRadio.get_irq_status(irq)) && (irq & E80_IRQ_TX_DONE)) {
            done = true;
            break;
        }
#else
        if (!lr2021_ok(gRadio.check_irq(asserted)) || !asserted) {
            esp_rom_delay_us(50);
            continue;
        }
        break;
#endif
        esp_rom_delay_us(50);
    }
#if !LR2021_E80_COMPAT
    done = asserted;
#endif
    if (!done) gTimeouts++;

    gRadio.clear_irq();
    gRadio.start_rx();
    gLastOkMs = now_ms();
}

/* Fixed-length FLRC packets are zero-padded. Trim to the link header's
 * declared payload length before giving the strict host parser the frame. */
static size_t frameLength(const uint8_t *data, size_t len)
{
    if (len < 20 || data[0] != 0xF1 || data[1] != 0x50 || (data[2] >> 4) != 1) {
        return len;
    }
    size_t payload_len = (size_t)data[18] | ((size_t)data[19] << 8);
    size_t total = 20 + payload_len + 4;
    return total <= len ? total : len;
}

static void handleRx(void)
{
    if (!gRadioOk) return;

#if LR2021_NICERF_C3
    /* DIO9 is the reliable receive notification on this carrier. */
    bool asserted = false;
    if (!lr2021_ok(gRadio.check_irq(asserted)) || !asserted) return;
    /* Preamble/sync-enabled IRQs are a busy indication, not RX_DONE. Leave
     * those events latched so channelGuard defers until the packet completes. */
    uint32_t irq = 0;
    if (lr2021_ok(gRadio.get_irq_status(irq)) &&
        (irq & E80_RX_IN_PROGRESS) &&
        !(irq & (E80_IRQ_RX_DONE | E80_IRQ_CRC_ERROR))) return;
#elif LR2021_E80_COMPAT
    uint32_t irq = 0;
    if (!lr2021_ok(gRadio.get_irq_status(irq))) return;
    if (!(irq & (E80_IRQ_RX_DONE | E80_IRQ_CRC_ERROR))) return;
#else
    bool asserted = false;
    if (!lr2021_ok(gRadio.check_irq(asserted)) || !asserted) return;
#endif

#if LR2021_NICERF_C3
    bool phy_crc_error = false;
#elif LR2021_E80_COMPAT
    bool phy_crc_error = (irq & E80_IRQ_CRC_ERROR) != 0;
    if (phy_crc_error) gCrc++;
    if (!(irq & E80_IRQ_RX_DONE) && !phy_crc_error) {
        gRadio.clear_irq();
        gRadio.start_rx();
        return;
    }
#else
    bool phy_crc_error = false;
#endif

    static uint8_t buf[RADIO_MAX_PAYLOAD];
    PacketStatus st;
    Lr2021Error err = gRadio.read_packet(buf, sizeof(buf), st);
    gRadio.clear_irq();
    gRadio.start_rx();

    if (!lr2021_ok(err) || st.length == 0) return;
    if (!st.crc_ok) {
        gCrc++;
        return;
    }

    static uint8_t payload[6 + RADIO_MAX_PAYLOAD];
    size_t len = frameLength(buf, st.length);
    payload[0] = (uint8_t)(st.rssi_dbm & 0xFF);
    payload[1] = (uint8_t)((st.rssi_dbm >> 8) & 0xFF);
    payload[2] = (uint8_t)st.snr_db;
    payload[3] = phy_crc_error ? 0 : 1;
    payload[4] = (uint8_t)(len & 0xFF);
    payload[5] = (uint8_t)(len >> 8);
    memcpy(payload + 6, buf, len);
    sendFrame(BR_RX, payload, (uint16_t)(6 + len));
    gRx++;
    gLastOkMs = now_ms();
}

static void handleHello(void)
{
    uint8_t p[8] = {1, FW_VERSION[0], FW_VERSION[1], FW_VERSION[2],
                    gChipVersion[0], gChipVersion[1],
                    (uint8_t)(CAPS & 0xFF), (uint8_t)(CAPS >> 8)};
    sendFrame(BR_HELLO_ACK, p, sizeof(p));
}

static void handleCfg(const BridgeFrame &f)
{
    CfgPayload next;
    if (!cfgDecode(f.payload, f.len, next)) {
        uint8_t ack[10];
        cfgAckEncode(3, gCfg, ack);
        sendFrame(BR_CFG_ACK, ack, sizeof(ack));
        return;
    }
    gCfg = next;
    bool ok = radioApply(gCfg);
    uint8_t ack[10];
    cfgAckEncode(ok ? 0 : 1, gCfg, ack);
    sendFrame(BR_CFG_ACK, ack, sizeof(ack));
}

static void handleFrame(const BridgeFrame &f)
{
    switch (f.kind) {
    case BR_HELLO: handleHello(); break;
    case BR_CFG_EXT: {
        CfgExtPayload ext;
        if (cfgExtDecode(f.payload, f.len, ext)) {
            gSlotRole = (uint8_t)(ext.local_id & 1u);
            gHostEpochOffsetMs = ext.epoch_ms - local_ms();
#if LR2021_ENABLE_TDMA
            gSlotConfigured = true;
#endif
            char msg[64];
            snprintf(msg, sizeof(msg), "slot role=%u id=%lu epoch_ms=%llu",
                     (unsigned)gSlotRole, (unsigned long)ext.local_id,
                     (unsigned long long)ext.epoch_ms);
            sendFrame(BR_EVT, (const uint8_t *)msg, (uint16_t)strlen(msg));
        }
        break;
    }
    case BR_CFG:   handleCfg(f); break;
    case BR_TX:    txPacket(f.payload, f.len); break;
    case BR_PING:
        sendFrame(BR_PONG, NULL, 0);
        sendStat();
#if LR2021_E80_COMPAT
        {
            uint16_t packets = 0, crc_errors = 0, length_errors = 0;
            Lr2021Error e = gRadio.get_flrc_rx_stats(packets, crc_errors, length_errors);
            char msg[64];
            snprintf(msg, sizeof(msg), "flrc_rx valid=%u crc=%u len=%u err=%d",
                     (unsigned)packets, (unsigned)crc_errors,
                     (unsigned)length_errors, (int)e);
            sendFrame(BR_EVT, (const uint8_t *)msg, (uint16_t)strlen(msg));
        }
        {
            char mm[96];
            snprintf(mm, sizeof(mm),
                     "cca deferral=%u capped=%u guard_us=%u slot_role=%u slot_wait_ms=%u usb_short=%u",
                     (unsigned)gCcaDeferrals, (unsigned)gCcaTimeouts,
                     (unsigned)gCcaLastGuardUs, (unsigned)gSlotConfigured ? (unsigned)gSlotRole : 9,
                     (unsigned)gSlotWaitMs, (unsigned)gUsbShortWrites);
            sendFrame(BR_EVT, (const uint8_t *)mm, (uint16_t)strlen(mm));
        }
#endif
        break;
    default: break;
    }
}

extern "C" void app_main(void)
{
    usb_serial_jtag_driver_config_t uj = {};
    uj.tx_buffer_size = 16384;
    uj.rx_buffer_size = 16384;
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&uj));

    gCfg.band = 0;
    gCfg.frequency_hz = 868100000UL;
    gCfg.bitrate_kbps = 650;
    gCfg.tx_power_dbm = 14;
    gCfg.radio_payload = 128; // Stable FIFO/data path on current S3/C3 bench.
                              // 160/192 fails host link CRC on this RF pair.
    gCfg.relay = false;
    gCfg.sub_ghz = true;
    memcpy(gCfg.sync_word, "\x2D\xD4\xD4\xB2", 4);

    radioApply(gCfg);
    gLastOkMs = now_ms();
    gLastInitMs = now_ms();

    static uint8_t buf[256];
    uint32_t lastStat = now_ms();

    for (;;) {
        /* RX has priority over host commands: a just-completed radio frame must
         * be consumed before a queued TX request can clear/overwrite FIFO
         * events. */
        handleRx();

        /* Service radio RX on a 1 ms cadence (CONFIG_FREERTOS_HZ=1000). A
         * 128-byte FLRC frame occupies only ~1.6 ms of airtime. */
        int n = usb_serial_jtag_read_bytes(buf, sizeof(buf), pdMS_TO_TICKS(1));
        if (n > 0 && gDecoder.push(buf, (size_t)n)) {
            BridgeFrame f;
            while (gDecoder.next(f)) {
                handleRx();
                handleFrame(f);
            }
        }

        handleRx();

        if ((now_ms() - lastStat) > 5000) {
            lastStat = now_ms();
            sendStat();
        }
    }
}
