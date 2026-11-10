#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "pressure_pair.h"
int main(void) {
    pp_config cfg = {100, 20, 90000, 110000, 0, 40};
    pp_sample in = {0x76, 103000, 22, 990, true};
    pp_sample amb = {0x77, 100000, 22, 995, true};
    pp_result out;
    assert(pp_evaluate(&cfg, &in, &amb, 1000, 25, &out));
    assert(out.raw_pa == 3000 && out.corrected_pa == 2975);
    in.valid = false;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 25, &out));
    assert(isnan(out.raw_pa) && isnan(out.corrected_pa));
    in.valid = true; amb.address = in.address;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 25, &out));
    amb.address = 0x77; amb.timestamp_ms = 899;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 25, &out));
    amb.timestamp_ms = 1001;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 25, &out));
    amb.timestamp_ms = 950;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 25, &out));
    amb.timestamp_ms = 995; in.abs_pa = NAN;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 25, &out));
    in.abs_pa = 110001;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 25, &out));
    in.abs_pa = 103000; in.temp_c = INFINITY;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 25, &out));
    in.temp_c = 22;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, NAN, &out));
    cfg.max_age_ms = 0;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 25, &out));
    cfg.max_age_ms = 100;
    assert(!pp_evaluate(NULL, &in, &amb, 1000, 0, &out));
    assert(!pp_evaluate(&cfg, NULL, &amb, 1000, 0, &out));
    assert(!pp_evaluate(&cfg, &in, NULL, 1000, 0, &out));
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 0, NULL));
    amb.valid = false;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 0, &out));
    amb.valid = true;
    in.abs_pa = 99000;
    assert(pp_evaluate(&cfg, &in, &amb, 1000, 25, &out));
    assert(out.raw_pa == -1000 && out.corrected_pa == -1025);
    in.timestamp_ms = 900; amb.timestamp_ms = 920;
    assert(pp_evaluate(&cfg, &in, &amb, 1000, 0, &out));
    in.timestamp_ms = 899;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 0, &out));
    in.timestamp_ms = 900; amb.timestamp_ms = 921;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 0, &out));
    /* Each failure must overwrite an earlier plausible result, on either role. */
    for (int role = 0; role < 2; ++role) {
        for (int fault = 0; fault < 10; ++fault) {
            in = (pp_sample){0x76, 103000, 22, 990, true};
            amb = (pp_sample){0x77, 100000, 22, 995, true};
            pp_sample *s = role ? &amb : &in;
            switch (fault) {
                case 0: s->valid = false; break;
                case 1: s->abs_pa = NAN; break;
                case 2: s->abs_pa = INFINITY; break;
                case 3: s->abs_pa = 89999; break;
                case 4: s->temp_c = NAN; break;
                case 5: s->temp_c = -1; break;
                case 6: s->temp_c = 41; break;
                case 7: s->timestamp_ms = 899; break;
                case 8: s->timestamp_ms = 1001; break;
                case 9: s->address = role ? 0x76 : 0x77; break;
            }
            out = (pp_result){123, 123};
            assert(!pp_evaluate(&cfg, &in, &amb, 1000, 0, &out));
            assert(isnan(out.raw_pa) && isnan(out.corrected_pa));
        }
    }
    in = (pp_sample){0x76, 90000, 0, 990, true};
    amb = (pp_sample){0x77, 110000, 40, 995, true};
    assert(pp_evaluate(&cfg, &in, &amb, 1000, -25, &out));
    assert(out.raw_pa == -20000 && out.corrected_pa == -19975);
    assert(in.abs_pa == 90000 && amb.abs_pa == 110000);
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, INFINITY, &out));
    cfg.min_abs_pa = NAN;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 0, &out));
    cfg.min_abs_pa = cfg.max_abs_pa;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 0, &out));
    cfg.min_abs_pa = 90000; cfg.max_skew_ms = 0;
    assert(!pp_evaluate(&cfg, &in, &amb, 1000, 0, &out));
    puts("pressure pair: signed Pa, bounds, nulls, validity, identity and freshness checks passed");
    puts("pressure pair: 20 per-role poison cases, boundary and offset checks passed");
    return 0;
}
