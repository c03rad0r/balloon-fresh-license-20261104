#ifndef PRESSURE_PAIR_H
#define PRESSURE_PAIR_H
#include <stdbool.h>
#include <stdint.h>
/* Caller supplies independently justified fixture bounds, NOT balloon limits.
 * Addresses denote roles on one bus: internal 0x76, ambient 0x77.
 * Acquisition must verify actual device type/PROM separately.
 * Offset is externally calibrated; this stateless module cannot re-zero or
 * enforce immutability between calls. Caller must freeze it for each run.
 * raw_pa = internal.abs_pa - ambient.abs_pa; corrected_pa = raw_pa - offset.
 * Caller retains/logs both absolute readings; result contains differentials.
 * Timestamps and now_ms share one monotonic clock. Bounds are inclusive;
 * max_age_ms and max_skew_ms must both be nonzero. Failure returns false and
 * writes NaN to both outputs when out is non-NULL.
 */
typedef struct {
    uint64_t max_age_ms, max_skew_ms;
    double min_abs_pa, max_abs_pa, min_temp_c, max_temp_c;
} pp_config;
typedef struct {
    uint8_t address;
    double abs_pa, temp_c;
    uint64_t timestamp_ms;
    bool valid;
} pp_sample;
typedef struct { double raw_pa, corrected_pa; } pp_result;
bool pp_evaluate(const pp_config *, const pp_sample *internal,
                 const pp_sample *ambient, uint64_t now_ms,
                 double zero_offset_pa, pp_result *);
#endif
