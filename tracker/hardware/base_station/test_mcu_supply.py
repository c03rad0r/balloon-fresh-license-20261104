"""Contract on freshly generated netlist, not source text; no physical signoff."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def generate():
    # Run the actual generator in isolation: never regenerate the rejected PCB.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        for name in ('gen_base_station_netlist.py', 'spec.json'):
            (out / name).write_bytes((HERE / name).read_bytes())
        subprocess.run([sys.executable, str(out / 'gen_base_station_netlist.py')],
                       check=True, capture_output=True)
        return (out / 'base_station_v1.net').read_text()


def parse(text):
    comps = dict(re.findall(r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]*)"\)', text))
    pins = {}
    for name, body in re.findall(r'\(net \(code "\d+"\) \(name "([^"]+)"\)(.*?)(?=\n    \))', text, re.S):
        for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)\)', body):
            assert pin not in pins.setdefault(ref, {}), (ref, pin)
            pins[ref][pin] = name
    return comps, pins


class MCUSupply(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = generate()
        cls.c, cls.n = parse(cls.text)

    def test_exact_regulator_and_package(self):
        self.assertIn('AP2112K-3.3TRG1', self.c['U_LDO'])
        self.assertRegex(self.text, r'\(comp \(ref "U_LDO"\).*?\n.*?\n\s*\(footprint "Package_TO_SOT_SMD:SOT-23-5"\)')

    def test_startup_pinout_and_nc(self):
        self.assertEqual(self.n['U_LDO'], {'1': '+5V_PCBA', '2': 'GND',
                                         '3': '+5V_PCBA', '5': '+3V3_MCU'})
        self.assertNotIn('LDO_EN', self.text)

    def cap(self, ref, rail, value):
        self.assertIn(ref, self.c, f'missing {ref}')
        self.assertIn(value, self.c[ref])
        self.assertEqual(self.n[ref], {'1': rail, '2': 'GND'})

    def test_ldo_local_capacitors(self):
        self.cap('C_LDO1', '+3V3_MCU', '2.2uF 16V X7R')
        self.cap('C_LDO2', '+5V_PCBA', '2.2uF 16V X7R')

    def test_vreg_stability(self):
        self.cap('C_MCU2', '+3V3_MCU', '1uF')  # pin 44 VREG_IN
        self.cap('C_VREG_OUT', '+1V1_CORE', '1uF')  # pin 45

    def test_per_pin_decoupling(self):
        self.cap('C_MCU1', '+3V3_MCU', '100nF')  # IOVDD pin 1
        for pin in (10, 22, 33, 42, 43, 48, 49):
            self.cap(f'C_MCU_P{pin}', '+3V3_MCU', '100nF')
        for pin in (23, 50):
            self.cap(f'C_MCU_P{pin}', '+1V1_CORE', '100nF')
        self.cap('C_FLASH', '+3V3_MCU', '100nF')

    def test_power_tree_no_five_volt_mcu_connection(self):
        m = self.n['U_MCU']
        for pin in (1, 10, 22, 33, 42, 43, 44, 48, 49):
            self.assertEqual(m[str(pin)], '+3V3_MCU')
        for pin in (23, 45, 50):
            self.assertEqual(m[str(pin)], '+1V1_CORE')
        high = {'VIN_GS', 'VIN_GS_PROT', 'REG_SW', '+5V_PCBA', '+5V_LNA_SW', '+5V_VGA', '+5V_DET'}
        self.assertTrue(high.isdisjoint(m.values()))
        # No passive DC bridge can join these rails to MCU pins (caps aren't DC bridges).
        for ref, pins in self.n.items():
            if ref.startswith(('R_', 'FB_', 'L1')):
                self.assertFalse(high.intersection(pins.values()) and set(m.values()).intersection(pins.values()))
        self.assertEqual(self.n['R_PG'], {'1': '+3V3_MCU', '2': 'REG_PG'})
        self.assertEqual(self.n['U_FLASH']['8'], '+3V3_MCU')

    def test_committed_netlist_matches_generation(self):
        self.assertEqual(self.text, (HERE / 'base_station_v1.net').read_text())


if __name__ == '__main__':
    unittest.main()
