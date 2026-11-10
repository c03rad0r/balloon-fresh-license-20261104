"""Logical supply regression only; does not certify PCB, ERC or analog performance."""
import ast
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent

def components():
    tree = ast.parse((HERE / 'gen_base_station_netlist.py').read_text())
    return {ast.literal_eval(n.args[0]): tuple(ast.literal_eval(a) for a in n.args[1:])
            for n in ast.walk(tree) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == 'add'}

class Supply(unittest.TestCase):
    def setUp(self):
        self.c = components()

    def test_fixed_five_volt_orderable(self):
        self.assertIn('TPS62163DSGR', self.c['U_REG'][0])

    def test_enable_has_input_not_output_startup(self):
        self.assertEqual(dict(self.c['U_REG'][2])['3'], 'VIN_GS_PROT')
        self.assertNotIn('R_EN', self.c)

    def test_pg_pullup_is_logic_safe(self):
        self.assertIn('R_PG', self.c)
        self.assertIn('100k', self.c['R_PG'][0])
        self.assertEqual(dict(self.c['R_PG'][2]), {'1': '+3V3_MCU', '2': 'REG_PG'})

    def test_no_unused_feedback_divider(self):
        self.assertNotIn('R_FB1', self.c)
        self.assertNotIn('R_FB2', self.c)
        self.assertEqual(dict(self.c['U_REG'][2])['5'], 'GND')

    def test_selected_passives(self):
        for ref, mpn in {'L1':'SRN4018-2R2M', 'C_IN':'GRM31CR61E106KA12L',
                         'C_OUT':'GRM31CR71A226KE15L'}.items():
            with self.subTest(ref=ref):
                self.assertIn(mpn, self.c[ref][0])
        self.assertEqual(dict(self.c['C_OUT'][2]), {'1': '+5V_PCBA', '2':'GND'})

    def test_mcu_domains_remain_separate(self):
        m = dict(self.c['U_MCU'][2])
        self.assertFalse(any(n.startswith('+5V') or n == 'VIN_GS_PROT' for n in m.values()))
        self.assertEqual({p for p,n in m.items() if n == '+1V1_CORE'}, {'23','45','50'})
        self.assertEqual(m['37'], 'REG_PG')

    def test_generated_components_and_pins_match_source(self):
        text = (HERE / 'base_station_v1.net').read_text()
        values = dict(re.findall(r'\(comp \(ref "([^"]+)"\)\s*\n\s*\(value "([^"]*)"\)', text))
        nets = {}
        for name, body in re.findall(r'\(net \(code "\d+"\) \(name "([^"]+)"\)(.*?)(?=\n    \))', text, re.S):
            for ref,pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)\)', body):
                nets[ref,pin] = name
        self.assertEqual(values, {r:v for r,(v,fp,pins) in self.c.items()})
        self.assertEqual(nets, {(r,p):n for r,(_,_,pins) in self.c.items() for p,n in pins})

if __name__ == '__main__':
    unittest.main()
