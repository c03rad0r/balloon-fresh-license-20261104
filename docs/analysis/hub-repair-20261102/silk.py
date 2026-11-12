"""Scan for a legal ${REFERENCE} silk position. Proposal by analytic geometry,
verdict ALWAYS by native DRC. Never moves copper."""
import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
import pcbnew as k

HERE = Path(__file__).resolve().parent
BASE = HERE / 'thermal' / 'after'
STEM = 'hub_board_v10_lora1280_7of9'
BASEPCB = BASE / (STEM + '.kicad_pcb')
BASEPRO = BASE / (STEM + '.kicad_pro')
OUT = HERE / 'silk'
THERMAL = '8bc4428aa4c62f01255ec065cf8033ef74397a51dba74c2c5d200764fd1218cb'
REF = 'U_LORA1280'
TEXT_UUID = 'a9d40fa2-004f-4e15-93bb-ff812bf97689'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tokens(t):
    return re.findall(r'"(?:\\.|[^"\\])*"|[^\s()]+|[()]', t)


def parse(ts):
    root = []
    stack = [root]
    for t in ts:
        if t == '(':
            new = []
            stack[-1].append(new)
            stack.append(new)
        elif t == ')':
            stack.pop()
        else:
            stack[-1].append(t)
    return root


def canonical(text):
    """Only the one target PCB_TEXT block (uuid-addressed) may differ."""
    def norm(node):
        out = []
        for item in node:
            if isinstance(item, list) and item:
                if item[0] == 'fp_text':
                    hit = any(isinstance(g, list) and len(g) == 2 and g[0] == 'uuid' and g[1].strip('"') == TEXT_UUID for g in item if isinstance(g, list))
                    if hit:
                        out.append(['TARGET_TEXT_NORMALIZED'])
                        continue
                out.append(norm(item))
            else:
                out.append(item)
        return out
    return hashlib.sha256(json.dumps(norm(parse(tokens(text))), separators=(',', ':')).encode()).hexdigest()


def identities(d):
    return Counter(json.dumps((v['type'], v['severity'], v['description'], sorted((i['uuid'], i['description']) for i in v['items']))) for v in d['violations'])


def boxes(b):
    """Rects (x0,y0,x1,y1) in mm that the label's silk must avoid."""
    rects = []
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if not pad.IsOnLayer(k.F_Cu):
                continue
            bb = pad.GetBoundingBox()
            m = 0.25  # mask + silk clip margin
            rects.append((bb.GetX()/1e6 - m, bb.GetY()/1e6 - m, bb.GetRight()/1e6 + m, bb.GetBottom()/1e6 + m))
        for it in fp.GraphicalItems():
            if it.GetLayer() == k.F_SilkS and it.m_Uuid.AsString() != TEXT_UUID:
                bb = it.GetBoundingBox()
                m = 0.15
                rects.append((bb.GetX()/1e6 - m, bb.GetY()/1e6 - m, bb.GetRight()/1e6 + m, bb.GetBottom()/1e6 + m))
    for it in b.GetDrawings():
        if it.GetLayer() == k.F_SilkS:
            bb = it.GetBoundingBox()
            rects.append((bb.GetX()/1e6 - 0.15, bb.GetY()/1e6 - 0.15, bb.GetRight()/1e6 + 0.15, bb.GetBottom()/1e6 + 0.15))
    return rects


def outline(b):
    edge = [d for d in b.GetDrawings() if d.GetLayer() == k.Edge_Cuts]
    xs = [p/1e6 for d in edge for p in (d.GetStart().x, d.GetEnd().x) if hasattr(d, 'GetStart')]
    ys = [p/1e6 for d in edge for p in (d.GetStart().y, d.GetEnd().y) if hasattr(d, 'GetStart')]
    return min(xs), min(ys), max(xs), max(ys)


def run(name, pos=None):
    directory = OUT / name
    directory.mkdir(parents=True, exist_ok=True)
    pcb = directory / (STEM + '.kicad_pcb')
    shutil.copy2(BASEPRO, pcb.with_suffix('.kicad_pro'))
    for table in BASE.glob('*lib-table'):
        shutil.copy2(table, directory / table.name)
    b = k.LoadBoard(str(BASEPCB))
    if pos is not None:
        target = [it for it in b.FindFootprintByReference(REF).GraphicalItems() if it.m_Uuid.AsString() == TEXT_UUID]
        assert len(target) == 1
        target[0].SetPosition(k.VECTOR2I(round(pos[0]*1e6), round(pos[1]*1e6)))
        target[0].SetTextAngle(k.EDA_ANGLE(0, k.DEGREES_T))
    k.ZONE_FILLER(b).Fill(b.Zones())
    k.SaveBoard(str(pcb), b)
    assert sha(pcb.with_suffix('.kicad_pro')) == sha(BASEPRO)
    r = subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--severity-all', '--exit-code-violations', '-o', str(directory/'drc.json'), str(pcb)], capture_output=True, text=True)
    assert r.returncode in (0, 5), r.stderr
    (directory/'command.json').write_text(json.dumps(dict(argv=r.args, exit=r.returncode, stdout=r.stdout, stderr=r.stderr), indent=2)+'\n')
    return json.loads((directory/'drc.json').read_text()), pcb


def main():
    assert sha(BASEPCB) == THERMAL, sha(BASEPCB)
    b = k.LoadBoard(str(BASEPCB))
    target = [it for it in b.FindFootprintByReference(REF).GraphicalItems() if it.m_Uuid.AsString() == TEXT_UUID][0]
    bb = target.GetBoundingBox()
    w, h = bb.GetWidth()/1e6, bb.GetHeight()/1e6
    px, py = target.GetPosition().x/1e6, target.GetPosition().y/1e6
    # text is centred on its position
    x0l, y0l, x1l, y1l = outline(b)
    obstacles = boxes(b)
    proposals = []
    step = 0.5
    x = x0l + 1.0
    while x <= x1l - 1.0:
        y = y0l + 1.0
        while y <= y1l - 1.0:
            r = (x - w/2, y - h/2, x + w/2, y + h/2)
            if r[0] > x0l + 0.5 and r[2] < x1l - 0.5 and r[1] > y0l + 0.5 and r[3] < y1l - 0.5:
                if not any(not (r[2] <= o[0] or r[0] >= o[2] or r[3] <= o[1] or r[1] >= o[3]) for o in obstacles):
                    d = ((x-px)**2 + (y-py)**2) ** 0.5
                    proposals.append((round(d, 3), round(x, 3), round(y, 3)))
            y += step
        x += step
    proposals.sort()
    assert proposals, 'analytic scan found no clear rectangle - do not guess'
    (OUT/'analytic_proposals.json').write_text(json.dumps(dict(
        text_bbox_mm=[w, h], origin_mm=[px, py], board_outline=[x0l, y0l, x1l, y1l],
        grid_step_mm=step, obstacle_rects=len(obstacles),
        proposals=[dict(distance_mm=d, x_mm=x, y_mm=y) for d, x, y in proposals[:40]]), indent=2)+'\n')

    before, bpcb = run('baseline')
    base_ids = identities(before)
    tried, chosen = [], None
    for d, x, y in proposals[:6]:
        report, pcb = run(f'cand_{x:.1f}_{y:.1f}', (x, y))
        added = identities(report) - base_ids
        removed = base_ids - identities(report)
        silk = [v for v in report['violations'] if v['type'].startswith('silk')]
        tried.append(dict(x_mm=x, y_mm=y, distance_mm=d, added=len(added), removed=len(removed),
                          silk_after=len(silk), unconnected=len(report['unconnected_items']),
                          board_sha256=sha(pcb)))
        ok = (not added and not silk
              and len(report['unconnected_items']) == len(before['unconnected_items']) == 86)
        if ok and chosen is None:
            chosen = dict(x_mm=x, y_mm=y, distance_mm=d, board_sha256=sha(pcb))
            final, final_pcb = report, pcb
    assert chosen is not None, f'no native-clean candidate among {len(tried)} proposals'
    assert canonical(bpcb.read_text()) == canonical(final_pcb.read_text()), 'NON-TEXT BOARD TOKENS CHANGED'
    evidence = dict(base_sha256=sha(BASEPCB), chosen=chosen, candidate_sha256=sha(final_pcb),
                    canonical_all_tokens_except_target_text_sha256=canonical(bpcb.read_text()),
                    counts=dict(before=dict(Counter(v['type'] for v in before['violations'])),
                                after=dict(Counter(v['type'] for v in final['violations']))),
                    removed=dict(identities(before) - identities(final)),
                    unconnected=86, tried=tried,
                    method='analytic rectangle scan proposes, native DRC decides; a failed site means no legal site in this SAMPLE only')
    (OUT/'evidence.json').write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
