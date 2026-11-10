#ifndef BALLOON_MS5611_H
#define BALLOON_MS5611_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define MS5611_INTERNAL_ADDRESS 0x77
#define MS5611_AMBIENT_ADDRESS 0x76
#define MS5611_INVALID_PROM (-1001)
#define MS5611_NOT_READY (-1002)
#define MS5611_INVALID_ADC (-1003)
/* transfer: command-only when size=0, otherwise command + repeated-start read.
 * Return 0 on success, nonzero transport error otherwise; timeout in ms.
 * wait_ms MUST wait at least the requested elapsed duration. No globals. */
typedef struct {
    void *ctx;
    int (*transfer)(void *, uint8_t, uint8_t *, size_t, unsigned);
    void (*wait_ms)(void *, unsigned);
} ms5611_io_t;
typedef struct {
    ms5611_io_t io;
    uint16_t prom[8];
    bool ready;
} ms5611_t;
typedef struct { int32_t pressure_pa; int32_t temperature_centi_c; } ms5611_sample_t;
/* Reset and load complete PROM atomically; any failure clears readiness. */
int ms5611_read_prom(ms5611_t *dev);
/* OSR4096 acquisition; output untouched on failure, never a cached reading. */
int ms5611_read(ms5611_t *dev, ms5611_sample_t *sample);
#endif
