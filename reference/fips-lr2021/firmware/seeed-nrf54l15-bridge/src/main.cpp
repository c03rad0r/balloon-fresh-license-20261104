#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/ring_buffer.h>

#include "bridge_core.h"

#if defined(CONFIG_SEEED_BRIDGE_FLRC)
#include "flrc_radio.h"
#endif

namespace {

const struct device* const kHostUart = DEVICE_DT_GET(DT_ALIAS(seeed_bridge_uart));
constexpr size_t kReadChunk = 512;
constexpr size_t kWriteCap = 4096;
constexpr int kStatPeriodMs = 5000;

RING_BUF_DECLARE(host_rx_ring, 4096);
RING_BUF_DECLARE(host_tx_ring, 8192);
seeed_bridge::BridgeCore core;

#if defined(CONFIG_SEEED_BRIDGE_FLRC)
void onRadioTxDone(void*) { core.noteTxDone(); }
void onRadioCrcError(void*) { core.noteCrcError(); }
void onRadioTxTimeout(void*) { core.noteTxTimeout(); }
void onRadioDrop(void*) { core.noteDrop(); }
#endif


void queue_host_bytes(const uint8_t* data, size_t len) {
    size_t sent = 0;
    while (sent < len) {
        uint32_t written =
            ring_buf_put(&host_tx_ring, data + sent, static_cast<uint32_t>(len - sent));
        sent += written;
        uart_irq_tx_enable(kHostUart);
        if (sent < len) {
            k_sleep(K_MSEC(1));
        }
    }
}

void host_uart_isr(const struct device* dev, void* user_data) {
    (void)user_data;
    if (!uart_irq_update(dev)) {
        return;
    }

    if (uart_irq_rx_ready(dev)) {
        while (uart_irq_rx_ready(dev)) {
            uint8_t chunk[64];
            int received = uart_fifo_read(dev, chunk, sizeof(chunk));
            if (received <= 0) {
                break;
            }
            (void)ring_buf_put(&host_rx_ring, chunk,
                               static_cast<uint32_t>(received));
        }
    }

    if (uart_irq_tx_ready(dev)) {
        static uint8_t pending = 0;
        static bool has_pending = false;

        if (has_pending) {
            if (uart_fifo_fill(dev, &pending, 1) != 1) {
                return;
            }
            has_pending = false;
        }

        while (uart_irq_tx_ready(dev)) {
            uint8_t byte = 0;
            if (ring_buf_get(&host_tx_ring, &byte, 1) != 1) {
                uart_irq_tx_disable(dev);
                break;
            }
            if (uart_fifo_fill(dev, &byte, 1) != 1) {
                pending = byte;
                has_pending = true;
                break;
            }
        }
    }
}

[[noreturn]] void fatal() {
    k_panic();
    for (;;) {
        k_sleep(K_FOREVER);
    }
}

}  // namespace

int main() {
    if (!device_is_ready(kHostUart)) {
        fatal();
    }

    struct uart_config config = {};
    config.baudrate = CONFIG_SEEED_BRIDGE_UART_BAUD;
    config.parity = UART_CFG_PARITY_NONE;
    config.stop_bits = UART_CFG_STOP_BITS_1;
    config.data_bits = UART_CFG_DATA_BITS_8;
    config.flow_ctrl = UART_CFG_FLOW_CTRL_NONE;
    if (uart_configure(kHostUart, &config) != 0) {
        fatal();
    }
    if (uart_irq_callback_user_data_set(kHostUart, host_uart_isr, NULL) != 0) {
        fatal();
    }
    uart_irq_rx_enable(kHostUart);

#if defined(CONFIG_SEEED_BRIDGE_FLRC)
    static seeed_bridge::RadioBackend radio_backend;
    if (seeed_bridge::flrcRadioInit(&radio_backend)) {
        radio_backend.on_tx_done = onRadioTxDone;
        radio_backend.on_crc_error = onRadioCrcError;
        radio_backend.on_tx_timeout = onRadioTxTimeout;
        radio_backend.on_drop = onRadioDrop;
        core.setRadio(&radio_backend);
    }
#endif

    static uint8_t read_buf[kReadChunk];
    static uint8_t write_buf[kWriteCap];
    int64_t last_stat_ms = k_uptime_get();

    for (;;) {
#if defined(CONFIG_SEEED_BRIDGE_FLRC)
        seeed_bridge::flrcRadioRunEngine();
        seeed_bridge::flrcRadioService();
        char event_text[80];
        while (seeed_bridge::flrcRadioPopEvent(event_text, sizeof(event_text))) {
            size_t event_len =
                core.encodeEvent(event_text, write_buf, sizeof(write_buf));
            if (event_len > 0) {
                queue_host_bytes(write_buf, event_len);
            }
        }
        seeed_bridge::RadioRxPacket packet;
        while (seeed_bridge::flrcRadioPop(&packet)) {
            size_t rx_len = core.encodeRx(packet.rssi_dbm, packet.snr_db,
                                          packet.data, packet.len, write_buf,
                                          sizeof(write_buf));
            if (rx_len > 0) {
                queue_host_bytes(write_buf, rx_len);
            }
        }
#endif

        uint32_t read_len =
            ring_buf_get(&host_rx_ring, read_buf, sizeof(read_buf));

        if (read_len > 0) {
            size_t out_len =
                core.process(read_buf, read_len, write_buf, sizeof(write_buf));
            if (out_len > 0) {
                queue_host_bytes(write_buf, out_len);
            }
        }

        if (k_uptime_get() - last_stat_ms >= kStatPeriodMs) {
            size_t out_len = core.encodeStat(write_buf, sizeof(write_buf));
            if (out_len > 0) {
                queue_host_bytes(write_buf, out_len);
            }
            last_stat_ms = k_uptime_get();
        }

        if (read_len == 0) {
            k_sleep(K_MSEC(1));
        } else {
#if defined(CONFIG_SEEED_BRIDGE_FLRC)
            // Host TX frames were queued during process(); start them now.
            seeed_bridge::flrcRadioService();
            k_yield();
#endif
        }
    }
}
