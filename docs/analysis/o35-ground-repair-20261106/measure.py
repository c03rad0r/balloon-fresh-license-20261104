exec(open(__file__.replace('measure.py','probe.py')).read().split("b=p.LoadBoard")[0])
delta={n:{'export_only':sorted(nets['export'].get(n,set())-nets['committed_netlist'].get(n,set())),'committed_only':sorted(nets['committed_netlist'].get(n,set())-nets['export'].get(n,set()))} for n in nets['export'].keys()|nets['committed_netlist'].keys() if nets['export'].get(n)!=nets['committed_netlist'].get(n)}
b=p.LoadBoard(str(B)); pad=next(q for f in b.GetFootprints() if f.GetReference()=='D_BP4' for q in f.Pads() if q.GetNumber()=='2'); via=next(t for t in b.GetTracks() if t.m_Uuid.AsString()=='ada07303-f780-4328-8252-828fab20734c')
ps=pad.GetEffectivePolygon(p.B_Cu); coords=[(v.x/1e6,v.y/1e6) for v in ps.COutline(0).CPoints()]
from shapely.geometry import Polygon,Point
poly=Polygon(coords); radius=via.GetWidth(p.B_Cu)/2e6
r={'stale_committed_netlist_delta':delta,'pad_bounds_mm':poly.bounds,'existing_via_diameter_mm':2*radius,'existing_via_drill_mm':via.GetDrillValue()/1e6,'via_edge_to_pad_copper_mm':poly.distance(Point(via.GetPosition().x/1e6,via.GetPosition().y/1e6))-radius,'added_track_length_mm':2.040292,'new_vias':0}
(O/'measurement.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
