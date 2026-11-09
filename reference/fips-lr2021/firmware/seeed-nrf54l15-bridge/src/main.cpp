#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>

#include "bridge_core.h"

namespace {

const struct device* const kHostUart = DEVICE_DT_GET(DT_NODELABEL(uart20));
constexpr size_t kReadChunk = 512;
constexpr size_t kWriteCap = 4096;
constexpr int kTxTimeoutMs = 100;
constexpr int kStatPeriodMs = 5000;

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

    static seeed_bridge::LoopbackCore core;
    static uint8_t read_buf[kReadChunk];
    static uint8_t write_buf[kWriteCap];
    int64_t last_stat_ms = k_uptime_get();

    for (;;) {
        size_t read_len = 0;
        while (read_len < sizeof(read_buf)) {
            unsigned char byte = 0;
            if (uart_poll_in(kHostUart, &byte) != 0) {
                break;
            }
            read_buf[read_len++] = byte;
        }

        if (read_len > 0) {
            size_t out_len =
                core.process(read_buf, read_len, write_buf, sizeof(write_buf));
            if (out_len > 0) {
                (void)uart_tx(kHostUart, write_buf, out_len, kTxTimeoutMs);
            }
        }

        if (k_uptime_get() - last_stat_ms >= kStatPeriodMs) {
            size_t out_len = core.encodeStat(write_buf, sizeof(write_buf));
            if (out_len > 0) {
                (void)uart_tx(kHostUart, write_buf, out_len, kTxTimeoutMs);
            }
            last_stat_ms = k_uptime_get();
        }

        if (read_len == 0) {
            k_sleep(K_MSEC(1));
        }
    }
}
