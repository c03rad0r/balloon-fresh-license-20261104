#!/usr/bin/env python3
"""Compact study gates: one clean control plus real mutation controls.

Every negative control writes a poisoned copy and requires the SAME audit the clean
run uses to REFUSE. A gate that cannot refuse has not been tested.

Run: /usr/bin/python3 test_compact.py     (needs distro pcbnew + shapely)
"""
import json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
import pcbnew as pcb

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import study


class Compact(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='compact-test-'))
        cls.board = HERE / 'compact.kicad_pcb'
        if not cls.board.exists():
            subprocess.run([sys.executable, str(HERE / 'study.py')], check=True)

    def copy(self, name):
        p = self.tmp / (name + '.kicad_pcb')
        shutil.copyfile(self.board, p)
        return p

    def assertRefused(self, path, pattern):
        with self.assertRaisesRegex(ValueError, pattern):
            study.audit(path)

    # ---- clean control -------------------------------------------------
    def test_clean_control_passes_and_is_65x50(self):
        proof = study.audit()
        self.assertEqual(proof['references'], 26)
        self.assertEqual(proof['exported_endpoints'], 125)
        self.assertEqual(proof['nets'], 51)
        self.assertEqual(proof['side_counts'], {'top': 26, 'bottom': 0})
        self.assertEqual(proof['courtyard_overlaps'], 0)
        self.assertEqual(proof['pad_bbox_overlaps'], 0)
        published = json.loads((HERE / 'proof.json').read_text())
        self.assertEqual(published['candidate_dimensions_mm'], [65, 50])
        self.assertGreater(proof['courtyard_occupancy_percent_inside_board'], 0)
        b = pcb.LoadBoard(str(self.board))
        e = [g for g in b.GetDrawings() if g.GetLayer() == pcb.Edge_Cuts][0]
        self.assertAlmostEqual((e.GetEnd().x - e.GetStart().x) / 1e6, 65.0, places=6)
        self.assertAlmostEqual((e.GetEnd().y - e.GetStart().y) / 1e6, 50.0, places=6)

    def test_motor_reservation_is_30x24_and_empty(self):
        b = pcb.LoadBoard(str(self.board))
        keep = [z for z in b.Zones() if z.GetIsRuleArea()]
        self.assertEqual(len(keep), 1)
        bb = keep[0].GetBoundingBox()
        self.assertAlmostEqual((bb.GetRight() - bb.GetLeft()) / 1e6, 30.0, places=6)
        self.assertAlmostEqual((bb.GetBottom() - bb.GetTop()) / 1e6, 24.0, places=6)
        space = json.loads((HERE / 'space.json').read_text())
        self.assertTrue(space['motor_reservation_fully_empty'])

    def test_source_checkpoint_byte_identical_to_git(self):
        src = HERE.parent / 'placement/core-placement.kicad_pcb'
        head = subprocess.run(['git', 'show', 'HEAD:tracker/hardware/pressure-controller-core/'
                               'placement/core-placement.kicad_pcb'],
                              cwd=HERE.parent.parent.parent.parent, capture_output=True, check=True).stdout
        self.assertEqual(head, src.read_bytes(), 'source checkpoint was modified')

    def test_no_routing_in_candidate(self):
        b = pcb.LoadBoard(str(self.board))
        self.assertEqual(len(list(b.GetTracks())), 0)

    # ---- negative controls ---------------------------------------------
    def test_duplicate_placement_is_refused(self):
        p = self.copy('overlap')
        b = pcb.LoadBoard(str(p))
        f = {x.GetReference(): x for x in b.GetFootprints()}
        f['U4'].SetPosition(f['U3'].GetPosition())
        pcb.SaveBoard(str(p), b)
        self.assertRefused(p, 'pad overlap|courtyard overlap')

    def test_part_in_motor_reservation_is_refused(self):
        p = self.copy('motor')
        b = pcb.LoadBoard(str(p))
        f = {x.GetReference(): x for x in b.GetFootprints()}
        f['U4'].SetPosition(pcb.VECTOR2I(pcb.FromMM(48), pcb.FromMM(40)))
        pcb.SaveBoard(str(p), b)
        self.assertRefused(p, 'motor reservation')

    def test_part_in_antenna_keepout_is_refused(self):
        p = self.copy('antenna')
        b = pcb.LoadBoard(str(p))
        f = {x.GetReference(): x for x in b.GetFootprints()}
        f['U3'].SetPosition(pcb.VECTOR2I(pcb.FromMM(20), pcb.FromMM(-12)))
        pcb.SaveBoard(str(p), b)
        self.assertRefused(p, 'antenna keepout')

    def test_wrong_net_is_refused(self):
        p = self.copy('net')
        b = pcb.LoadBoard(str(p))
        f = {x.GetReference(): x for x in b.GetFootprints()}
        f['U3'].Pads()[0].SetNetCode(0)
        pcb.SaveBoard(str(p), b)
        self.assertRefused(p, 'net parity')

    def test_part_off_board_is_refused(self):
        p = self.copy('outside')
        b = pcb.LoadBoard(str(p))
        f = {x.GetReference(): x for x in b.GetFootprints()}
        f['U4'].SetPosition(pcb.VECTOR2I(pcb.FromMM(64), pcb.FromMM(15)))
        pcb.SaveBoard(str(p), b)
        self.assertRefused(p, 'outside board')

    def test_part_over_sensor_port_is_refused(self):
        p = self.copy('port')
        b = pcb.LoadBoard(str(p))
        f = {x.GetReference(): x for x in b.GetFootprints()}
        # R9's courtyard is 3.02 x 1.505 mm at y 18.25..19.75, x 46.49..49.51.
        # U3's port keepout is x 46.5..49.5, y 7.5..12.5: place R9 on it.
        f['R9'].SetPosition(pcb.VECTOR2I(pcb.FromMM(48), pcb.FromMM(10)))
        pcb.SaveBoard(str(p), b)
        self.assertRefused(p, 'sensor port access|courtyard overlap')

    def test_added_copper_is_refused(self):
        p = self.copy('copper')
        b = pcb.LoadBoard(str(p))
        f = {x.GetReference(): x for x in b.GetFootprints()}
        a = [q for q in f['C4'].Pads() if q.GetNumber() == '1'][0]
        c = [q for q in f['U2'].Pads() if q.GetNumber() == '2'][0]
        t = pcb.PCB_TRACK(b)
        t.SetStart(a.GetPosition())
        t.SetEnd(c.GetPosition())
        t.SetWidth(pcb.FromMM(0.2))
        t.SetLayer(pcb.F_Cu)
        t.SetNet(a.GetNet())
        b.Add(t)
        pcb.SaveBoard(str(p), b)
        self.assertRefused(p, 'unrouted')

    def test_second_side_part_is_refused(self):
        p = self.copy('side')
        b = pcb.LoadBoard(str(p))
        f = {x.GetReference(): x for x in b.GetFootprints()}
        f['R9'].Flip(f['R9'].GetPosition(), False)
        pcb.SaveBoard(str(p), b)
        self.assertRefused(p, 'single-sided')

    def test_real_drc_refuses_a_short_on_the_candidate(self):
        """Native DRC, not our own checker, must also reject real copper."""
        p = self.copy('short')
        b = pcb.LoadBoard(str(p))
        f = {x.GetReference(): x for x in b.GetFootprints()}
        pads = {q.GetNumber(): q for q in f['C1'].Pads() if q.GetNumber()}
        a, c = pads['1'], pads['2']
        self.assertNotEqual(a.GetNetname(), c.GetNetname())
        t = pcb.PCB_TRACK(b)
        t.SetStart(a.GetPosition())
        t.SetEnd(c.GetPosition())
        t.SetWidth(pcb.FromMM(0.25))
        t.SetLayer(pcb.F_Cu)
        t.SetNet(a.GetNet())
        b.Add(t)
        pcb.SaveBoard(str(p), b)
        report = self.tmp / 'short-drc.json'
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json',
                        '-o', str(report), str(p)], check=True)
        kinds = {v['type'] for v in json.loads(report.read_text())['violations']}
        self.assertIn('shorting_items', kinds)


if __name__ == '__main__':
    unittest.main(verbosity=2)
