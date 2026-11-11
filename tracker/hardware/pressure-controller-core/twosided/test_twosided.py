#!/usr/bin/env python3
"""Regression and negative controls for the two-sided placement audit.

A gate never observed failing has not been tested. Each negative control poisons a COPY of
the candidate with one specific defect and requires the same `audit()` to refuse it. The
clean control asserts the candidate's real state, so a gate that refuses everything is
equally caught.

Run: /usr/bin/python3 test_twosided.py -v
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import pcbnew as pcb

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import twosided as T  # noqa: E402


def poisoned(fn):
    """Copy the candidate, apply `fn`, and return the audit's refusal message."""
    tmp = Path(tempfile.mkdtemp(prefix='twosided-poison-')) / 'poison.kicad_pcb'
    shutil.copyfile(T.BOARD, tmp)
    for name in ('kicad_pro', 'fp-lib-table'):
        src = HERE / ('twosided.' + name if name == 'kicad_pro' else name)
        if src.exists():
            shutil.copyfile(src, tmp.parent / ('poison.' + name) if name == 'kicad_pro'
                            else tmp.parent / name)
    b = pcb.LoadBoard(str(tmp))
    fn(b)
    pcb.SaveBoard(str(tmp), b)
    del b
    try:
        T.audit(tmp)
    except ValueError as exc:
        return str(exc)
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)
    return None


class CleanControl(unittest.TestCase):
    def test_candidate_state(self):
        proof = T.audit()
        self.assertEqual(proof['board_mm'], [52.0, 46.0])
        self.assertEqual(proof['references'], 26)
        self.assertEqual(proof['exported_endpoints'], 125)
        self.assertEqual(proof['nets'], 51)
        self.assertEqual(proof['side_counts'], {'top': 12, 'bottom': 14})
        self.assertEqual(proof['tracks'], 0)
        self.assertLessEqual(proof['motor_reservation_mm'][2], 52.0)
        del proof

    def test_both_sides_are_actually_populated(self):
        """The operator asked for both sides; a single-sided result must fail this."""
        proof = T.audit()
        self.assertGreaterEqual(proof['side_counts']['top'], 1)
        self.assertGreaterEqual(proof['side_counts']['bottom'], 1)
        self.assertEqual(sum(proof['side_counts'].values()), 26)

    def test_buck_loop_metrics_are_rigid(self):
        """A rigid mirror+translate must not change ANY internal pad-centre metric."""
        proof = T.audit()
        loops = proof['power_loop_mm']
        self.assertEqual(loops['CIN_to_VIN_mm'], 2.35)
        self.assertEqual(loops['CIN_to_PGND_mm'], 3.4)
        self.assertEqual(loops['SW_to_L_mm'], 2.28)
        self.assertEqual(loops['L_to_COUT_mm'], 3.33)
        self.assertEqual(loops['COUT_to_VOS_mm'], 9.66)
        self.assertEqual(loops['FB_divider_to_FB_mm'], 4.91)

    def test_motor_reservation_is_empty_and_full_size(self):
        proof = T.audit()
        self.assertEqual(proof['motor_area_mm2'], 720)
        m = proof['motor_reservation_mm']
        self.assertAlmostEqual(m[2] - m[0], 30.0)
        self.assertAlmostEqual(m[3] - m[1], 24.0)

    def test_antenna_keepout_is_preserved(self):
        proof = T.audit()
        self.assertEqual(proof['antenna_keepout_mm'][0], 4.0)
        self.assertEqual(proof['antenna_keepout_mm'][2], 52.0)


class NegativeControls(unittest.TestCase):
    def test_second_part_on_same_face_at_same_spot_is_refused(self):
        def plant(b):
            fp = {f.GetReference(): f for f in b.GetFootprints()}
            c2, c3 = fp['C2'], fp['C3']
            c3.SetPosition(c2.GetPosition())
        msg = poisoned(plant)
        self.assertIsNotNone(msg, 'a same-face duplicate was accepted')
        self.assertIn('overlap', msg)

    def test_part_inside_motor_reservation_is_refused(self):
        def plant(b):
            fp = {f.GetReference(): f for f in b.GetFootprints()}
            fp['R2'].SetPosition(pcb.VECTOR2I(pcb.FromMM(40), pcb.FromMM(35)))
        msg = poisoned(plant)
        self.assertIsNotNone(msg)
        self.assertIn('motor reservation', msg)

    def test_part_inside_antenna_keepout_is_refused(self):
        def plant(b):
            fp = {f.GetReference(): f for f in b.GetFootprints()}
            fp['R1'].SetPosition(pcb.VECTOR2I(pcb.FromMM(30), pcb.FromMM(-10)))
        msg = poisoned(plant)
        self.assertIsNotNone(msg)
        self.assertIn('antenna keepout', msg)

    def test_part_off_the_board_is_refused(self):
        def plant(b):
            fp = {f.GetReference(): f for f in b.GetFootprints()}
            fp['R2'].SetPosition(pcb.VECTOR2I(pcb.FromMM(60), pcb.FromMM(40)))
        msg = poisoned(plant)
        self.assertIsNotNone(msg)
        self.assertIn('outside board', msg)

    def test_added_copper_is_refused(self):
        def plant(b):
            fp = {f.GetReference(): f for f in b.GetFootprints()}
            net = b.FindNet('/GND')
            seg = pcb.PCB_TRACK(b)
            seg.SetNet(net)
            seg.SetLayer(pcb.B_Cu)
            seg.SetWidth(pcb.FromMM(0.2))
            seg.SetStart(pcb.VECTOR2I(pcb.FromMM(10), pcb.FromMM(20)))
            seg.SetEnd(pcb.VECTOR2I(pcb.FromMM(20), pcb.FromMM(20)))
            b.Add(seg)
        msg = poisoned(plant)
        self.assertIsNotNone(msg)
        self.assertIn('unrouted', msg)

    def test_part_in_a_through_hole_pad_field_is_refused(self):
        """THE DEFECT THAT NATIVE DRC FOUND. J1's S1 shield pads are THT and occupy both
        faces, so a BOTTOM SMT part under them is illegal even though the two courtyards are
        on different layers and never intersect. This control plants exactly that and
        requires the audit to refuse it."""
        def plant(b):
            fp = {f.GetReference(): f for f in b.GetFootprints()}
            # J1's shield pads are around y 23.2..32.8 on the west edge.
            fp['C2'].SetPosition(pcb.VECTOR2I(pcb.FromMM(5.7), pcb.FromMM(27.5)))
        msg = poisoned(plant)
        self.assertIsNotNone(msg, 'a part inside a THT pad field was accepted')
        self.assertIn('through-hole pad field', msg)

    def test_wrong_net_is_refused(self):
        def plant(b):
            fp = {f.GetReference(): f for f in b.GetFootprints()}
            for p in fp['U3'].Pads():
                if p.GetNumber() == '1':
                    p.SetNetCode(0)
                    break
        msg = poisoned(plant)
        self.assertIsNotNone(msg)
        self.assertIn('net parity', msg)

    def test_wrong_side_is_refused(self):
        def plant(b):
            fp = {f.GetReference(): f for f in b.GetFootprints()}
            fp['U3'].Flip(fp['U3'].GetPosition(), False)
        msg = poisoned(plant)
        self.assertIsNotNone(msg)
        self.assertIn('wrong side', msg)

    def test_sensor_port_blocked_on_same_face_is_refused(self):
        def plant(b):
            fp = {f.GetReference(): f for f in b.GetFootprints()}
            # In the straight tube run NORTH of U3's port: no courtyard touch, but the
            # pressure tube could not leave the sensor. The refusal must name the corridor.
            fp['R9'].SetPosition(pcb.VECTOR2I(pcb.FromMM(41.0), pcb.FromMM(3.0)))
        msg = poisoned(plant)
        self.assertIsNotNone(msg)
        self.assertIn('tube corridor', msg)

    def test_rotated_footprint_is_not_a_false_positive(self):
        """CONTROL FOR THE INSTRUMENT, not the board. pad_signature() compares pads in the
        footprint's own frame; a legal rotation must NOT read as a package change. Measured:
        the first version compared board-frame offsets and reported C7's 90-degree rotation as
        'footprint geometry changed'."""
        tmp = Path(tempfile.mkdtemp(prefix='twosided-rot-')) / 'rot.kicad_pcb'
        shutil.copyfile(T.BOARD, tmp)
        shutil.copyfile(HERE / 'twosided.kicad_pro', tmp.parent / 'rot.kicad_pro')
        shutil.copyfile(HERE / 'fp-lib-table', tmp.parent / 'fp-lib-table')
        b = pcb.LoadBoard(str(tmp))
        fp = {f.GetReference(): f for f in b.GetFootprints()}
        fp['C7'].SetOrientationDegrees(fp['C7'].GetOrientationDegrees() + 90.0)
        pcb.SaveBoard(str(tmp), b)
        del b
        try:
            T.audit(tmp)          # must NOT raise
        finally:
            shutil.rmtree(tmp.parent, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
