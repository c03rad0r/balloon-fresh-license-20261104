#pragma once

#include <stdint.h>

#include "bridge_core.h"

namespace seeed_bridge {

struct RadioRxPacket {
    int16_t rssi_dbm;
    int8_t snr_db;
    uint16_t len;
    uint8_t data[kMaxRadioPayload];
};

// Bring up the LR2021 RAC/FLRC backend. Returns false when the radio cannot be
// opened. The bridge stays in loopback when this fails.
bool flrcRadioInit(RadioBackend* backend);

// Service RAC timers and radio IRQs. Call from the main loop.
void flrcRadioRunEngine();

// Start or re-arm RX/TX from main-loop context. Call after flrcRadioRunEngine.
void flrcRadioService();

// Non-blocking pop of one received packet. Call only from the main thread.
bool flrcRadioPop(RadioRxPacket* packet);

// Non-blocking pop of one diagnostic event string.
bool flrcRadioPopEvent(char* text, size_t cap);

// Human-readable diagnostics for the BR_DIAG request. Returns the number of
// bytes written, or 0 when unavailable.
size_t flrcRadioDiagnostics(void* context, char* out, size_t cap);

}  // namespace seeed_bridge
