#include "flrc_radio.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/kernel.h>
#include <zephyr/lorawan_lbm/lorawan_hal_init.h>

#include "smtc_rac_api.h"
#include "smtc_sw_platform_helper.h"
#include "lr20xx_system.h"
#include <hal/nrf_reset.h>

extern "C" {
extern volatile uint32_t seeed_fatal_magic;
extern volatile uint32_t seeed_fatal_reason;
extern volatile uint32_t seeed_fatal_pc;
extern volatile uint32_t seeed_fatal_lr;
bool smtc_modem_hal_crashlog_get_status(void);
void smtc_modem_hal_crashlog_restore(uint8_t* crash_string, uint8_t* crash_string_length);
void smtc_modem_hal_crashlog_set_status(bool available);
}

namespace seeed_bridge {
namespace {

constexpr uint16_t kMaxPayload = kMaxRadioPayload;
constexpr uint8_t kTxQueueDepth = 16;
constexpr uint8_t kRxQueueDepth = 16;
constexpr uint32_t kRxTimeoutMs = 100;

// RAC transaction states. Only one owner may submit at a time.
constexpr atomic_val_t kStateIdle = 0;
constexpr atomic_val_t kStateRx = 1;
constexpr atomic_val_t kStateTx = 2;

struct TxPacket {
    uint16_t len;
    uint8_t data[kMaxPayload];
};

struct RadioState {
    uint8_t access_id;
    smtc_rac_context_t* ctx;
    RadioBackend* backend;
    uint8_t tx_payload[kMaxPayload];
    uint8_t rx_payload[kMaxPayload];
    uint8_t sync_word[4];
    uint8_t zero_sync_word[4];
    uint16_t chip_id;
    uint32_t last_tx_ms;
    char crash[256];
    bool crash_pending;
    bool initialized;
    bool configured;
};

RadioState g;
atomic_t g_state = ATOMIC_INIT(kStateIdle);
atomic_t g_rx_enabled = ATOMIC_INIT(0);

K_MSGQ_DEFINE(g_tx_queue, sizeof(TxPacket), kTxQueueDepth, 4);
K_MSGQ_DEFINE(g_rx_queue, sizeof(RadioRxPacket), kRxQueueDepth, 4);

struct EventText {
    char text[80];
};
K_MSGQ_DEFINE(g_event_queue, sizeof(EventText), 16, 4);

// Diagnostic events are rare (configuration or error paths) and are surfaced
// to the host as BR_EVT frames. They are never emitted per packet.
void emitEvent(const char* fmt, ...) {
    EventText event;
    va_list args;
    va_start(args, fmt);
    vsnprintf(event.text, sizeof(event.text), fmt, args);
    va_end(args);
    if (k_msgq_put(&g_event_queue, &event, K_NO_WAIT) != 0) {
        EventText discard;
        (void)k_msgq_get(&g_event_queue, &discard, K_NO_WAIT);
        (void)k_msgq_put(&g_event_queue, &event, K_NO_WAIT);
    }
}

// The USP engine is not run in a separate thread. Its mutex does not exist in
// that configuration, so these are no-ops until a future threaded variant.
void racLock() {
#if defined(CONFIG_USP_THREADS_MUTEXES)
    k_mutex_lock(&rac_api_mutex, K_FOREVER);
#endif
}

void racUnlock() {
#if defined(CONFIG_USP_THREADS_MUTEXES)
    k_mutex_unlock(&rac_api_mutex);
#endif
}

void notifyDrop() {
    if (g.backend != NULL && g.backend->on_drop != NULL) {
        g.backend->on_drop(g.backend->context);
    }
}

void notifyTxDone() {
    if (g.backend != NULL && g.backend->on_tx_done != NULL) {
        g.backend->on_tx_done(g.backend->context);
    }
}

void notifyCrcError() {
    if (g.backend != NULL && g.backend->on_crc_error != NULL) {
        g.backend->on_crc_error(g.backend->context);
    }
}

void notifyTxTimeout() {
    if (g.backend != NULL && g.backend->on_tx_timeout != NULL) {
        g.backend->on_tx_timeout(g.backend->context);
    }
}

void startRx();
void startTx();

void startRx() {
    if (g.ctx == NULL) {
        return;
    }
    if (!atomic_cas(&g_state, kStateIdle, kStateRx)) {
        return;
    }

    racLock();
    g.ctx->radio_params.flrc.is_tx = false;
    g.ctx->radio_params.flrc.tx_size = 0;
    g.ctx->radio_params.flrc.max_rx_size = kMaxPayload;
    g.ctx->scheduler_config.start_time_ms = k_uptime_get_32();
    g.ctx->scheduler_config.scheduling = SMTC_RAC_ASAP_TRANSACTION;
    smtc_rac_return_code_t rc =
        smtc_rac_submit_radio_transaction(g.access_id);
    racUnlock();

    if (rc != SMTC_RAC_SUCCESS) {
        atomic_set(&g_state, kStateIdle);
        emitEvent("rx submit rc=%d", rc);
        notifyDrop();
    }
}

void startTx() {
    if (g.ctx == NULL) {
        return;
    }
    if (!atomic_cas(&g_state, kStateIdle, kStateTx)) {
        return;
    }

    // Give the peer time to re-arm its RX transaction between back-to-back
    // fragments. Without this guard the second fragment of a multi-frame link
    // message can start before the receiver is listening again.
    if (g.last_tx_ms != 0) {
        uint32_t elapsed = k_uptime_get_32() - g.last_tx_ms;
        if (elapsed < 2) {
            k_busy_wait((2 - elapsed) * 1000);
        }
    }

    TxPacket packet;
    if (k_msgq_get(&g_tx_queue, &packet, K_NO_WAIT) != 0) {
        atomic_set(&g_state, kStateIdle);
        return;
    }

    racLock();
    memcpy(g.tx_payload, packet.data, packet.len);
    g.ctx->radio_params.flrc.is_tx = true;
    g.ctx->radio_params.flrc.tx_size = packet.len;
    g.ctx->scheduler_config.start_time_ms = k_uptime_get_32();
    g.ctx->scheduler_config.scheduling = SMTC_RAC_ASAP_TRANSACTION;
    smtc_rac_return_code_t rc =
        smtc_rac_submit_radio_transaction(g.access_id);
    racUnlock();

    if (rc != SMTC_RAC_SUCCESS) {
        atomic_set(&g_state, kStateIdle);
        emitEvent("tx submit rc=%d len=%u", rc, packet.len);
        notifyTxTimeout();
    }
}

void radioCallback(rp_status_t status) {
    switch (status) {
    case RP_STATUS_RX_PACKET: {
        RadioRxPacket packet;
        packet.rssi_dbm = g.ctx->smtc_rac_data_result.rssi_result;
        packet.snr_db = g.ctx->smtc_rac_data_result.snr_result;
        uint16_t len = g.ctx->smtc_rac_data_result.rx_size;
        if (len > kMaxPayload) {
            len = kMaxPayload;
        }
        packet.len = len;
        memcpy(packet.data, g.rx_payload, len);
        if (k_msgq_put(&g_rx_queue, &packet, K_NO_WAIT) != 0) {
            emitEvent("rx queue full");
            notifyDrop();
        }
        break;
    }
    case RP_STATUS_RX_CRC_ERROR:
        notifyCrcError();
        break;
    case RP_STATUS_TX_DONE:
        g.last_tx_ms = k_uptime_get_32();
        notifyTxDone();
        break;
    case RP_STATUS_RX_TIMEOUT:
    case RP_STATUS_TASK_ABORTED:
        break;
    default:
        emitEvent("radio status=%d", status);
        break;
    }

    // Re-arm immediately from the RAC callback, before the main loop spends
    // milliseconds writing the received frame to the 1 Mbaud host UART. This is
    // the vendor sample's supported completion-callback pattern.
    atomic_set(&g_state, kStateIdle);
    if (atomic_get(&g_rx_enabled) != 0) {
        if (k_msgq_num_used_get(&g_tx_queue) > 0) {
            startTx();
        } else {
            startRx();
        }
    }
}

bool mapBitrate(uint16_t kbps, ral_flrc_raw_bit_rate_t* out) {
    switch (kbps) {
    case 2600:
        *out = RAL_FLRC_RAW_BIT_RATE_2_600_MBPS;
        return true;
    case 2080:
        *out = RAL_FLRC_RAW_BIT_RATE_2_080_MBPS;
        return true;
    case 1300:
        *out = RAL_FLRC_RAW_BIT_RATE_1_300_MBPS;
        return true;
    case 650:
        *out = RAL_FLRC_RAW_BIT_RATE_0_650_MBPS;
        return true;
    case 325:
        *out = RAL_FLRC_RAW_BIT_RATE_0_325_MBPS;
        return true;
    default:
        return false;
    }
}

bool validateBand(uint8_t band, uint32_t frequency_hz) {
    switch (band) {
    case 0:  // eu868
    case 1:  // eu868-high
        return frequency_hz >= 863000000u && frequency_hz <= 870000000u;
    case 2:  // us915
    case 3:  // us915-robust
        return frequency_hz >= 902000000u && frequency_hz <= 928000000u;
    case 4:  // eu2400
    case 5:  // us2400
        return frequency_hz >= 2400000000u && frequency_hz <= 2500000000u;
    case 6:  // custom
        return frequency_hz >= 150000000u && frequency_hz <= 2500000000u;
    default:
        return false;
    }
}

bool radioConfigure(void* context, const CfgPayload& cfg, uint8_t* status) {
    (void)context;
    if (!g.initialized || g.ctx == NULL) {
        *status = 1;
        return false;
    }
    if (cfg.relay) {
        *status = 5;  // relay not implemented
        return false;
    }
    if (cfg.radio_payload < 32 || cfg.radio_payload > kMaxPayload) {
        *status = 4;  // payload length not supported by this radio buffer
        return false;
    }
    if (!validateBand(cfg.band, cfg.frequency_hz)) {
        *status = 2;
        emitEvent("cfg reject band=%u freq=%u", cfg.band, cfg.frequency_hz);
        return false;
    }
    if (cfg.sub_ghz != (cfg.frequency_hz < 1000000000u)) {
        *status = 2;
        return false;
    }
    if (cfg.tx_power_dbm < -18 || cfg.tx_power_dbm > 22) {
        *status = 2;
        emitEvent("cfg reject power=%d", cfg.tx_power_dbm);
        return false;
    }

    ral_flrc_raw_bit_rate_t bitrate;
    if (!mapBitrate(cfg.bitrate_kbps, &bitrate)) {
        *status = 2;
        emitEvent("cfg reject rate=%u", cfg.bitrate_kbps);
        return false;
    }

    // Stop continuous RX before touching shared radio parameters.
    atomic_set(&g_rx_enabled, 0);
    racLock();
    (void)smtc_rac_abort_radio_submit(g.access_id);

    memcpy(g.sync_word, cfg.sync_word, sizeof(g.sync_word));
    g.ctx->modulation_type = SMTC_RAC_MODULATION_FLRC;
    g.ctx->radio_params.flrc.is_tx = false;
    g.ctx->radio_params.flrc.tx_size = 0;
    g.ctx->radio_params.flrc.max_rx_size = cfg.radio_payload;
    g.ctx->radio_params.flrc.frequency_in_hz = cfg.frequency_hz;
    g.ctx->radio_params.flrc.rx_frequency_offset_in_hz = 0;
    g.ctx->radio_params.flrc.tx_power_in_dbm = cfg.tx_power_dbm;
    g.ctx->radio_params.flrc.raw_bit_rate = bitrate;
    g.ctx->radio_params.flrc.cr = RAL_FLRC_CR_3_4;
    g.ctx->radio_params.flrc.pulse_shape = RAL_FLRC_PULSE_SHAPE_BT_05;
    g.ctx->radio_params.flrc.preamble_len = RAL_FLRC_PREAMBLE_LENGTH_32_BITS;
    g.ctx->radio_params.flrc.sync_word_len =
        RAL_FLRC_SYNCWORD_LENGTH_4_BYTES;
    g.ctx->radio_params.flrc.tx_syncword_index = RAL_FLRC_TX_SYNCWORD_1;
    g.ctx->radio_params.flrc.match_sync_word =
        RAL_FLRC_RX_MATCH_SYNCWORD_1;
    g.ctx->radio_params.flrc.pld_is_fix = false;
    g.ctx->radio_params.flrc.crc_type = RAL_FLRC_CRC_2_BYTES;
    g.ctx->radio_params.flrc.crc_seed = 0;
    g.ctx->radio_params.flrc.crc_polynomial = 0;
    g.ctx->radio_params.flrc.rx_timeout_ms = kRxTimeoutMs;
    g.ctx->radio_params.flrc.sync_word[0] = g.sync_word;
    g.ctx->radio_params.flrc.sync_word[1] = g.zero_sync_word;
    g.ctx->radio_params.flrc.sync_word[2] = g.zero_sync_word;
    g.ctx->scheduler_config.callback_post_radio_transaction = radioCallback;
    g.ctx->scheduler_config.callback_pre_radio_transaction = NULL;
    g.ctx->scheduler_config.scheduling = SMTC_RAC_ASAP_TRANSACTION;
    g.ctx->keep_radio_awake = true;

    g.configured = true;
    racUnlock();

    atomic_set(&g_state, kStateIdle);
    atomic_set(&g_rx_enabled, 1);
    startRx();

    *status = 0;
    emitEvent("cfg ok freq=%u rate=%u pwr=%d payload=%u",
              cfg.frequency_hz, cfg.bitrate_kbps, cfg.tx_power_dbm,
              cfg.radio_payload);
    return true;
}

bool radioSend(void* context, const uint8_t* data, uint16_t len) {
    (void)context;
    if (!g.configured || data == NULL || len == 0 || len > kMaxPayload) {
        return false;
    }

    TxPacket packet;
    packet.len = len;
    memcpy(packet.data, data, len);
    if (k_msgq_put(&g_tx_queue, &packet, K_NO_WAIT) != 0) {
        emitEvent("tx queue full");
        return false;
    }
    return true;
}

uint16_t radioChipId(void* context) {
    (void)context;
    if (g.crash_pending) {
        g.crash_pending = false;
        emitEvent("crash: %s", g.crash);
    }
    return g.chip_id;
}

uint16_t radioCapabilities(void* context) {
    (void)context;
    return g.initialized ? kCapabilitiesFlrc : kCapabilitiesLoopback;
}

}  // namespace

bool flrcRadioInit(RadioBackend* backend) {
    if (backend == NULL) {
        return false;
    }

    SMTC_SW_PLATFORM_INIT();
    SMTC_SW_PLATFORM_VOID(smtc_rac_init());

    racLock();
    uint8_t access_id = smtc_rac_open_radio(RAC_HIGH_PRIORITY);
    racUnlock();
    if (access_id == RAC_INVALID_RADIO_ID) {
        return false;
    }
    smtc_rac_context_t* ctx = smtc_rac_get_context(access_id);
    if (ctx == NULL) {
        return false;
    }

    g.access_id = access_id;
    g.ctx = ctx;
    g.backend = backend;
    g.initialized = true;
    g.configured = false;
    g.chip_id = 0;
    g.last_tx_ms = 0;
    g.crash[0] = '\0';
    g.crash_pending = false;

    uint32_t resetreas = nrf_reset_resetreas_get(NRF_RESET);
    nrf_reset_resetreas_clear(NRF_RESET, resetreas);
    if (resetreas != 0) {
        snprintf(g.crash, sizeof(g.crash), "resetreas=0x%08x",
                 (unsigned)resetreas);
        g.crash_pending = true;
    }

    if (seeed_fatal_magic == 0x53454544u) {
        seeed_fatal_magic = 0;
        snprintf(g.crash, sizeof(g.crash),
                 "fatal reason=%u pc=%08x lr=%08x",
                 (unsigned)seeed_fatal_reason, (unsigned)seeed_fatal_pc,
                 (unsigned)seeed_fatal_lr);
        g.crash_pending = true;
    } else if (smtc_modem_hal_crashlog_get_status()) {
        uint8_t crash_len = 0;
        smtc_modem_hal_crashlog_restore(
            reinterpret_cast<uint8_t*>(g.crash), &crash_len);
        if (crash_len >= sizeof(g.crash)) {
            crash_len = sizeof(g.crash) - 1;
        }
        g.crash[crash_len] = '\0';
        g.crash_pending = true;
        smtc_modem_hal_crashlog_set_status(false);
    }

    ctx->modulation_type = SMTC_RAC_MODULATION_FLRC;
    ctx->smtc_rac_data_buffer_setup.tx_payload_buffer = g.tx_payload;
    ctx->smtc_rac_data_buffer_setup.size_of_tx_payload_buffer =
        sizeof(g.tx_payload);
    ctx->smtc_rac_data_buffer_setup.rx_payload_buffer = g.rx_payload;
    ctx->smtc_rac_data_buffer_setup.size_of_rx_payload_buffer =
        sizeof(g.rx_payload);
    ctx->radio_params.flrc.max_rx_size = kMaxPayload;
    ctx->scheduler_config.callback_post_radio_transaction = radioCallback;
    ctx->scheduler_config.callback_pre_radio_transaction = NULL;
    ctx->scheduler_config.scheduling = SMTC_RAC_ASAP_TRANSACTION;
    ctx->keep_radio_awake = true;

    void* driver_context = smtc_rac_get_radio_driver_context();
    if (driver_context != NULL) {
        lr20xx_system_version_t version;
        racLock();
        lr20xx_status_t rc = lr20xx_system_get_version(driver_context, &version);
        racUnlock();
        if (rc == LR20XX_STATUS_OK) {
            g.chip_id = (static_cast<uint16_t>(version.major) << 8) |
                        version.minor;
        }
    }

    backend->context = &g;
    backend->configure = radioConfigure;
    backend->send = radioSend;
    backend->chip_id = radioChipId;
    backend->capabilities = radioCapabilities;
    backend->on_tx_done = NULL;
    backend->on_crc_error = NULL;
    backend->on_tx_timeout = NULL;
    backend->on_drop = NULL;

    atomic_set(&g_state, kStateIdle);
    atomic_set(&g_rx_enabled, 0);
    return true;
}

void flrcRadioRunEngine() {
    if (g.initialized) {
        smtc_rac_run_engine();
    }
}

void flrcRadioService() {
    if (!g.initialized || atomic_get(&g_rx_enabled) == 0) {
        return;
    }

    atomic_val_t state = atomic_get(&g_state);
    if (state == kStateIdle) {
        if (k_msgq_num_used_get(&g_tx_queue) > 0) {
            startTx();
        } else {
            startRx();
        }
    } else if (state == kStateRx && k_msgq_num_used_get(&g_tx_queue) > 0) {
        // Interrupt continuous RX so the completion callback can hand the radio
        // to the pending transmit. Only abort while the radio is still in RX,
        // never against a TX started concurrently.
        racLock();
        if (atomic_get(&g_state) == kStateRx) {
            (void)smtc_rac_abort_radio_submit(g.access_id);
        }
        racUnlock();
    }
}

bool flrcRadioPop(RadioRxPacket* packet) {
    if (packet == NULL) {
        return false;
    }
    return k_msgq_get(&g_rx_queue, packet, K_NO_WAIT) == 0;
}

bool flrcRadioPopEvent(char* text, size_t cap) {
    if (text == NULL || cap == 0) {
        return false;
    }
    EventText event;
    if (k_msgq_get(&g_event_queue, &event, K_NO_WAIT) != 0) {
        return false;
    }
    size_t len = strnlen(event.text, sizeof(event.text));
    if (len >= cap) {
        len = cap - 1;
    }
    memcpy(text, event.text, len);
    text[len] = '\0';
    return true;
}

}  // namespace seeed_bridge
