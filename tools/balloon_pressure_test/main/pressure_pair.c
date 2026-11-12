#include "pressure_pair.h"
#include <math.h>
#include <stddef.h>
bool pp_evaluate(const pp_config *cfg, const pp_sample *internal,
                 const pp_sample *ambient, uint64_t now_ms,
                 double zero_offset_pa, pp_result *out) {
    if (!out) return false;
    out->raw_pa = out->corrected_pa = NAN;
    if (!cfg || !internal || !ambient || !isfinite(zero_offset_pa)) return false;
    if (!cfg->max_age_ms || !cfg->max_skew_ms ||
        !isfinite(cfg->min_abs_pa) || !isfinite(cfg->max_abs_pa) ||
        !isfinite(cfg->min_temp_c) || !isfinite(cfg->max_temp_c) ||
        cfg->min_abs_pa <= 0 || cfg->min_abs_pa >= cfg->max_abs_pa ||
        cfg->min_temp_c >= cfg->max_temp_c) return false;
    if (internal->address != 0x77 || ambient->address != 0x76) return false;
    const pp_sample *samples[] = {internal, ambient};
    for (size_t i = 0; i < 2; ++i) {
        const pp_sample *s = samples[i];
        if (!s->valid || !isfinite(s->abs_pa) || !isfinite(s->temp_c) ||
            s->abs_pa < cfg->min_abs_pa || s->abs_pa > cfg->max_abs_pa ||
            s->temp_c < cfg->min_temp_c || s->temp_c > cfg->max_temp_c ||
            s->timestamp_ms > now_ms || now_ms - s->timestamp_ms > cfg->max_age_ms)
            return false;
    }
    uint64_t t1 = internal->timestamp_ms, t2 = ambient->timestamp_ms;
    if ((t1 > t2 ? t1 - t2 : t2 - t1) > cfg->max_skew_ms) return false;
    double raw = internal->abs_pa - ambient->abs_pa;
    double corrected = raw - zero_offset_pa;
    if (!isfinite(raw) || !isfinite(corrected)) return false;
    out->raw_pa = raw;
    out->corrected_pa = corrected;
    return true;
}
