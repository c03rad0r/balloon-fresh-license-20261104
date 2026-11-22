#include "reset_diag.h"

#include <stddef.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/init.h>
#include <zephyr/kernel.h>
#include <zephyr/linker/section_tags.h>

#include <hal/nrf_reset.h>

/*
 * The record deliberately has C linkage so pyocd can locate it by symbol name
 * while the firmware is running or halted. It lives in .noinit, which the C
 * runtime does not clear, so it survives a warm reset.
 */
extern "C" {
__noinit seeed_boot_record_t seeed_boot_record;
}

namespace {

constexpr uint32_t kBootMagic = SEEED_BOOT_MAGIC;
constexpr uint32_t kFatalMagic = SEEED_FATAL_MAGIC;
constexpr uint32_t kRecordVersion = SEEED_BOOT_RECORD_VERSION;

uint32_t fnv1a(const uint8_t* data, size_t len) {
    uint32_t hash = 2166136261u;
    for (size_t i = 0; i < len; i++) {
        hash ^= data[i];
        hash *= 16777619u;
    }
    return hash;
}

uint32_t recordChecksum(const seeed_boot_record_t& record) {
    return fnv1a(reinterpret_cast<const uint8_t*>(&record),
                 offsetof(seeed_boot_record_t, checksum));
}

struct ResetBit {
    uint32_t bit;
    const char* name;
};

constexpr ResetBit kResetBits[] = {
    {1u << 0, "PIN"},        {1u << 1, "DOG0"},       {1u << 2, "DOG1"},
    {1u << 3, "CTRLAPSOFT"}, {1u << 4, "CTRLAPHARD"}, {1u << 5, "CTRLAPPIN"},
    {1u << 6, "SREQ"},       {1u << 7, "LOCKUP"},     {1u << 8, "OFF"},
    {1u << 9, "LPCOMP"},     {1u << 10, "DIF"},
};

void appendText(char* out, size_t cap, size_t* used, const char* text) {
    if (*used >= cap) {
        return;
    }
    size_t room = cap - *used - 1;
    size_t len = strnlen(text, room);
    memcpy(out + *used, text, len);
    *used += len;
    out[*used] = '\0';
}

void appendResetBits(char* out, size_t cap, size_t* used, uint32_t reason) {
    if (reason == 0) {
        appendText(out, cap, used, "none");
        return;
    }
    bool first = true;
    uint32_t remaining = reason;
    for (const ResetBit& entry : kResetBits) {
        if ((reason & entry.bit) == 0) {
            continue;
        }
        if (!first) {
            appendText(out, cap, used, "|");
        }
        appendText(out, cap, used, entry.name);
        first = false;
        remaining &= ~entry.bit;
    }
    if (remaining != 0 || first) {
        char hex[16];
        snprintf(hex, sizeof(hex), first ? "0x%08x" : "|0x%08x",
                 static_cast<unsigned>(remaining));
        appendText(out, cap, used, hex);
    }
}

}  // namespace

extern "C" int seeed_reset_diag_init(void) {
    uint32_t reason = nrf_reset_resetreas_get(NRF_RESET);
    nrf_reset_resetreas_clear(NRF_RESET, reason);

    bool valid = (seeed_boot_record.magic == kBootMagic) &&
                 (seeed_boot_record.version == kRecordVersion) &&
                 (seeed_boot_record.checksum == recordChecksum(seeed_boot_record));

    uint32_t previous_boots = valid ? seeed_boot_record.boot_count : 0;
    uint32_t fatal_magic = valid ? seeed_boot_record.fatal_magic : 0;
    uint32_t fatal_count = valid ? seeed_boot_record.fatal_count : 0;
    uint32_t fatal_reason = valid ? seeed_boot_record.fatal_reason : 0;
    uint32_t fatal_pc = valid ? seeed_boot_record.fatal_pc : 0;
    uint32_t fatal_lr = valid ? seeed_boot_record.fatal_lr : 0;
    uint32_t fatal_thread_id = valid ? seeed_boot_record.fatal_thread_id : 0;
    char fatal_thread[SEEED_THREAD_NAME_MAX] = {0};
    if (valid) {
        memcpy(fatal_thread, seeed_boot_record.fatal_thread,
               sizeof(fatal_thread) - 1);
    }

    memset(&seeed_boot_record, 0, sizeof(seeed_boot_record));
    seeed_boot_record.magic = kBootMagic;
    seeed_boot_record.version = kRecordVersion;
    seeed_boot_record.boot_count = previous_boots + 1;
    seeed_boot_record.resetreas = reason;
    seeed_boot_record.fatal_magic = fatal_magic;
    seeed_boot_record.fatal_count = fatal_count;
    seeed_boot_record.fatal_reason = fatal_reason;
    seeed_boot_record.fatal_pc = fatal_pc;
    seeed_boot_record.fatal_lr = fatal_lr;
    seeed_boot_record.fatal_thread_id = fatal_thread_id;
    memcpy(seeed_boot_record.fatal_thread, fatal_thread,
           sizeof(seeed_boot_record.fatal_thread));
    seeed_boot_record.last_uptime_ms = 0;
    seeed_boot_record.checksum = recordChecksum(seeed_boot_record);
    return 0;
}

SYS_INIT(seeed_reset_diag_init, PRE_KERNEL_1, 0);

extern "C" uint32_t seeed_boot_count(void) {
    return seeed_boot_record.boot_count;
}

extern "C" uint32_t seeed_reset_reason(void) {
    return seeed_boot_record.resetreas;
}

extern "C" int seeed_last_boot_was_reset(void) {
    return seeed_boot_record.boot_count > 1;
}

extern "C" void seeed_reset_diag_update_uptime(void) {
    seeed_boot_record.last_uptime_ms = k_uptime_get_32();
    seeed_boot_record.checksum = recordChecksum(seeed_boot_record);
}

extern "C" void seeed_reset_diag_format(char* out, size_t cap) {
    if (out == NULL || cap == 0) {
        return;
    }
    size_t used = 0;
    char head[48];
    snprintf(head, sizeof(head), "boot#%u rst=",
             static_cast<unsigned>(seeed_boot_record.boot_count));
    appendText(out, cap, &used, head);
    appendResetBits(out, cap, &used, seeed_boot_record.resetreas);
    char tail[48];
    snprintf(tail, sizeof(tail), " up=%ums",
             static_cast<unsigned>(seeed_boot_record.last_uptime_ms));
    appendText(out, cap, &used, tail);
}

extern "C" int seeed_reset_diag_fatal_format(char* out, size_t cap) {
    if (out == NULL || cap == 0) {
        return 0;
    }
    if (seeed_boot_record.fatal_magic != kFatalMagic) {
        out[0] = '\0';
        return 0;
    }
    snprintf(out, cap, "fatal#%u r=%u pc=%08x lr=%08x th=%s",
             static_cast<unsigned>(seeed_boot_record.fatal_count),
             static_cast<unsigned>(seeed_boot_record.fatal_reason),
             static_cast<unsigned>(seeed_boot_record.fatal_pc),
             static_cast<unsigned>(seeed_boot_record.fatal_lr),
             seeed_boot_record.fatal_thread[0] != '\0'
                 ? seeed_boot_record.fatal_thread
                 : "?");
    return 1;
}

extern "C" void seeed_reset_diag_fatal(unsigned int reason, uint32_t pc,
                                        uint32_t lr, uint32_t thread_id,
                                        const char* thread_name) {
    seeed_boot_record.fatal_magic = kFatalMagic;
    seeed_boot_record.fatal_count++;
    seeed_boot_record.fatal_reason = reason;
    seeed_boot_record.fatal_pc = pc;
    seeed_boot_record.fatal_lr = lr;
    seeed_boot_record.fatal_thread_id = thread_id;
    memset(seeed_boot_record.fatal_thread, 0,
           sizeof(seeed_boot_record.fatal_thread));
    if (thread_name != NULL) {
        strncpy(seeed_boot_record.fatal_thread, thread_name,
                sizeof(seeed_boot_record.fatal_thread) - 1);
    }
    seeed_boot_record.last_uptime_ms = k_uptime_get_32();
    seeed_boot_record.checksum = recordChecksum(seeed_boot_record);
}
