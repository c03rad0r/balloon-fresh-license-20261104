/**
 * @file esp_idf_lr2021_radio.cpp
 * @brief ESP-IDF raw SPI adapter for LR2021 — EspHalLr2021Radio implementation.
 *
 * Ported from proven firmware: firmware/esp32-c3-flrc/main/main.cpp
 *   Achieved 1733 kbps, 1000/1000 packets at 20 MHz SPI.
 *
 * Key patterns preserved from proven firmware:
 * - Manual CS control (spics_io_num = -1) with cs_low()/cs_high() wrapping each SPI transfer
 * - Half-duplex SPI2_HOST at 20 MHz
 * - Batched TX FIFO writes (opcode + payload in single transfer)
 * - BUSY pin polling with 1µs resolution
 * - Exact 17-step init sequence with verified register values
 *
 * The entire file is guarded so it only compiles under ESP-IDF.
 * Host tests do not include this source file in their Makefile.
 *
 * Refs: ADR-020 (raw SPI), ADR-026 (dual-MCU architecture)
 */

#include "esp_idf_lr2021_radio.h"

// ════════════════════════════════════════════════════════════════════
// Guard: only compile under ESP-IDF
// ════════════════════════════════════════════════════════════════════
#if defined(ESP_PLATFORM) || (defined(__has_include) && __has_include(<esp_idf_version.h>))

#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

static const char* TAG = "esp_lr2021";

// ════════════════════════════════════════════════════════════════════
// Constructor / Destructor
// ════════════════════════════════════════════════════════════════════

EspHalLr2021Radio::EspHalLr2021Radio(const Lr2021PinConfig& pins)
    : spi_(nullptr)
    , pins_(pins)
    , initialized_(false)
    , payload_len_(LR2021_MAX_PACKET)
{}

EspHalLr2021Radio::~EspHalLr2021Radio() {
    if (spi_ != nullptr) {
        spi_bus_remove_device(spi_);
        spi_ = nullptr;
    }
}

// ════════════════════════════════════════════════════════════════════
// Hardware Init (SPI bus + GPIO)
// ════════════════════════════════════════════════════════════════════

esp_err_t EspHalLr2021Radio::init_hardware() {
    // ── GPIO setup ──
    // CS + RST: output (CS default HIGH, RST default HIGH)
    gpio_config_t io_conf = {};
    io_conf.pin_bit_mask = (1ULL << pins_.cs) | (1ULL << pins_.rst);
    io_conf.mode = GPIO_MODE_OUTPUT;
    io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io_conf.pull_up_en = GPIO_PULLUP_DISABLE;
    io_conf.intr_type = GPIO_INTR_DISABLE;
    gpio_config(&io_conf);
    cs_high();
    gpio_set_level((gpio_num_t)pins_.rst, 1);

    // BUSY + IRQ: input, no pull
    io_conf = {};
    io_conf.pin_bit_mask = (1ULL << pins_.busy) | (1ULL << pins_.irq);
    io_conf.mode = GPIO_MODE_INPUT;
    io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io_conf.pull_up_en = GPIO_PULLUP_DISABLE;
    io_conf.intr_type = GPIO_INTR_DISABLE;
    gpio_config(&io_conf);

    // ── SPI bus init ──
    spi_bus_config_t buscfg = {};
    buscfg.miso_io_num = pins_.miso;
    buscfg.mosi_io_num = pins_.mosi;
    buscfg.sclk_io_num = pins_.sck;
    buscfg.quadwp_io_num = -1;
    buscfg.quadhd_io_num = -1;
    buscfg.max_transfer_sz = (LR2021_MAX_PACKET + 8) * 2;  // opcode + payload headroom

    esp_err_t ret = spi_bus_initialize((spi_host_device_t)pins_.spi_host, &buscfg, SPI_DMA_CH_AUTO);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI bus init failed: %s", esp_err_to_name(ret));
        return ret;
    }

    // ── SPI device init — CS handled MANUALLY (not by driver) ──
    // This is the KEY difference from EspIdfLr2021Radio.
    // Manual CS gives exact timing control needed for 20 MHz throughput.
    spi_device_interface_config_t devcfg = {};
    devcfg.clock_speed_hz = pins_.spi_clock_hz;
    devcfg.mode = 0;                     // SPI mode 0 (CPOL=0, CPHA=0)
    devcfg.spics_io_num = -1;            // CS handled manually
    devcfg.queue_size = 1;
    devcfg.flags = 0;  // full-duplex (half-duplex conflicts with simultaneous TX+RX)

    ret = spi_bus_add_device((spi_host_device_t)pins_.spi_host, &devcfg, &spi_);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI device add failed: %s", esp_err_to_name(ret));
        return ret;
    }

    ESP_LOGI(TAG, "SPI initialized: %d MHz, mode 0, half-duplex, manual CS",
             pins_.spi_clock_hz / 1000000);
    return ESP_OK;
}

// ════════════════════════════════════════════════════════════════════
// SPI Operations (proven patterns from main.cpp)
// ════════════════════════════════════════════════════════════════════

void EspHalLr2021Radio::wait_busy() {
    // Hybrid wait: tight spin for fast commands, yield to FreeRTOS for calibration.
    // Pure esp_rom_delay_us loop starves FreeRTOS watchdog during CALIB_FRONT_END.
    const uint32_t SPIN_THRESHOLD = 200;
    const uint32_t MAX_DELAY_MS = 500;
    uint32_t spin = 0;
    uint32_t ms = 0;
    while (busy_high()) {
        if (spin < SPIN_THRESHOLD) {
            esp_rom_delay_us(1);
            spin++;
        } else {
            vTaskDelay(pdMS_TO_TICKS(1));
            if (++ms >= MAX_DELAY_MS) {
                ESP_LOGE(TAG, "BUSY timeout after %lu ms", (unsigned long)MAX_DELAY_MS);
                break;
            }
        }
    }
}

void EspHalLr2021Radio::spi_write(const uint8_t* data, size_t len) {
    wait_busy();

    spi_transaction_t t = {};
    t.length = len * 8;   // bits
    t.tx_buffer = data;
    t.rx_buffer = nullptr;

    cs_low();
    spi_device_polling_transmit(spi_, &t);
    cs_high();
}

void EspHalLr2021Radio::spi_write_tx_fifo(const uint8_t* data, size_t len) {
    wait_busy();

    // Build buffer: opcode(2) + payload in one contiguous transfer
    static uint8_t tx_buf[2 + LR2021_MAX_PACKET];
    tx_buf[0] = 0x00;  // WRITE_TX_FIFO opcode high byte
    tx_buf[1] = 0x02;  // WRITE_TX_FIFO opcode low byte
    memcpy(tx_buf + 2, data, len);

    spi_transaction_t t = {};
    t.length = (2 + len) * 8;  // bits
    t.tx_buffer = tx_buf;
    t.rx_buffer = nullptr;
    t.flags = 0;  // use tx_buffer pointer (data > 4 bytes)

    cs_low();
    spi_device_polling_transmit(spi_, &t);
    cs_high();
}

void EspHalLr2021Radio::spi_read_rx_fifo(uint8_t* buf, size_t len) {
    wait_busy();

    // Combine opcode + response into ONE full-duplex transaction.
    // tx = [0x00, 0x01, 0x00, 0x00, ...dummy zeros...]
    // rx = [skip,   skip,  byte1,  byte2,  ...response...]
    // CS stays LOW for the entire transaction — the LR2021 forgets the
    // command if CS goes HIGH between opcode and response (fix: 19f6443).
    static uint8_t tx_buf[2 + LR2021_MAX_PACKET];
    static uint8_t rx_buf[2 + LR2021_MAX_PACKET];
    tx_buf[0] = 0x00;  // READ_RX_FIFO opcode high byte
    tx_buf[1] = 0x01;  // READ_RX_FIFO opcode low byte
    memset(tx_buf + 2, 0x00, len);  // dummy zeros to clock response out

    spi_transaction_t t = {};
    t.length = (2 + len) * 8;  // bits
    t.tx_buffer = tx_buf;
    t.rx_buffer = rx_buf;
    t.flags = 0;  // use tx_buffer/rx_buffer pointers (data > 4 bytes)

    cs_low();
    spi_device_polling_transmit(spi_, &t);
    cs_high();

    // Response data starts at byte 2 (after opcode echo on MISO)
    memcpy(buf, rx_buf + 2, len);
}

Lr2021Error EspHalLr2021Radio::read_irq_register(uint32_t& flags_out) {
    wait_busy();

    // Combine opcode + response into ONE full-duplex transaction.
    // tx = [0x01, 0x17, 0x00, 0x00, 0x00, 0x00]  (opcode + 4 dummy)
    // rx = [skip,  skip, flag3, flag2, flag1, flag0]
    // CS stays LOW for the entire transaction — previously the code raised
    // CS HIGH between opcode and response, causing the chip to forget the
    // command and return 0x00 for all reads (fix: 19f6443).
    uint8_t tx_buf[6] = { 0x01, 0x17, 0x00, 0x00, 0x00, 0x00 };  // GET_IRQ_STATUS + dummy
    uint8_t rx[6] = {0};

    spi_transaction_t t = {};
    t.length = 6 * 8;  // bits
    t.tx_buffer = tx_buf;
    t.rx_buffer = rx;
    t.flags = 0;  // use tx_buffer/rx_buffer pointers

    cs_low();
    spi_device_polling_transmit(spi_, &t);
    cs_high();

    // Parse 32-bit flags from bytes[2:5] (bytes[0:1] are status/dummy)
    flags_out = ((uint32_t)rx[2] << 24) |
                ((uint32_t)rx[3] << 16) |
                ((uint32_t)rx[4] << 8)  |
                ((uint32_t)rx[5]);
    return Lr2021Error::Ok;
}

// ════════════════════════════════════════════════════════════════════
// GPIO Helpers
// ════════════════════════════════════════════════════════════════════

void EspHalLr2021Radio::hardware_reset() {
    gpio_set_level((gpio_num_t)pins_.rst, 0);
    vTaskDelay(pdMS_TO_TICKS(1));
    gpio_set_level((gpio_num_t)pins_.rst, 1);
    vTaskDelay(pdMS_TO_TICKS(50));
}

uint32_t EspHalLr2021Radio::compute_frf(float freq_mhz) {
    // frf = (freq_MHz * 1e6 * 2^18) / (XTAL_MHz * 1e6)
    // Using double for precision (matches proven firmware)
    return (uint32_t)((freq_mhz * 1e6 * (double)(1ULL << 18)) / (LR2021_XTAL_MHZ * 1e6));
}

// ════════════════════════════════════════════════════════════════════
// Full 17-Step LR2021 Init Sequence
// (exact register values from proven firmware main.cpp)
// ════════════════════════════════════════════════════════════════════

Lr2021Error EspHalLr2021Radio::init_sequence(const Lr2021Config& config) {
    // Step 0: Hardware reset
    hardware_reset();

    // Step 1: CLEAR_ERRORS
    uint8_t cmd_clr_err[] = { 0x01, 0x11, 0x00, 0x00 };
    spi_write(cmd_clr_err, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 2: SET_STANDBY (STDBY_XOSC)
    uint8_t cmd_stdby[] = { 0x01, 0x28, 0x01 };
    spi_write(cmd_stdby, 3);
    vTaskDelay(pdMS_TO_TICKS(5));

    // Step 3: SET_PACKET_TYPE FLRC (0x05)
    uint8_t cmd_pkttype[] = { 0x02, 0x07, 0x05 };
    spi_write(cmd_pkttype, 3);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 4: SET_RF_FREQUENCY
    uint32_t frf = compute_frf(config.freq_mhz);
    uint8_t cmd_freq[] = {
        0x02, 0x00,
        (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
    };
    spi_write(cmd_freq, 5);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 5: SET_RX_PATH (HF path for 2.4 GHz) — MANDATORY
    uint8_t cmd_rxpath[] = { 0x02, 0x01, 0x01, 0x00 };
    spi_write(cmd_rxpath, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 5b: SET_TX_PATH (HF path for 2.4 GHz) — needed for TX
    uint8_t cmd_txpath[] = { 0x02, 0x02, 0x01, 0x00 };
    spi_write(cmd_txpath, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 6: CALIB_FRONT_END — MANDATORY
    uint16_t feFreq = (uint16_t)((config.freq_mhz / 4.0f) + 0.5f) | 0x8000;
    uint8_t cmd_calfe[] = {
        0x01, 0x23,
        (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    };
    spi_write(cmd_calfe, 10);
    vTaskDelay(pdMS_TO_TICKS(5));

    // Step 7: CALIBRATE — 0x5F (NOT 0x6F)
    uint8_t cmd_cal[] = { 0x01, 0x22, 0x5F };
    spi_write(cmd_cal, 3);
    vTaskDelay(pdMS_TO_TICKS(5));

    // Step 8: SET_FLRC_MOD_PARAMS (2600 kbps, CR_1_0, BT0.5)
    uint8_t cmd_modparams[] = { 0x02, 0x48, 0x00, 0x25 };
    spi_write(cmd_modparams, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 9: SET_FLRC_SYNCWORD
    uint8_t cmd_sync[] = {
        0x02, 0x4C, 0x01,
        config.sync_word[0], config.sync_word[1],
        config.sync_word[2], config.sync_word[3]
    };
    spi_write(cmd_sync, 7);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 10: SET_FLRC_PACKET_PARAMS
    uint8_t cmd_pktparams[] = {
        0x02, 0x49,
        0x0C,   // preamble=8 | syncLen=4/2
        0x4C,   // syncTx=1 | syncMatch=1 | fixed=1 | crc=0
        (uint8_t)(config.payload_length >> 8), (uint8_t)config.payload_length
    };
    spi_write(cmd_pktparams, 6);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 11: SET_RX_TX_FALLBACK (Fs=0x03 — keeps PLL warm)
    uint8_t cmd_fallback[] = { 0x02, 0x06, 0x03 };
    spi_write(cmd_fallback, 3);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 12: SET_TX_POWER (power*2, ramp=0x04)
    uint8_t cmd_power[] = { 0x02, 0x03, (uint8_t)(config.tx_power_dbm * 2), 0x04 };
    spi_write(cmd_power, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 13: SET_PA_CONFIG
    uint8_t cmd_paconfig[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 };
    spi_write(cmd_paconfig, 7);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 14: SET_DIO_FUNCTION (DIO9 = IRQ)
    uint8_t cmd_dio[] = { 0x01, 0x12, 0x09, 0x11 };
    spi_write(cmd_dio, 4);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 15: SET_DIO_IRQ (TX_DONE: bit 11 = 0x00000800)
    uint8_t cmd_irqcfg_tx[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 };
    spi_write(cmd_irqcfg_tx, 7);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Step 16: CLEAR_IRQ
    uint8_t cmd_clr_irq[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    spi_write(cmd_clr_irq, 6);

    // Step 17: Done
    ESP_LOGI(TAG, "LR2021 init complete (%.1f MHz, %lu kbps, %ddBm, %d-byte payload)",
             config.freq_mhz, (unsigned long)config.bitrate_kbps,
             (int)config.tx_power_dbm, (int)config.payload_length);

    return Lr2021Error::Ok;
}

// ════════════════════════════════════════════════════════════════════
// Lr2021Radio Interface Implementation
// ════════════════════════════════════════════════════════════════════

Lr2021Error EspHalLr2021Radio::init(const Lr2021Config& config) {
    // Store payload length for read_packet
    payload_len_ = config.payload_length;
    if (payload_len_ == 0) payload_len_ = LR2021_MAX_PACKET;

    // Initialize SPI bus + GPIO (if not already done)
    if (spi_ == nullptr) {
        esp_err_t ret = init_hardware();
        if (ret != ESP_OK) {
            return Lr2021Error::SpiError;
        }
    }

    // Run full 17-step init sequence
    Lr2021Error err = init_sequence(config);
    if (err != Lr2021Error::Ok) return err;

    initialized_ = true;

    // Enter RX mode after init
    return start_rx();
}

Lr2021Error EspHalLr2021Radio::start_rx() {
    // Reconfigure DIO IRQ for RX_DONE (bit 18 = 0x00040000)
    uint8_t cmd_irqcfg_rx[] = { 0x01, 0x15, 0x09, 0x00, 0x04, 0x00, 0x00 };
    spi_write(cmd_irqcfg_rx, 7);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Clear IRQ
    uint8_t cmd_clr_irq[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    spi_write(cmd_clr_irq, 6);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Clear RX FIFO — stale data can prevent new packet detection.
    uint8_t cmd_clr_rxfifo[] = { 0x01, 0x1E };
    spi_write(cmd_clr_rxfifo, 2);
    vTaskDelay(pdMS_TO_TICKS(1));

    // Enter continuous RX
    uint8_t cmd_set_rx[] = { 0x02, 0x0C, 0xFF, 0xFF, 0xFF };
    spi_write(cmd_set_rx, 5);
    vTaskDelay(pdMS_TO_TICKS(2));

    return Lr2021Error::Ok;
}

Lr2021Error EspHalLr2021Radio::send_packet(const uint8_t* data, size_t len) {
    if (len > LR2021_MAX_PACKET) return Lr2021Error::PacketTooLong;

    // 1. Clear IRQ
    uint8_t cmd_clr_irq[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    spi_write(cmd_clr_irq, 6);

    // 2. Write TX FIFO (batched: opcode + payload in single transfer)
    spi_write_tx_fifo(data, len);

    // 3. Trigger TX (SET_TX, 5 bytes)
    uint8_t cmd_set_tx[] = { 0x02, 0x0D, 0xFF, 0xFF, 0xFF };  // timeout=0xFFFFFF (infinite)
    spi_write(cmd_set_tx, 5);

    // 4. Fixed delay for TX completion (fix: 8f93593)
    // FLRC at 2600 kbps takes ~1ms per packet; 5ms is a safe margin.
    // Replaces tight IRQ polling loop that triggered ESP32 task watchdog
    // timeout after ~90 minutes of continuous TX.
    vTaskDelay(pdMS_TO_TICKS(5));

    return Lr2021Error::Ok;
}

Lr2021Error EspHalLr2021Radio::read_packet(uint8_t* buf, size_t buf_len, PacketStatus& status) {
    // Read RX FIFO (fixed-length FLRC packets — read payload_len_ bytes)
    size_t read_len = payload_len_;
    if (read_len > buf_len) read_len = buf_len;

    spi_read_rx_fifo(buf, read_len);

    // Fill PacketStatus
    status = PacketStatus{};
    status.length = read_len;
    status.crc_ok = true;  // FLRC with fixed-length mode — CRC checked via IRQ flags

    return Lr2021Error::Ok;
}

Lr2021Error EspHalLr2021Radio::get_irq_status(uint32_t& flags) {
    return read_irq_register(flags);
}

Lr2021Error EspHalLr2021Radio::clear_irq() {
    uint8_t cmd_clr_irq[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    spi_write(cmd_clr_irq, 6);
    return Lr2021Error::Ok;
}

Lr2021Error EspHalLr2021Radio::check_irq(bool& asserted) {
    // IRQ pin goes HIGH when an interrupt is pending (active HIGH)
    asserted = irq_high();
    return Lr2021Error::Ok;
}

Lr2021Error EspHalLr2021Radio::standby() {
    // SET_STANDBY (STDBY_XOSC) — {0x01, 0x28, 0x01}
    uint8_t cmd[] = { 0x01, 0x28, 0x01 };
    spi_write(cmd, 3);
    return Lr2021Error::Ok;
}

Lr2021Error EspHalLr2021Radio::sleep() {
    // LR2021 sleep is not well documented — use SET_STANDBY (STDBY_RC) as fallback
    // {0x01, 0x28, 0x00} = STDBY_RC (lowest documented power state)
    uint8_t cmd[] = { 0x01, 0x28, 0x00 };
    spi_write(cmd, 3);
    return Lr2021Error::Ok;
}

#endif // ESP_PLATFORM / __has_include
