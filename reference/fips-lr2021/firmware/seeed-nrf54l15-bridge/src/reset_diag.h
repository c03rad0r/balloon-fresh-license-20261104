#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SEEED_BOOT_MAGIC 0x53454544u   /* 'SEED' */
#define SEEED_FATAL_MAGIC 0x4641544cu  /* 'FATL' */
#define SEEED_BOOT_RECORD_VERSION 1u
#define SEEED_THREAD_NAME_MAX 16

/*
 * Survives a warm reset in .noinit. A power cycle loses it, which is why the
 * magic is validated and a lost record is reported rather than trusted.
 *
 * resetreas is the raw nRF RESETREAS value captured at the very start of this
 * boot, before any driver can clear it. The decoded names are produced by
 * seeed_reset_diag_format().
 */
typedef struct {
    uint32_t magic;
    uint32_t version;
    uint32_t boot_count;
    uint32_t resetreas;       /* reason for THIS boot */
    uint32_t fatal_magic;
    uint32_t fatal_count;
    uint32_t fatal_reason;
    uint32_t fatal_pc;
    uint32_t fatal_lr;
    uint32_t fatal_thread_id;
    char fatal_thread[SEEED_THREAD_NAME_MAX];
    uint32_t last_uptime_ms;
    uint32_t checksum;
} seeed_boot_record_t;

extern seeed_boot_record_t seeed_boot_record;

/* Runs at PRE_KERNEL_1, before the reset cause can be consumed elsewhere. */
int seeed_reset_diag_init(void);

uint32_t seeed_boot_count(void);
uint32_t seeed_reset_reason(void);
int seeed_last_boot_was_reset(void);

/* Refresh the recorded uptime/checksum so a later crash shows how far it got. */
void seeed_reset_diag_update_uptime(void);

/* "boot#3 rst=SREQ up=12345ms" — always NUL-terminated. */
void seeed_reset_diag_format(char* out, size_t cap);

/* "fatal r=3 pc=0000abcd lr=0000ef01 th=main" when one was recorded. */
int seeed_reset_diag_fatal_format(char* out, size_t cap);

/* Called from the fatal handler immediately before the reboot. */
void seeed_reset_diag_fatal(unsigned int reason, uint32_t pc, uint32_t lr,
                            uint32_t thread_id, const char* thread_name);

#ifdef __cplusplus
}
#endif
