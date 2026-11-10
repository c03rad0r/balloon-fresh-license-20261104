#!/usr/bin/env python3
"""Bounded source pin-map regression, NOT a board-readiness/voltage gate.
TI SLVSAM2E section 6: TPS6216x DSG pins; fixed versions FB -> AGND.
Run with /usr/bin/python3. Does not execute the legacy generator on import.
"""
import ast
import re
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
EXPECTED = {'1': 'GND', '2': 'VIN_GS_PROT', '3': 'VIN_GS_PROT', '4': 'GND',
            '5': 'GND', '6': '+5V_PCBA', '7': 'REG_SW', '8': 'REG_PG', '9': 'GND'}


def regulator():
    tree = ast.parse((HERE / 'gen_base_station_netlist.py').read_text())
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'add' and ast.literal_eval(node.args[0]) == 'U_REG'):
            return dict(ast.literal_eval(node.args[3]))
    raise AssertionError('U_REG absent')


class PinMap(unittest.TestCase):
    def test_manufacturer_fixed_voltage_pinmap(self):
        self.assertEqual(regulator(), EXPECTED)

    def test_generated_netlist_pinmap(self):
        netlist = (HERE / 'base_station_v1.net').read_text()
        actual = {}
        for name, body in re.findall(r'\(net \(code "\d+"\) \(name "([^"]+)"\)(.*?)(?=\n    \))', netlist, re.S):
            for pin in re.findall(r'\(node \(ref "U_REG"\) \(pin "([^"]+)"\)\)', body):
                actual[pin] = name
        self.assertEqual(actual, EXPECTED)

    def test_known_bad_mapping_is_rejected(self):
        bad = dict(EXPECTED, **{'1': 'VIN_GS_PROT', '2': 'GND'})
        self.assertNotEqual(bad, EXPECTED)


if __name__ == '__main__':
    unittest.main()
