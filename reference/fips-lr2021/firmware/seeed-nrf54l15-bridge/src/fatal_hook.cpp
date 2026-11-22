/*
 * Capture a Zephyr fatal error in the persistent boot record before rebooting.
 *
 * HW_STACK_PROTECTION is enabled, so a stack overflow raises a fatal error and
 * reaches this handler rather than silently corrupting memory. The modem crash
 * log does not see Zephyr fatals, so the shared noinit record is the only place
 * that survives both paths.
 */

#include <zephyr/arch/cpu.h>
#include <zephyr/fatal.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/reboot.h>

#include "reset_diag.h"

extern "C" void k_sys_fatal_error_handler(unsigned int reason,
                                          const struct arch_esf* esf) {
    uint32_t pc = 0;
    uint32_t lr = 0;
    if (esf != NULL) {
        pc = esf->basic.pc;
        lr = esf->basic.lr;
    }

    k_tid_t thread = k_current_get();
    const char* name = NULL;
#if defined(CONFIG_THREAD_NAME)
    name = k_thread_name_get(thread);
#endif

    seeed_reset_diag_fatal(reason, pc, lr,
                           static_cast<uint32_t>(reinterpret_cast<uintptr_t>(thread)),
                           name);

    sys_reboot(SYS_REBOOT_COLD);
    for (;;) {
        k_sleep(K_FOREVER);
    }
}
