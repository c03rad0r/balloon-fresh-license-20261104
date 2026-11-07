/*
 * ESP32 bridge for FIPS over LR2021/FLRC.
 *
 * Radio side reuses the PROVEN driver from
 * tracker/firmware/components/lr2021_transport (EspIdfLr2021Radio). That driver
 * already encodes every carrier quirk we hit while reimplementing it:
 *   - SET_STANDBY_XOSC (TCXO module, RC standby leaves it unclocked)
 *   - hardware CS + SPI_DEVICE_HALFDUPLEX
 *   - FLRC packet type 0x05
 *   - IRQ status register reads back 0 on this chip -> poll the DIO pin
 *   - carrier-specific bitrate table (650 kbps = 0x03)
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

static const uint8_t FW_VERSION[3] = {0, 3, 0};
static const uint16_t CAPS = 0x0007;

static EspIdfLr2021Radio gRadio;
static Lr2021Config gRadioCfg;
static CfgPayload gCfg;
static uint8_t gChipVersion[4] = {0};
static BridgeDecoder gDecoder;

static uint32_t gTx, gRx, gCrc, gDrops, gTimeouts, gResets;
static uint32_t gLastOkMs, gLastInitMs;
static bool gRadioOk;

static uint32_t now_ms(void) { return (uint32_t)(esp_timer_get_time() / 1000); }

static void sendFrame(uint8_t kind, const uint8_t *payload, uint16_t len)
{
    static uint8_t out[BRIDGE_MAX_PAYLOAD + 16];
    size_t n = bridgeEncode(kind, payload, len, out, sizeof(out));
    if (n) usb_serial_jtag_write_bytes(out, n, pdMS_TO_TICKS(50));
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
    gRadioCfg.freq_mhz = (float)cfg.frequency_hz / 1000000.0f;
    gRadioCfg.bitrate_kbps = cfg.bitrate_kbps;
    gRadioCfg.tx_power_dbm = cfg.tx_power_dbm;
    gRadioCfg.crc_enabled = true;
    gRadioCfg.payload_length = (uint8_t)cfg.radio_payload;
    memcpy(gRadioCfg.sync_word, cfg.sync_word, 4);

    Lr2021Error err = gRadio.init(gRadioCfg);
    gLastInitMs = now_ms();
    gRadioOk = (err == Lr2021Error::Ok);
    if (gRadioOk) {
        gRadio.start_rx();
        gLastOkMs = now_ms();
    } else {
        gResets++;
        gRadioOk = false;
    }
    return gRadioOk;
}

static void txPacket(const uint8_t *data, size_t len)
{
    if (!gRadioOk || len == 0 || len > gCfg.radio_payload) return;

    gRadio.send_packet(data, len);
    gTx++;

    /* Wait for the DIO line: the IRQ status register is unusable on this chip. */
    bool asserted = false;
    uint32_t start = now_ms();
    while ((now_ms() - start) < 60) {
        if (lr2021_ok(gRadio.check_irq(asserted)) && asserted) break;
        esp_rom_delay_us(50);
    }
    if (!asserted) gTimeouts++;

    gRadio.clear_irq();
    gRadio.start_rx();
    gLastOkMs = now_ms();
}

static void handleRx(void)
{
    if (!gRadioOk) return;

    bool asserted = false;
    if (!lr2021_ok(gRadio.check_irq(asserted)) || !asserted) return;

    static uint8_t buf[255];
    PacketStatus st;
    Lr2021Error err = gRadio.read_packet(buf, sizeof(buf), st);
    gRadio.clear_irq();
    gRadio.start_rx();

    if (!lr2021_ok(err) || st.length == 0) return;
    if (!st.crc_ok) {
        gCrc++;
        return;
    }

    static uint8_t payload[6 + 255];
    payload[0] = (uint8_t)(st.rssi_dbm & 0xFF);
    payload[1] = (uint8_t)((st.rssi_dbm >> 8) & 0xFF);
    payload[2] = (uint8_t)st.snr_db;
    payload[3] = 1;
    payload[4] = (uint8_t)(st.length & 0xFF);
    payload[5] = (uint8_t)(st.length >> 8);
    memcpy(payload + 6, buf, st.length);
    sendFrame(BR_RX, payload, (uint16_t)(6 + st.length));
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
    case BR_CFG:   handleCfg(f); break;
    case BR_TX:    txPacket(f.payload, f.len); break;
    case BR_PING:  sendFrame(BR_PONG, NULL, 0); sendStat(); break;
    default: break;
    }
}

extern "C" void app_main(void)
{
    usb_serial_jtag_driver_config_t uj = {};
    uj.tx_buffer_size = 1024;
    uj.rx_buffer_size = 4096;
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&uj));

    gCfg.band = 0;
    gCfg.frequency_hz = 868100000UL;
    gCfg.bitrate_kbps = 650;
    gCfg.tx_power_dbm = 14;
    gCfg.radio_payload = 255;
    gCfg.relay = false;
    gCfg.sub_ghz = true;
    memcpy(gCfg.sync_word, "\x2D\xD4\xD4\xB2", 4);

    radioApply(gCfg);
    gLastOkMs = now_ms();
    gLastInitMs = now_ms();

    static uint8_t buf[256];
    uint32_t lastStat = now_ms();

    for (;;) {
        int n = usb_serial_jtag_read_bytes(buf, sizeof(buf), pdMS_TO_TICKS(20));
        if (n > 0 && gDecoder.push(buf, (size_t)n)) {
            BridgeFrame f;
            while (gDecoder.next(f)) handleFrame(f);
        }

        handleRx();

        if ((now_ms() - lastStat) > 5000) {
            lastStat = now_ms();
            sendStat();
        }
    }
}
