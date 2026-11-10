"""Reproduce rejection of an unqualified supervisor retrofit; not qualification.
TI TPS3808 Rev N sections 4,6.5,6.6; TMUX1511 Rev B section 5.7.
All ramp/delay examples below are hypothetical, explicitly NOT guaranteed.
"""
import runpy
from pathlib import Path

dc = runpy.run_path(str(Path(__file__).with_name('check_cutter_adc_path.py')))
vin = 5.4 * max(dc['corners'])
vtrip_min = 3.07 * (1 - .015)
vtrip_max = 3.07 * (1 + .015)
margin = vtrip_min - vin
assert margin > 0
print(f'COMPUTED: loaded fault input={vin:.9f} V')
print(f'COMPUTED: G33 falling threshold={vtrip_min:.6f}..{vtrip_max:.6f} V; headroom={margin:.9f} V')
# 20us is TYPICAL ONLY; 55ns applies to the datasheet test load only.
illustrative_delay = 20e-6 + 55e-9
print(f'ILLUSTRATIVE ONLY: headroom/(20us+55ns)={margin/illustrative_delay:.3f} V/s')
# Counterexample to ANY universal ramp guarantee from a finite-latency detector.
slew = 100000.0  # hypothetical 0.1 V/us collapse, no lower slew bound supplied
at_disconnect = vtrip_min - slew * illustrative_delay
assert at_disconnect < vin
print(f'COUNTEREXAMPLE: at 0.1V/us with typical delay, rail={at_disconnect:.6f} V < input')
r_source = 500 * 10000 / 10500
print(f'TYPICAL ONLY: ADC 710kohm loading error={100*r_source/(710000+r_source):.6f}%')
print(f'CONDITIONAL: 2uA*10.05kohm={2e-6*10050:.6f} V; not valid zero-injection proof')
# None deliberately prevents a typical-only timing number becoming a safety bound.
supervisor_assertion_max_s = None
assert supervisor_assertion_max_s is None
print('BLOCKED: no maximum SENSE-to-RESET delay; no collapse slew/hold-up bound; no full-ramp leakage bound')
