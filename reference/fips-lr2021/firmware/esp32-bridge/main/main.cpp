/*
 * ESP32 bridge for FIPS over LR2021/FLRC.
 *
 * Speaks the same host protocol as the RP2040 and STM32 bridges
 * (docs/BRIDGE-PROTOCOL.md), so fips-lr2021ctl / fips-lr2021d / the FIPS
 * lr2021 transport work unchanged.
 *
 * Reuses the proven raw register driver from firmware/e80-bypass/common by
 * supplying the ESP-IDF equivalents of the RP2040 macros it expects.
 *
 * Carrier differences are compile-time:
 *   E80_RADIO_IRQ_DIO   8 for the E80, 9 for the NiceRF carrier
 *   E80_RFREQ_FRF       0 plain 4-byte Hz (E80), 1 FRF (NiceRF carrier)
 *   E80_BRIDGE_CARRIER_INIT 1 to use the carrier init sequence
 */
#include <stdio.h>
#include <string.h>

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "driver/usb_serial_jtag.h"
#include "esp_rom_sys.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define E80_HOST_ESP32C3
#include "e80_pinmap.h"

static spi_device_handle_t s_spi;

static void spi_xfer(const uint8_t *tx, uint8_t *rx, size_t len)
{
    spi_transaction_t t = {0};
    t.length = len * 8;
    t.rxlength = rx ? (len * 8) : 0;
    t.tx_buffer = tx;
    t.rx_buffer = rx;
    spi_device_transmit(s_spi, &t);
}

/* The SPI peripheral drives CS via spics_io_num, matching the carrier's own
 * proven driver (SPI_DEVICE_HALFDUPLEX + hardware CS). */
#define E80_CS_LOW()   do {} while (0)
#define E80_CS_HIGH()  do {} while (0)
#define E80_SPI_TX(b, n) do { spi_xfer((const uint8_t *)(b), NULL, (n)); } while (0)
#define E80_SPI_RX(b, n) do { spi_xfer(NULL, (uint8_t *)(b), (n)); } while (0)
#define E80_BUSY_READ() (gpio_get_level(PIN_BUSY) == 1)
#define E80_IRQ_READ()  (gpio_get_level(PIN_IRQ) == 1)
#define E80_DELAY_US(us) esp_rom_delay_us(us)
#define E80_DELAY_MS(ms) vTaskDelay(pdMS_TO_TICKS(ms))

#include "e80_lr20xx_raw.h"
#include "bridge_protocol.h"

#ifndef E80_BRIDGE_CARRIER_INIT
#define E80_BRIDGE_CARRIER_INIT 0
#endif

static const uint8_t FW_VERSION[3] = {0, 2, 0};
static const uint16_t CAPS = 0x0007; /* LF, HF, relay */

static CfgPayload gCfg;
static uint8_t gChipVersion[4] = {0};
static BridgeDecoder gDecoder;

static uint32_t gTx, gRx, gCrc, gDrops, gTimeouts, gResets;
static uint32_t gLastOkMs, gLastInitMs;
static bool gRadioOk;

static uint32_t now_ms(void) { return (uint32_t)(esp_timer_get_time() / 1000); }

#ifndef E80_SPI_HZ
#define E80_SPI_HZ 4000000
#endif

static void rfHardReset(void)
{
    gpio_set_level(PIN_RST, 0);
    vTaskDelay(pdMS_TO_TICKS(20));
    gpio_set_level(PIN_RST, 1);
    vTaskDelay(pdMS_TO_TICKS(50));
}

static uint8_t powerHalfDb(int8_t dbm)
{
    int v = (int)dbm * 2;
    if (v < -20) v = -20;
    if (v > 44) v = 44;
    return (uint8_t)v;
}

/* The raw driver's rfFlrcSetSyncWord() writes a fixed 12AD101B. The bridge must
 * use the value from CFG so it can match a peer, so write it explicitly. */
static void setSyncWord(const uint8_t sync[4])
{
    uint8_t p[5] = {0x01, sync[0], sync[1], sync[2], sync[3]};
    rfWrite2(OC_FLRC_SYNCWORD, p, 5);
}

#if E80_BRIDGE_CARRIER_INIT
/* Sequence taken from this carrier's own proven driver
 * (tracker/firmware/components/lr2021_transport): XOSC standby, because the
 * module carries a TCXO and does not answer SPI out of RC standby. */
static int radioInit(const CfgPayload &cfg)
{
    rfHardReset();
    vTaskDelay(pdMS_TO_TICKS(10));

    { uint8_t c[] = {0x01, 0x11, 0x00, 0x00}; rfWriteCmd(c, 4); }  /* CLEAR_ERRORS */
    { uint8_t c[] = {0x01, 0x28, 0x01}; rfWriteCmd(c, 3); }        /* STANDBY_XOSC */
    vTaskDelay(pdMS_TO_TICKS(5));

    { uint8_t c[] = {0x02, 0x07, 0x05}; rfWriteCmd(c, 3); }        /* PACKET_TYPE FLRC */
    vTaskDelay(pdMS_TO_TICKS(1));

    rfSetRfFreqHz(cfg.frequency_hz);
    vTaskDelay(pdMS_TO_TICKS(1));

    { uint8_t c[] = {0x02, 0x01, (uint8_t)(cfg.sub_ghz ? 0x00 : 0x01), 0x00};
      rfWriteCmd(c, 4); }
    vTaskDelay(pdMS_TO_TICKS(1));

    uint16_t fe = (uint16_t)(cfg.frequency_hz / 4000000UL);
    if (!cfg.sub_ghz) fe |= 0x8000;
    { uint8_t c[] = {0x01, 0x23, (uint8_t)(fe >> 8), (uint8_t)(fe & 0xFF), 0, 0};
      rfWriteCmd(c, 6); }
    vTaskDelay(pdMS_TO_TICKS(5));

    { uint8_t c[] = {0x01, 0x22, 0x5F}; rfWriteCmd(c, 3); }        /* CALIBRATE */
    vTaskDelay(pdMS_TO_TICKS(10));

    rfGetVersion(gChipVersion);
    bool zero = !gChipVersion[0] && !gChipVersion[1] && !gChipVersion[2] && !gChipVersion[3];
    bool ff = gChipVersion[0] == 0xFF && gChipVersion[1] == 0xFF &&
              gChipVersion[2] == 0xFF && gChipVersion[3] == 0xFF;
    if (zero || ff) return 2;

    rfFlrcSetModParams(cfg.bitrate_kbps);
    vTaskDelay(pdMS_TO_TICKS(1));
    setSyncWord(cfg.sync_word);
    vTaskDelay(pdMS_TO_TICKS(1));

    /* preamble 16 (0x0E), syncTx=1, syncMatch=1, fixed length, CRC on */
    { uint8_t c[] = {0x02, 0x49, 0x0E, 0x4D,
                     (uint8_t)(cfg.radio_payload >> 8),
                     (uint8_t)(cfg.radio_payload & 0xFF)};
      rfWriteCmd(c, 6); }
    vTaskDelay(pdMS_TO_TICKS(1));

    if (cfg.sub_ghz) {
        rfSetPaCfgLf();
    } else {
        uint8_t c[] = {0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10};
        rfWriteCmd(c, 7);
    }
    vTaskDelay(pdMS_TO_TICKS(1));

    rfSetTxParams(powerHalfDb(cfg.tx_power_dbm));
    vTaskDelay(pdMS_TO_TICKS(1));
    rfSetFallbackFs();
    vTaskDelay(pdMS_TO_TICKS(1));

    rfSetDioIrqFunction();
    rfSetDioIrqMask(IRQ_RX_DONE | IRQ_TX_DONE | IRQ_CRC_ERROR);
    vTaskDelay(pdMS_TO_TICKS(1));

    rfClearTxFifo();
    rfClearRxFifo();
    rfClearIrq();
    vTaskDelay(pdMS_TO_TICKS(10));

    if (!rfWaitBusy()) return 1;
    rfSetRx();
    return 0;
}
#else
static int radioInit(const CfgPayload &cfg)
{
    rfHardReset();
    rfGetErrors();
    rfClearErrors();
    rfSetRegModeDcdc();
    rfSetTcxoMode2V2();
    vTaskDelay(pdMS_TO_TICKS(5));
    rfCfgLfClkRc();
    rfCalibrateAll();
    vTaskDelay(pdMS_TO_TICKS(5));
    (void)rfGetErrors();
    rfClearErrors();
    rfSetStandbyXosc();
    vTaskDelay(pdMS_TO_TICKS(5));

    if (rfGetVersion(gChipVersion) == 0) return 2;
    bool zero = !gChipVersion[0] && !gChipVersion[1] && !gChipVersion[2] && !gChipVersion[3];
    bool ff = gChipVersion[0] == 0xFF && gChipVersion[1] == 0xFF &&
              gChipVersion[2] == 0xFF && gChipVersion[3] == 0xFF;
    if (zero || ff) return 2;

    rfSetDioIrqFunction();
    rfSetPacketTypeFlrc();
    rfSetRfFreqHz(cfg.frequency_hz);
    rfSetRxPath(cfg.sub_ghz ? 0 : 1);
    if (cfg.sub_ghz) {
        rfSetPaCfgLf();
    } else {
        uint8_t c[] = {0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10};
        rfWriteCmd(c, 7);
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
#endif

static void sendFrame(uint8_t kind, const uint8_t *payload, uint16_t len)
{
    /* Static, not stack: this is 2 KB and the main task stack is small. */
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

static void radioRearm(void)
{
    rfClearErrors();
    rfClearIrq();
    rfSetRx();
}

static bool radioApply(const CfgPayload &cfg)
{
    int rc = radioInit(cfg);
    gLastInitMs = now_ms();
    gRadioOk = (rc == 0);
    if (gRadioOk) {
        gLastOkMs = now_ms();
    } else {
        gResets++;
    }
    return gRadioOk;
}

static void txPacket(const uint8_t *data, size_t len)
{
    if (!gRadioOk || len == 0 || len > gCfg.radio_payload) return;
    rfClearErrors();
    rfClearIrq();
    rfClearTxFifo();
    rfWriteTxFifo(data, len);
    rfSetTx();
    gTx++;

    uint32_t start = now_ms();
    bool done = false;
    while ((now_ms() - start) < 60) {
        uint32_t irq = rfGetIrqStatus();
        if (irq & IRQ_TX_DONE) { done = true; break; }
        if (irq & IRQ_CRC_ERROR) break;
    }
    if (!done) gTimeouts++;
    gLastOkMs = now_ms();
    rfClearIrq();
    radioRearm();
}

static void handleRx(void)
{
    uint32_t irq = rfGetIrqStatus();
    if (!(irq & (IRQ_RX_DONE | IRQ_CRC_ERROR))) return;

    if (irq & IRQ_CRC_ERROR) {
        gCrc++;
        rfClearRxFifo();
        rfClearIrq();
        radioRearm();
        return;
    }

    FlrcPktStatus st;
    rfFlrcGetPktStatus(&st);
    uint8_t buf[255];
    size_t want = st.len ? st.len : gCfg.radio_payload;
    if (want > sizeof(buf)) want = sizeof(buf);
    rfReadRxFifo(buf, want);
    size_t len = want;

    if (len > 0) {
        static uint8_t payload[6 + 255];
        int16_t rssi = (int16_t)(st.rssi_avg_dbm);
        payload[0] = (uint8_t)(rssi & 0xFF);
        payload[1] = (uint8_t)((rssi >> 8) & 0xFF);
        payload[2] = 0;
        payload[3] = 1;
        payload[4] = (uint8_t)(len & 0xFF);
        payload[5] = (uint8_t)(len >> 8);
        memcpy(payload + 6, buf, len);
        sendFrame(BR_RX, payload, (uint16_t)(6 + len));
        gRx++;
        gLastOkMs = now_ms();
    }

    rfClearRxFifo();
    rfClearIrq();
    radioRearm();
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
    gpio_config_t out = {
        .pin_bit_mask = (1ULL << PIN_RST),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&out);
    gpio_config_t in = {
        .pin_bit_mask = (1ULL << PIN_BUSY) | (1ULL << PIN_IRQ),
        .mode = GPIO_MODE_INPUT,
    };
    gpio_config(&in);

    spi_bus_config_t bus = {};
    bus.mosi_io_num = PIN_MOSI;
    bus.miso_io_num = PIN_MISO;
    bus.sclk_io_num = PIN_SCK;
    bus.quadwp_io_num = -1;
    bus.quadhd_io_num = -1;
    bus.max_transfer_sz = 64;
    ESP_ERROR_CHECK(spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_CH_AUTO));

    spi_device_interface_config_t dev = {};
    dev.clock_speed_hz = E80_SPI_HZ;
    dev.mode = 0;
    dev.spics_io_num = PIN_CS;
    dev.queue_size = 1;
    dev.flags = SPI_DEVICE_HALFDUPLEX;
    ESP_ERROR_CHECK(spi_bus_add_device(SPI2_HOST, &dev, &s_spi));

    usb_serial_jtag_driver_config_t uj = {};
    uj.tx_buffer_size = 1024;
    uj.rx_buffer_size = 4096;
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&uj));

    gCfg.band = 0; /* eu868 */
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

        if (gRadioOk && (now_ms() - gLastOkMs) > 30000 &&
            (now_ms() - gLastInitMs) > 60000) {
            gResets++;
            radioApply(gCfg);
        }
        if ((now_ms() - lastStat) > 5000) {
            lastStat = now_ms();
            sendStat();
        }
    }
}
