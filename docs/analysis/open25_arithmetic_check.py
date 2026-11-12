"""Arithmetic regression only; does not certify a circuit or mechanical release."""
import math
v, r, shunt = 5.4, 2.17, 0.01
i = v / (r + shunt)
lsb = 0.256 / 32768
assert math.isclose(i, 2.477064220183486)
assert 3100 < i * shunt / lsb < 3200
assert math.isclose(100_000 / 2 * 100e-9, 0.005)
assert math.isclose(10_000 / 2 * 100e-9, 0.0005)
assert 2.7 > 0 + 0.3  # Divider unsafe for an unpowered ADS1115.
assert 5.4 > 3.3  # Series R and C do not divide the steady-state voltage.
print(f"PASS: I={i:.6f}A Vshunt={i*shunt:.7f}V counts={i*shunt/lsb:.1f}; six arithmetic checks")
