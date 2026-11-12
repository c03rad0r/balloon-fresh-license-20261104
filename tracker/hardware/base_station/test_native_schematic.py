#!/usr/bin/env python3
"""Tests for the base-station native-schematic milestone.

Gate 1  native ERC on the produced .kicad_sch, against a NAMED logical baseline.
Gate 2  netlist parity: generator netlist == native export, every net and every pin.
Gate 3  negative control: break ONE pin and prove the parity gate rejects it.

Run: /usr/bin/python3 tracker/hardware/base_station/test_native_schematic.py
Exit 0 == all gates hold. Every test here exercises the REAL kicad-cli, no mocks.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCH = HERE / "base_station_v1.kicad_sch"
MAP = HERE / "symbol-mapping.json"
sys.path.insert(0, str(HERE))
import base_station_parity as P            # noqa: E402
import base_station_erc_gate as E          # noqa: E402
import gen_base_station_schematic as G     # noqa: E402


def kicad():
    return shutil.which("kicad-cli") is not None


def mutate_pin(src: Path, moves, dest: Path):
    """Move pins' labels to other nets in a copy of the schematic.

    `moves` is [(ref, pin, new_net), ...] so a whole net can be renamed by naming every
    one of its endpoints. Returns the old net of each moved pin.
    """
    positions = json.loads(MAP.read_text())["pin_positions"]
    text = src.read_text()
    olds = []
    for ref, pin, new_net in moves:
        at = positions[ref][pin]
        old = positions[ref][pin]["net"]
        olds.append(old)
        if old is None:
            # pin had a no_connect: replace it with a label on a net of our choosing
            marker = f"(no_connect (at {at['x']} {at['y']})"
            assert marker in text, f"no no_connect found for {ref}.{pin} at {at}"
            i = text.index(marker)
            j = text.index(")", text.index("(uuid", i)) + 1
            text = text[:i] + (f'(label "{new_net}" (at {at["x"]} {at["y"]} 0) '
                               f'(effects (font (size 1.27 1.27)) (justify left bottom)) '
                               f'(uuid "00000000-000o-4000-8000-00000000000'
                               f'{len(olds)}"))') + text[j:]
        else:
            # Match the label by net name and position, whatever rotation/justification the
            # placer chose. Pinning rot 0 here made the negative control fail the moment the
            # layout started rotating bottom-pin labels -- the control must break the NET,
            # not depend on how it is drawn.
            pat = re.compile(r'\(label "' + re.escape(old) + r'" \(at '
                             + re.escape(f"{at['x']} {at['y']}") + r' [-\d.]+\)')
            m = pat.search(text)
            assert m, f"label {old} at {ref}.{pin} ({at['x']},{at['y']}) not found"
            rot = m.group(0).rsplit(" ", 1)[1].rstrip(")")
            text = (text[:m.start()] + f'(label "{new_net}" (at {at["x"]} {at["y"]} {rot})'
                    + text[m.end():])
    dest.write_text(text)
    return olds


@unittest.skipUnless(kicad(), "kicad-cli not installed -- a gate that cannot run must not pass")
class Gate1NativeERC(unittest.TestCase):
    """The schematic loads in KiCad and its ERC result is the named baseline, nothing else."""

    @classmethod
    def setUpClass(cls):
        assert SCH.exists(), "run gen_base_station_schematic.py first"
        cls.violations, cls.raw = E.run_erc(SCH)

    def test_erc_runs_and_is_at_the_named_baseline(self):
        ok, failures = E.evaluate(self.violations, verbose=False)
        self.assertTrue(ok, f"ERC drifted from the named baseline: {failures}")

    def test_no_symbol_or_footprint_resolution_failures(self):
        types, _ = E.classify(self.violations)
        self.assertNotIn("lib_symbol_issues", types,
                         "a symbol did not resolve: the schematic is not self-contained")
        self.assertNotIn("footprint_link_issues", types,
                        "a footprint library is missing from the search path")

    def test_the_7_dangling_nets_are_the_generators_single_node_nets(self):
        """The ERC allowance is not a fudge: each net really is single-node in the generator."""
        mapping = json.loads(MAP.read_text())
        single = {n for n, nodes in mapping["nets"].items() if len(nodes) == 1}
        self.assertEqual(single, E.BASELINE_NETS,
                         "the ERC baseline and the generator's single-node nets disagree")

    def test_erc_cannot_see_the_pcb(self):
        """Guard the claim: ERC output carries no board information at all."""
        types, _ = E.classify(self.violations)
        for board_only in ("clearance", "unconnected_items", "silk_overlap",
                           "solder_mask_bridge", "track_dangling"):
            self.assertNotIn(board_only, types,
                             f"{board_only} is a board finding; ERC must never report it")


@unittest.skipUnless(kicad(), "kicad-cli not installed")
class Gate2NetlistParity(unittest.TestCase):
    """Every net and every pin membership in the generator appears in the native export."""

    @classmethod
    def setUpClass(cls):
        cls.gen = P.regenerate()
        cls.nat = P.native_export(SCH)

    def test_parity_holds(self):
        failures, _, ng, nn, na = P.compare(self.gen, self.nat, verbose=False)
        self.assertEqual(failures, [], f"parity broken: {failures}")
        self.assertEqual(ng, 40, "the generator should declare 40 nets")
        self.assertEqual(nn, 40, "the native export should declare the same 40 nets")

    def test_component_set_and_fields_are_identical(self):
        tree = __import__("ast").parse((HERE / "gen_base_station_netlist.py").read_text())
        gen = {}
        for node in __import__("ast").walk(tree):
            if (isinstance(node, __import__("ast").Call)
                    and isinstance(node.func, __import__("ast").Name)
                    and node.func.id == "add"):
                gen[__import__("ast").literal_eval(node.args[0])] = (
                    __import__("ast").literal_eval(node.args[1]),
                    __import__("ast").literal_eval(node.args[2]))
        comps = dict(re.findall(r'\(comp \(ref "([^"]+)"\)\s*\n\s*\(value "([^"]*)"\)',
                                self.nat))
        fps = dict(re.findall(r'\(comp \(ref "([^"]+)"\)\s*\n\s*\(value "[^"]*"\)\s*\n'
                              r'\s*\(footprint "([^"]*)"\)', self.nat))
        self.assertEqual(set(comps), set(gen), "component refs differ")
        for ref, (value, fp) in gen.items():
            self.assertEqual(comps[ref], value, f"{ref} value changed")
            self.assertEqual(fps[ref], fp, f"{ref} footprint changed")

    def test_rp2040_pad_map_survives_transcription(self):
        """The corrected physical pin map is the thing at risk; assert it by pad number."""
        _nets, pins = P.parse_netlist(self.nat)
        expected = {
            "1": "+3V3_MCU", "10": "+3V3_MCU", "19": "GND", "20": "XIN", "21": "XOUT",
            "22": "+3V3_MCU", "23": "+1V1_CORE", "24": "SWCLK", "25": "SWDIO", "26": "RUN",
            "29": "VGA_GAIN0", "30": "VGA_GAIN1", "31": "VGA_GAIN2", "32": "LNA_EN",
            "33": "+3V3_MCU", "34": "LNA_FLT", "37": "REG_PG", "38": "DET_VOUT",
            "42": "+3V3_MCU", "43": "+3V3_MCU", "44": "+3V3_MCU", "45": "+1V1_CORE",
            "46": "USB_DM", "47": "USB_DP", "48": "+3V3_MCU", "49": "+3V3_MCU",
            "50": "+1V1_CORE", "51": "QSPI_SD3", "52": "QSPI_SCLK", "53": "QSPI_SD0",
            "54": "QSPI_SD2", "55": "QSPI_SD1", "56": "QSPI_SS", "57": "GND",
        }
        for pad, net in expected.items():
            self.assertEqual(pins.get(("U_MCU", pad)), net, f"U_MCU pad {pad}")

    def test_four_separate_five_volt_domains_exist(self):
        """spec.json's ERC requirement: no LNA fault may remove MCU power."""
        nets, _ = P.parse_netlist(self.nat)
        for rail in ("+5V_LNA_SW", "+5V_VGA", "+5V_DET", "+3V3_MCU"):
            self.assertIn(rail, nets, f"{rail} is not a net in the native export")
        self.assertNotIn(("U_MCU", "1"), nets["+5V_LNA_SW"].union(nets["+5V_VGA"]))
        for rail in ("+5V_LNA_SW", "+5V_VGA", "+5V_DET"):
            for ref, _pin in nets[rail]:
                self.assertFalse(ref.startswith("U_MCU"),
                                 f"{ref} is on {rail}; MCU power must not follow an RF rail")


@unittest.skipUnless(kicad(), "kicad-cli not installed")
class Gate3NegativeControl(unittest.TestCase):
    """A parity gate that has never been seen to fail is not a gate."""

    def _check_mutated(self, moves):
        with tempfile.TemporaryDirectory() as td:
            broken = Path(td) / "broken.kicad_sch"
            shutil.copy(HERE / "sym-lib-table", Path(td) / "sym-lib-table")
            shutil.copy(HERE / "BaseStation.kicad_sym", Path(td) / "BaseStation.kicad_sym")
            old = mutate_pin(SCH, moves, broken)
            nat = P.native_export(broken)
            failures, _, _ng, _nn, _na = P.compare(P.regenerate(), nat, verbose=False)
            return old, failures

    def test_moving_one_pin_breaks_parity(self):
        """Move GND off U_MCU pad 57 to +3V3_MCU: the export must disagree with the generator."""
        old, failures = self._check_mutated([("U_MCU", "57", "+3V3_MCU")])
        self.assertEqual(old, ["GND"])
        self.assertTrue(failures,
                        "moving U_MCU pad 57 from GND to +3V3_MCU went UNDETECTED -- the gate "
                        "does not test pin membership")
        joined = " ".join(failures)
        self.assertIn("PIN MEMBERSHIP MISMATCH", joined)
        self.assertIn("GND", joined)
        self.assertIn("+3V3_MCU", joined)

    def test_moving_one_endpoint_of_a_two_node_net_breaks_parity(self):
        """Rename one endpoint of RF_433_ANT: the gate must see the split, not shrug."""
        old, failures = self._check_mutated([("J_433_RX", "1", "RF_433_ANT_TYPO")])
        self.assertEqual(old, ["RF_433_ANT"])
        joined = " ".join(failures)
        self.assertTrue(failures, "a split net went undetected")
        self.assertIn("PIN MEMBERSHIP MISMATCH", joined)
        self.assertIn("RF_433_ANT_TYPO", joined)

    def test_renaming_a_whole_net_breaks_parity(self):
        """Rename EVERY endpoint of RF_433_ANT: that net must come out MISSING, the new one EXTRA."""
        old, failures = self._check_mutated([("J_433_RX", "1", "RF_433_ANT_TYPO"),
                                            ("FLT_433_A", "1", "RF_433_ANT_TYPO")])
        self.assertEqual(old, ["RF_433_ANT", "RF_433_ANT"])
        joined = " ".join(failures)
        self.assertIn("MISSING NET", joined)
        self.assertIn("RF_433_ANT", joined)
        self.assertIn("EXTRA NET", joined)
        self.assertIn("RF_433_ANT_TYPO", joined)

    def test_connecting_a_deliberately_open_pin_breaks_parity(self):
        """U_MCU pad 2 (GPIO0) is unconnected today; wiring it must be caught."""
        old, failures = self._check_mutated([("U_MCU", "2", "SPURIOUS_NET")])
        self.assertEqual(old, [None], "U_MCU pad 2 was expected to have no label")
        self.assertTrue(failures, "connecting an unused pad went undetected")
        joined = " ".join(failures)
        self.assertIn("EXTRA NET", joined)
        self.assertIn("SPURIOUS_NET", joined)

    def test_gate_reports_refusal_when_the_schematic_is_absent(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "nope.kicad_sch"
            rc = subprocess.run([sys.executable, str(HERE / "base_station_parity.py"),
                                 "--sch", str(missing)], capture_output=True, text=True)
            self.assertEqual(rc.returncode, 2, "a missing schematic must REFUSE, not pass")
            self.assertIn("REFUSED", rc.stdout)


@unittest.skipUnless(kicad(), "kicad-cli not installed")
class TranscriptionHonesty(unittest.TestCase):
    """The artifacts must not claim more than the transcription did."""

    def test_every_component_records_its_pin_number_basis(self):
        mapping = json.loads(MAP.read_text())
        for ref, d in mapping["components"].items():
            self.assertIn(d["pin_number_basis"],
                          ("stock-verified-pin-set", "UNVERIFIED"),
                          f"{ref} has no stated basis for its pin numbers")
            self.assertTrue(d["rationale"], f"{ref} has no recorded symbol rationale")

    def test_local_symbols_are_exactly_the_parts_with_no_stock_symbol(self):
        mapping = json.loads(MAP.read_text())
        local = {ref for ref, d in mapping["components"].items() if d["kind"] == "local"}
        self.assertEqual(local, {"U_VGA", "U_DET", "Q_LNA_SW", "FLT_433_A", "FLT_433_B"},
                         "the set of locally-invented symbols changed -- re-justify it")

    def test_no_local_symbol_asserts_a_power_output(self):
        """A part nobody has selected must not claim to drive a rail."""
        text = (HERE / "BaseStation.kicad_sym").read_text()
        for m in re.finditer(r'\(symbol "(BaseStation:[^"]+)".*?(?=\(symbol "|\)\s*$)',
                             text, re.S):
            self.assertNotIn("power_out", m.group(0),
                             f"{m.group(1)} asserts power_out but no part is selected")

    def test_generator_pin_counts_match_the_symbols_they_use(self):
        mapping = json.loads(MAP.read_text())
        for ref, d in mapping["components"].items():
            self.assertTrue(set(d["generator_pins"]) <= set(d["symbol_pins"]),
                            f"{ref}: generator pins missing from {d['lib_id']}")

    def test_schematic_is_self_contained(self):
        """No external symbol library is needed: every lib_id is embedded in lib_symbols."""
        text = SCH.read_text()
        embedded = set(re.findall(r'\(symbol "([A-Za-z0-9_]+:[^"]+)"', text))
        used = set(re.findall(r'\(lib_id "([^"]+)"\)', text))
        self.assertTrue(used <= embedded, f"lib_ids with no embedded symbol: {used - embedded}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
