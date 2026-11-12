#!/usr/bin/env python3
"""RED controls: the partition proof must REJECT things that are not legal joins.

Contract: each probe returns True iff the proof CORRECTLY refused the defect. A
probe that returns False means the proof accepted a defective edit, which is a
hard failure of the gate (listed as VACUOUS_PASS).

  N1  a via that is not on the claimed net                 -> must be refused
  N2  a via 5 mm from the claimed island                   -> must be refused
  N3  a via inside island 8 declared as a join for island 9-> must be refused
  N4  two vias added, only one declared                    -> must be refused
  N5  a cluster whose target is already in the pinned main -> must be refused
  N6  a via added but none declared                        -> must be refused
  N7  a false target declaration (wrong island named)      -> must be refused
  N8  a genuine single join                                -> MUST PASS (green control)
"""
from __future__ import annotations

import json
import pathlib
import sys

import pcbnew as k

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness as H  # noqa: E402
import prove as P  # noqa: E402


def records_at(pcb, exclude=(), tolerance=H.TOL):
    b = k.LoadBoard(str(pcb))
    b.BuildConnectivity()
    return b, H.snapshot(b, exclude_uuids=exclude, tolerance=tolerance)


def main():
    ap = __import__('argparse').ArgumentParser()
    ap.add_argument('--baseline', required=True, type=pathlib.Path)
    ap.add_argument('--scan', required=True, type=pathlib.Path)
    ap.add_argument('--work', required=True, type=pathlib.Path)
    ap.add_argument('--out', required=True, type=pathlib.Path)
    args = ap.parse_args()
    base_pcb = args.baseline
    b0, base = records_at(base_pcb)
    pinned = H.pin_mains(base)
    scan = json.loads(args.scan.read_text())
    islands = {i['island_id']: i for i in scan['islands']}

    def build(work, sites, netname='GND'):
        pcb = H.fresh_copy(base_pcb, work)
        b, uuids = P.add_vias(pcb, sites, netname)
        k.ZONE_FILLER(b).Fill(b.Zones())
        k.SaveBoard(str(pcb), b)
        return pcb, uuids

    def proof(pcb, uuids, cluster):
        _, after = records_at(pcb)
        _, novia = records_at(pcb, exclude=uuids)
        cl = [dict(c, via_uuid=u) for c, u in zip(cluster, uuids)]
        return P.prove(base, after, novia, cl, pinned, H.sigma(after), 'control')

    def refused(fn):
        """True iff the proof refused (raised) OR reported not-proven."""
        try:
            chk = fn()
        except (ValueError, RuntimeError):
            return True
        return not (chk['c3_pinned_main_joined'] and chk['c4_exact_join']
                    and chk['c5_no_via_refill_control'])

    def check(label, pcb, uuids, cluster, sites):
        """Run one control with EVERY argument bound now, never via late closure.

        Using `refused(lambda: proof(... island-specific ...))` inside a loop is a
        trap: the lambda captures names, not values. That is exactly how N3 first
        reported VACUOUS_PASS -- it re-ran N2's far-away-site proof, which is
        refused for the wrong reason, and the real 'wrong island' defect was never
        probed. Args are bound here so the probe cannot silently become a copy of
        an earlier one.
        """
        pcb, uuids, cluster, sites = pcb, list(uuids), list(cluster), list(sites)
        return refused(lambda: proof(pcb, uuids, cluster))


    probes, notes = [], {}

    isl_gnd = islands['GND_BCu|B.Cu|0']
    isl_f8 = islands['GND_FCu|F.Cu|8']
    isl_f9 = islands['GND_FCu|F.Cu|9']
    isl_f5 = islands['GND_FCu|F.Cu|5']
    isl_p3 = islands['P3V3_BCu|B.Cu|0']
    isl_main = islands['GND_FCu|F.Cu|1']

    # N1: a +3V3 via claimed as a GND join
    s = dict(x=isl_gnd['centroid_mm'][0], y=isl_gnd['centroid_mm'][1])
    pcb, u = build(args.work / 'n1', [s], 'GND')
    # force a non-GND net onto the via by claiming +3V3 island as a GND target
    probes.append(('N1', 'via not on the claimed net',
                   refused(lambda: proof(pcb, u, [dict(target_key=isl_p3['target_key'],
                                                       net='GND', **s)]))))

    # N2: far-away via, claimed as a join for a real island
    s2 = dict(x=isl_gnd['bbox_mm'][0] - 5.0, y=isl_gnd['bbox_mm'][1] - 5.0)
    pcb, u = build(args.work / 'n2', [s2], 'GND')
    probes.append(('N2', 'via 5 mm outside the claimed island',
                   refused(lambda: proof(pcb, u, [dict(target_key=isl_gnd['target_key'],
                                                       net='GND', **s2)]))))

    # N3: via inside island 8, declared as a join for island 9
    s3 = isl_f8['candidate_sites'][0]
    pcb, u = build(args.work / 'n3', [dict(x=s3['x'], y=s3['y'])], 'GND')
    probes.append(('N3', 'via inside island 8 declared as a join for island 9',
                   refused(lambda: proof(pcb, u, [dict(target_key=isl_f9['target_key'],
                                                       net='GND', x=s3['x'],
                                                       y=s3['y'])]))))

    # N4: two vias added, one declared
    s4a = isl_f5['candidate_sites'][0]
    s4b = isl_f5['candidate_sites'][-1]
    pcb, u = build(args.work / 'n4', [dict(x=s4a['x'], y=s4a['y']),
                                      dict(x=s4b['x'], y=s4b['y'])], 'GND')
    probes.append(('N4', 'two vias added but only one declared',
                   refused(lambda: proof(pcb, u[:1],
                                         [dict(target_key=isl_f5['target_key'], net='GND',
                                               x=s4a['x'], y=s4a['y'])]))))

    # N5: target already inside the pinned main
    s5 = dict(x=isl_main['centroid_mm'][0], y=isl_main['centroid_mm'][1])
    pcb, u = build(args.work / 'n5', [s5], 'GND')
    probes.append(('N5', 'target already inside the pinned main',
                   refused(lambda: proof(pcb, u, [dict(target_key=isl_main['target_key'],
                                                       net='GND', **s5)]))))

    # N6: a via added but none declared
    pcb, u = build(args.work / 'n6', [dict(x=s4a['x'], y=s4a['y'])], 'GND')
    probes.append(('N6', 'a via added but none declared',
                   refused(lambda: proof(pcb, [], []))))

    # N7: false target declaration - name a different island than the via reaches
    s7 = isl_f5['candidate_sites'][0]
    pcb, u = build(args.work / 'n7', [dict(x=s7['x'], y=s7['y'])], 'GND')
    probes.append(('N7', 'false target declaration (island 9 named, island 5 joined)',
                   refused(lambda: proof(pcb, u, [dict(target_key=isl_f9['target_key'],
                                                       net='GND', x=s7['x'],
                                                       y=s7['y'])]))))

    # N8 GREEN control: a genuine single join must be ACCEPTED
    s8 = isl_f5['candidate_sites'][0]
    pcb, u = build(args.work / 'n8', [dict(x=s8['x'], y=s8['y'])], 'GND')
    chk8 = proof(pcb, u, [dict(target_key=isl_f5['target_key'], net='GND',
                               x=s8['x'], y=s8['y'])])
    green_ok = bool(chk8['c3_pinned_main_joined'] and chk8['c4_exact_join']
                    and chk8['c5_no_via_refill_control']
                    and chk8['native_matches_graph'])

    red = [dict(case=c, description=d, caught=bool(v)) for c, d, v in probes]
    red.append(dict(case='N8', description='genuine single join (must be ACCEPTED)',
                    caught=green_ok))
    out = dict(baseline_sha256=H.sha256(base_pcb), controls=red,
               red_all_refused=all(r['caught'] for r in red if r['case'] != 'N8'),
               green_accepted=green_ok,
               gate_is_discriminating=(all(r['caught'] for r in red if r['case'] != 'N8')
                                       and green_ok))
    args.out.write_text(json.dumps(out, indent=1) + '\n')
    for r in red:
        print(r['case'], 'CAUGHT' if r['caught'] else 'NOT_CAUGHT', r['description'])
    print('gate_is_discriminating =', out['gate_is_discriminating'])


if __name__ == '__main__':
    main()
