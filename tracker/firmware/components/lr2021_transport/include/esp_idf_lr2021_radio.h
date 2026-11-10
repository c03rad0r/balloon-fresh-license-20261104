/**
 * @file esp_idf_lr2021_radio.h
 * @brief ESP-IDF hardware adapter implementing Lr2021Radio for direct ESP32-C3 → LR2021 SPI.
 *
 * Ported from proven firmware: firmware/esp32-c3-flrc/main/main.cpp
 *   — 1733 kbps, 1000/1000 packets at 20 MHz SPI, half-duplex, MANUAL CS.
 *
 * This is a standalone adapter that coexists with the inline EspIdfLr2021Radio
 * in lr2021_spi.h. The key difference: EspHalLr2021Radio uses manual GPIO CS
 * control (spics_io_num = -1) exactly as the proven firmware does, which is
 * critical for achieving full 20 MHz throughput.
 *
 * ## Pin mapping (proven on ESP32-C3):
 *   SCK=GPIO6, MOSI=GPIO7, MISO=GPIO2, CS=GPIO10, BUSY=GPIO4, IRQ=GPIO5, RST=GPIO3
 *
 * The header is guarded so it compiles cleanly on host (mock) builds — the class
 * definition only appears when ESP-IDF headers are detected.
 *
 * Refs: ADR-020 (raw SPI), ADR-026 (dual-MCU architecture)
 */

#pragma once

#include "lr2021_spi.h"  // Lr2021Radio, Lr2021Config, Lr2021Error, PacketStatus, IrqSource, Lr2021Opcodes

#include <stdint.h>
#include <stddef.h>

// ── Pin Configuration (always available, no ESP-IDF deps) ───────────

/// Pin configuration for the LR2021 radio on ESP32-C3.
/// Defaults match the proven firmware (firmware/esp32-c3-flrc/main/main.cpp).
struct Lr2021PinConfig {
    int sck;            ///< SPI clock pin  (default GPIO6)
    int miso;           ///< SPI MISO pin   (default GPIO2)
    int mosi;           ///< SPI MOSI pin   (default GPIO7)
    int cs;             ///< SPI CS pin     (default GPIO10) — manually controlled
    int busy;           ///< LR2021 BUSY    (default GPIO4)
    int irq;            ///< LR2021 DIO9    (default GPIO5)
    int rst;            ///< LR2021 RESET   (default GPIO3)
    int spi_clock_hz;   ///< SPI clock speed (default 20 MHz)
    int spi_host;       ///< SPI peripheral (default SPI2_HOST = 1)

    Lr2021PinConfig()
        : sck(6), miso(2), mosi(7), cs(10)
        , busy(4), irq(5), rst(3)
        , spi_clock_hz(20000000)
        , spi_host(1)  // SPI2_HOST
    {}
};

// ── ESP-IDF Hardware Adapter (only when ESP-IDF is available) ───────

#if defined(ESP_PLATFORM) || (defined(__has_include) && __has_include(<esp_idf_version.h>))

#include "esp_err.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "rom/ets_sys.h"  // ets_delay_us()

/**
 * Real LR2021 radio driver for ESP32-C3 using ESP-IDF raw SPI + GPIO.
 *
 * Implements Lr2021Radio using ESP-IDF spi_device + gpio APIs.
 * Ported faithfully from proven firmware (firmware/esp32-c3-flrc/main/main.cpp).
 *
 * Key design decisions (from proven firmware):
 * - Manual CS control (spics_io_num = -1) — critical for 20 MHz throughput
 * - Half-duplex SPI mode
 * - Blocking BUSY pin polling with tight 1µs loop
 * - Batched TX FIFO writes (opcode + payload in single transfer)
 * - 17-step init sequence with exact register values
 */
class EspHalLr2021Radio : public Lr2021Radio {
public:
    /// Construct with optional pin configuration (defaults match proven firmware).
    explicit EspHalLr2021Radio(const Lr2021PinConfig& pins = Lr2021PinConfig{});
    ~EspHalLr2021Radio() override;

    // ── Lr2021Radio interface (all 9 virtual methods) ──

    Lr2021Error init(const Lr2021Config& config) override;
    Lr2021Error start_rx() override;
    Lr2021Error send_packet(const uint8_t* data, size_t len) override;
    Lr2021Error read_packet(uint8_t* buf, size_t buf_len, PacketStatus& status) override;
    Lr2021Error get_irq_status(uint32_t& flags) override;
    Lr2021Error clear_irq() override;
    Lr2021Error check_irq(bool& asserted) override;
    Lr2021Error standby() override;
    Lr2021Error sleep() override;

private:
    // ── Hardware state ──
    spi_device_handle_t spi_;     ///< ESP-IDF SPI device handle
    Lr2021PinConfig      pins_;   ///< Pin configuration
    bool                 initialized_;  ///< init() has been called
    uint16_t             payload_len_;  ///< Fixed FLRC payload length (from config)

    // ── SPI operations (proven patterns from main.cpp) ──

    /// Write command bytes (no read). Waits BUSY, asserts CS, transmits, deasserts CS.
    void spi_write(const uint8_t* data, size_t len);

    /// Write data to TX FIFO as a single batched transfer.
    /// Buffer: {0x00, 0x02} + payload.
    void spi_write_tx_fifo(const uint8_t* data, size_t len);

    /// Read from RX FIFO. Combines opcode {0x00, 0x01} + response into
    /// a SINGLE full-duplex SPI transaction under one CS assertion.
    /// The LR2021 forgets the command if CS goes HIGH between opcode
    /// and response bytes.
    void spi_read_rx_fifo(uint8_t* buf, size_t len);

    /// Read IRQ status. Combines opcode {0x01, 0x17} + 4-byte response
    /// into a SINGLE full-duplex SPI transaction under one CS assertion.
    /// Parses 32-bit flags from bytes[2:5].
    /// @param flags_out [out] 32-bit IRQ status word
    /// @return Lr2021Error::Ok on success
    Lr2021Error read_irq_register(uint32_t& flags_out);

    // ── GPIO helpers ──

    inline void cs_low()   { gpio_set_level((gpio_num_t)pins_.cs, 0); }
    inline void cs_high()  { gpio_set_level((gpio_num_t)pins_.cs, 1); }
    inline bool busy_high() { return gpio_get_level((gpio_num_t)pins_.busy) == 1; }
    inline bool irq_high()  { return gpio_get_level((gpio_num_t)pins_.irq) == 1; }

    /// Poll BUSY pin until LOW (radio ready). Blocking with timeout.
    void wait_busy();

    /// Hardware reset: RST LOW → delay → RST HIGH → delay 50ms.
    void hardware_reset();

    /// Compute RF frequency register value from MHz.
    /// frf = (freq_MHz * 1e6 * 2^18) / (XTAL_MHz * 1e6)
    static uint32_t compute_frf(float freq_mhz);

    /// Full 17-step LR2021 FLRC init sequence (from proven firmware).
    Lr2021Error init_sequence(const Lr2021Config& config);

    /// Initialize SPI bus + GPIO pins (called by init()).
    esp_err_t init_hardware();
};

#endif // ESP_PLATFORM / __has_include
