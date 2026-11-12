#!/usr/bin/env python3
"""Logical package-pin contract, NOT ERC or board approval.
Oracle: official RP2040 datasheet §1.4 Figure 3, §2.9.
GPIO allocation is explicit here; integers in maps are physical QFN pads.
"""
import ast
from pathlib import Path
import re
import unittest

HERE = Path(__file__).resolve().parent
POWER = {str(p): '+3V3_MCU' for p in (1, 10, 22, 33, 42, 43, 44, 48, 49)}
POWER.update({str(p): '+1V1_CORE' for p in (23, 45, 50)})
GROUND = {'19': 'GND', '57': 'GND'}  # TESTEN and footprint's exposed-pad number
USB = {'46': 'USB_DM', '47': 'USB_DP'}
DEBUG_CLOCK = {'20': 'XIN', '21': 'XOUT', '24': 'SWCLK', '25': 'SWDIO', '26': 'RUN'}
FLASH = {'51': 'QSPI_SD3', '52': 'QSPI_SCLK', '53': 'QSPI_SD0',
         '54': 'QSPI_SD2', '55': 'QSPI_SD1', '56': 'QSPI_SS'}
# GPIO18/19/20 gains, GPIO21 enable, GPIO22 fault, GPIO25 PG, GPIO26/ADC0 detector.
GPIO = {'29': 'VGA_GAIN0', '30': 'VGA_GAIN1', '31': 'VGA_GAIN2',
        '32': 'LNA_EN', '34': 'LNA_FLT', '37': 'REG_PG', '38': 'DET_VOUT'}
EXPECTED = POWER | GROUND | USB | DEBUG_CLOCK | FLASH | GPIO
FLASH_DEVICE = {'1': 'QSPI_SS', '2': 'QSPI_SD1', '3': 'QSPI_SD2', '4': 'GND',
                '5': 'QSPI_SD0', '6': 'QSPI_SCLK', '7': 'QSPI_SD3',
                '8': '+3V3_MCU', '9': 'GND'}


def source():
    tree = ast.parse((HERE / 'gen_base_station_netlist.py').read_text())
    return {ast.literal_eval(n.args[0]): dict(ast.literal_eval(n.args[3]))
            for n in ast.walk(tree) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == 'add'}


def netlist():
    result = {}
    for name, body in re.findall(r'\(net \(code "\d+"\) \(name "([^"]+)"\)(.*?)(?=\n    \))',
                                 (HERE / 'base_station_v1.net').read_text(), re.S):
        for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)\)', body):
            assert pin not in result.setdefault(ref, {}), (ref, pin, 'duplicate node')
            result[ref][pin] = name
    return result


def validate(actual):
    assert actual == EXPECTED, (actual, EXPECTED)


class PinMap(unittest.TestCase):
    def test_source_contract(self):
        validate(source()['U_MCU'])

    def test_netlist_contract(self):
        validate(netlist()['U_MCU'])

    def test_flash_data_direction(self):
        # Standard serial NOR: pin 2 DO/IO1, pin 5 DI/IO0.
        # Exact flash MPN/package qualification is still a release blocker.
        for data in (source(), netlist()):
            self.assertEqual(data['U_FLASH'], FLASH_DEVICE)

    def test_every_function_rejects_wrong_net(self):
        for pin in EXPECTED:
            with self.subTest(pin=pin):
                bad = dict(EXPECTED)
                bad[pin] = 'WRONG_NET'
                with self.assertRaises(AssertionError):
                    validate(bad)

    def test_unused_gpio_must_not_be_grounded(self):
        bad = dict(EXPECTED, **{'2': 'GND'})
        with self.assertRaises(AssertionError):
            validate(bad)

    def test_supply_domains_and_endpoints(self):
        data = netlist()
        for ref in ('C_MCU1', 'C_MCU2'):
            self.assertEqual(data[ref], {'1': '+3V3_MCU', '2': 'GND'})
        self.assertEqual(data['J_SWD'], {'1': '+3V3_MCU', '2': 'SWDIO', '3': 'GND', '4': 'SWCLK'})
        self.assertEqual(data['R_RUN']['2'], 'RUN')
        self.assertEqual(data['Y1'], {'1': 'XIN', '2': 'GND', '3': 'XOUT', '4': 'GND'})
        for ref, pin, net in [('U_VGA', '6', 'VGA_GAIN0'), ('U_VGA', '7', 'VGA_GAIN1'),
                              ('U_VGA', '8', 'VGA_GAIN2'), ('Q_LNA_SW', '3', 'LNA_EN'),
                              ('Q_LNA_SW', '4', 'LNA_FLT'), ('U_DET', '6', 'DET_VOUT'),
                              ('U_REG', '8', 'REG_PG')]:
            self.assertEqual(data[ref][pin], net)


if __name__ == '__main__':
    unittest.main()
