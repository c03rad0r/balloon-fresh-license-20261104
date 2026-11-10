/* Extracted from main.c MS5611 path; TE MS5611-01BA03 compensation,
 * with full PROM CRC4 and per-device state. No actuator dependencies. */
#include "ms5611.h"
#include <string.h>
static unsigned crc4(const uint16_t prom[8]) {
    uint16_t rem=0;
    for (unsigned byte=0; byte<16; byte++) {
        uint16_t word=prom[byte/2];
        if(byte/2==7) word &= 0xff00;
        rem ^= (byte & 1) ? word & 0xff : word >> 8;
        for(unsigned bit=0;bit<8;bit++)
            rem = (rem & 0x8000) ? (rem << 1)^0x3000 : rem << 1;
    }
    return (rem >> 12)&15;
}
int ms5611_read_prom(ms5611_t *d) {
    if(!d) return MS5611_NOT_READY;
    d->ready=false;
    memset(d->prom,0,sizeof d->prom);
    if(!d->io.transfer || !d->io.wait_ms) return MS5611_NOT_READY;
    int r=d->io.transfer(d->io.ctx,0x1e,NULL,0,100);
    if(r) return r;
    d->io.wait_ms(d->io.ctx,3);
    uint16_t prom[8];
    for(unsigned i=0;i<8;i++) {
        uint8_t b[2];
        r=d->io.transfer(d->io.ctx,0xa0+2*i,b,2,100);
        if(r) return r;
        prom[i]=((uint16_t)b[0]<<8)|b[1];
    }
    for(unsigned i=1;i<=6;i++)
        if(prom[i]==0 || prom[i]==0xffff) return MS5611_INVALID_PROM;
    if(crc4(prom)!=(prom[7]&15)) return MS5611_INVALID_PROM;
    memcpy(d->prom,prom,sizeof prom);
    d->ready=true;
    return 0;
}
static int adc(ms5611_t *d,uint8_t command,uint32_t *out) {
    int r=d->io.transfer(d->io.ctx,command,NULL,0,100);
    if(r) return r;
    d->io.wait_ms(d->io.ctx,10); /* OSR4096 max conversion 9.04 ms */
    uint8_t b[3];
    r=d->io.transfer(d->io.ctx,0,b,3,100);
    if(r) return r;
    *out=((uint32_t)b[0]<<16)|((uint32_t)b[1]<<8)|b[2];
    return (*out==0 || *out==0xffffff) ? MS5611_INVALID_ADC : 0;
}
int ms5611_read(ms5611_t *d,ms5611_sample_t *s) {
    if(!d || !s || !d->ready || !d->io.transfer || !d->io.wait_ms)
        return MS5611_NOT_READY;
    uint32_t d1,d2;
    int r=adc(d,0x48,&d1); if(r) return r;
    r=adc(d,0x58,&d2); if(r) return r;
    const uint16_t *c=d->prom;
    int64_t dt=(int64_t)d2-(int64_t)c[5]*256;
    /* C11 division truncates toward zero, including below reference temp. */
    int64_t t=2000+dt*c[6]/8388608;
    int64_t off=(int64_t)c[2]*65536+c[4]*dt/128;
    int64_t sens=(int64_t)c[1]*32768+c[3]*dt/256;
    if(t<2000) {
        int64_t sq=(t-2000)*(t-2000);
        int64_t off2=5*sq/2, sens2=5*sq/4;
        if(t < -1500) {
            sq=(t+1500)*(t+1500);
            off2+=7*sq; sens2+=11*sq/2;
        }
        t-=dt*dt/2147483648LL;
        off-=off2; sens-=sens2;
    }
    s->pressure_pa=(int32_t)(((int64_t)d1*sens/2097152-off)/32768);
    s->temperature_centi_c=(int32_t)t;
    return 0;
}
