
import pcbnew
b = pcbnew.LoadBoard("docs/analysis/bulk-route-20261107/work.kicad_pcb")
MM = 1e6
bot = []
for fp in b.GetFootprints():
    if fp.IsFlipped():
        p = fp.GetPosition()
        bot.append((fp.GetReference(), str(fp.GetValue())[:20], p.x/MM, p.y/MM,
                    fp.IsExcludedFromBOM(), fp.IsExcludedFromPosFiles()))
print(f'{"ref":10s} {"value":20s} {"x":>7s} {"y":>7s}  status')
for r in sorted(bot):
    st = "DNP" if r[4] else ("handfit" if r[5] else "JLC-PLACED")
    print(f'{r[0]:10s} {r[1]:20s} {r[2]:7.2f} {r[3]:7.2f}  {st}')

print("\n=== wing sockets + board edge reference")
for fp in b.GetFootprints():
    if fp.GetReference().startswith("J_W"):
        p = fp.GetPosition()
        print(f'  {fp.GetReference():6s} ({p.x/MM:6.2f},{p.y/MM:6.2f})  flipped={fp.IsFlipped()}')
bb = b.GetBoardEdgesBoundingBox()
print(f"  edge bbox: x {bb.GetX()/MM:.2f}..{(bb.GetX()+bb.GetWidth())/MM:.2f}  y {bb.GetY()/MM:.2f}..{(bb.GetY()+bb.GetHeight())/MM:.2f}")

print("\n=== radio module bodies (keep-out relevance for what sits BEHIND them)")
for fp in b.GetFootprints():
    r = fp.GetReference()
    if r in ("U2","U3","U_C","U_LORA1280","U1"):
        p = fp.GetPosition()
        bb2 = fp.GetBoundingBox()
        print(f'  {r:11s} centre ({p.x/MM:6.2f},{p.y/MM:6.2f})  '
              f'size {bb2.GetWidth()/MM:5.2f} x {bb2.GetHeight()/MM:5.2f}  flipped={fp.IsFlipped()}')
