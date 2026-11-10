/* Scripted bus, not silicon. Datasheet coefficients and ADC example. */
#include "ms5611.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef struct {
    uint16_t prom[8];
    unsigned step, fail_at, waits;
    uint32_t d1, d2;
    int error;
} fake_t;
static int transfer(void *ctx, uint8_t cmd, uint8_t *out, size_t n, unsigned timeout) {
    fake_t *f = ctx;
    unsigned step = f->step++;
    assert(timeout == 100);
    if (step == f->fail_at) return f->error;
    if (step == 0) { assert(cmd == 0x1e && n == 0); return 0; }
    if (step <= 8) {
        assert(cmd == 0xa0 + 2*(step-1) && n == 2);
        out[0] = f->prom[step-1] >> 8; out[1] = f->prom[step-1]; return 0;
    }
    unsigned phase = (step-9)%4;
    if (phase == 0 || phase == 2) {
        assert(cmd == (phase == 0 ? 0x48 : 0x58) && n == 0); return 0;
    }
    assert(cmd == 0 && n == 3);
    uint32_t raw = phase == 1 ? f->d1 : f->d2;
    out[0] = raw >> 16; out[1] = raw >> 8; out[2] = raw; return 0;
}
static void wait_ms(void *ctx, unsigned ms) {
    fake_t *f = ctx;
    assert(ms == (f->waits == 0 ? 3 : 10)); ++f->waits;
}
static fake_t fixture(void) {
    /* CRC=0 independently precomputed for these full eight words. */
    fake_t f = {.prom={0,40127,36924,23317,23282,33464,28312,0},
                .d1=9085466, .d2=8569150, .fail_at=~0u, .error=-42};
    return f;
}
static ms5611_t device(fake_t *f) {
    ms5611_t d = {.io={.ctx=f,.transfer=transfer,.wait_ms=wait_ms}}; return d;
}
int main(void) {
    fake_t a=fixture(), b=fixture(); ms5611_t da=device(&a), db=device(&b);
    assert(ms5611_read_prom(&da)==0 && da.ready);
    assert(memcmp(da.prom,a.prom,sizeof a.prom)==0);
    b.prom[1]=40128; b.prom[7]=11; /* independently computed nonzero CRC */
    assert(ms5611_read_prom(&db)==0 && db.ready);
    assert(da.prom[1]==40127 && db.prom[1]==40128);
    ms5611_sample_t s={.pressure_pa=-123,.temperature_centi_c=-456};
    assert(ms5611_read(&da,&s)==0);
    assert(s.pressure_pa==100009 && s.temperature_centi_c==2007);
    /* Different calibration and ADC must not cross-contaminate instances. */
    b.d1=9000000;
    assert(ms5611_read(&db,&s)==0 && s.pressure_pa!=100009);
    assert(ms5611_read(&da,&s)==0 && s.pressure_pa==100009);
    /* Every transport phase fails closed, incl missing ACK and timeout. */
    for (unsigned step=0;step<13;step++) {
        for (int e=-1;e>=-2;e--) {
            fake_t f=fixture(); f.fail_at=step; f.error=e; ms5611_t d=device(&f);
            int r=ms5611_read_prom(&d);
            s=(ms5611_sample_t){-123,-456};
            if(step<9) { assert(r==e && !d.ready); assert(ms5611_read(&d,&s)!=0); }
            else { assert(r==0); assert(ms5611_read(&d,&s)==e); }
            assert(s.pressure_pa==-123 && s.temperature_centi_c==-456);
        }
    }
    /* Zero/ones/wrong-device PROM and all individual coefficient sentinels. */
    for(unsigned i=0;i<8;i++) {
        fake_t f=fixture(); f.prom[i]^=0x100; ms5611_t d=device(&f);
        assert(ms5611_read_prom(&d)==MS5611_INVALID_PROM && !d.ready);
    }
    for(unsigned i=1;i<=6;i++) for(unsigned v=0;v<2;v++) {
        fake_t f=fixture(); f.prom[i]=v?65535:0; ms5611_t d=device(&f);
        assert(ms5611_read_prom(&d)==MS5611_INVALID_PROM && !d.ready);
    }
    for(unsigned v=0;v<2;v++) {
        fake_t f=fixture(); memset(f.prom,v?255:0,sizeof f.prom); ms5611_t d=device(&f);
        assert(ms5611_read_prom(&d)==MS5611_INVALID_PROM && !d.ready);
    }
    /* A failed reinitialization invalidates previously valid calibration. */
    a.step=0; a.fail_at=2; a.waits=0;
    assert(ms5611_read_prom(&da)!=0 && !da.ready);
    /* Independent Decimal evaluation of the datasheet second-order formulas;
     * allow <=2 integer units for intermediate truncation, not physical accuracy. */
    const uint32_t cold_d2[]={8000000,7500000};
    const int cold_t[]={-63,-2130}, cold_p[]={95989,91911};
    for(unsigned i=0;i<2;i++) {
        fake_t f=fixture(); f.d2=cold_d2[i]; ms5611_t d=device(&f);
        assert(ms5611_read_prom(&d)==0 && ms5611_read(&d,&s)==0);
        assert(s.pressure_pa>=cold_p[i]-2 && s.pressure_pa<=cold_p[i]+2);
        assert(s.temperature_centi_c>=cold_t[i]-2 && s.temperature_centi_c<=cold_t[i]+2);
    }
    /* Invalid ADC sentinel must never become a reading. */
    for(unsigned v=0;v<2;v++) for(unsigned which=0;which<2;which++) {
        fake_t f=fixture(); if(which) f.d2=v?0xffffff:0; else f.d1=v?0xffffff:0;
        ms5611_t d=device(&f); assert(ms5611_read_prom(&d)==0);
        s=(ms5611_sample_t){-123,-456}; assert(ms5611_read(&d,&s)==MS5611_INVALID_ADC);
        assert(s.pressure_pa==-123 && s.temperature_centi_c==-456);
    }
    puts("MS5611: PROM/CRC, two instances, datasheet vector, transport faults PASS");
    return 0;
}
