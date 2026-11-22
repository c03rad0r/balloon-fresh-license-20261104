/*
 * Capture the Zephyr fatal reason in noinit RAM before rebooting.
 *
 * The direct-FLRC bridge resets under sustained FIPS load. The modem crash log
 * does not catch a Zephyr fatal error or hard fault, so this hook stores the
 * reason and stacked PC/LR where the next boot can report them as a BR_EVT.
 */

#include <zephyr/arch/cpu.h>
#include <zephyr/fatal.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/reboot.h>

extern "C" {

__noinit volatile uint32_t seeed_fatal_magic;
__noinit volatile uint32_t seeed_fatal_reason;
__noinit volatile uint32_t seeed_fatal_pc;
__noinit volatile uint32_t seeed_fatal_lr;

void k_sys_fatal_error_handler(unsigned int reason,
                               const struct arch_esf* esf) {
    seeed_fatal_magic = 0x53454544u;  // 'SEED'
    seeed_fatal_reason = reason;
    seeed_fatal_pc = 0;
    seeed_fatal_lr = 0;
    if (esf != NULL) {
        seeed_fatal_pc = esf->basic.pc;
        seeed_fatal_lr = esf->basic.lr;
    }

    sys_reboot(SYS_REBOOT_COLD);
    for (;;) {
        k_sleep(K_FOREVER);
    }
}

}  // extern "C"
