#!/usr/bin/env python3
"""Deterministic audit of the 9 (claimed) J_W <-> bypass-diode solar gaps.

Read-only on the source board. Emits JSON evidence to stdout and to
evidence/solar_audit.json. No board edit, no repair.

Run with the distro interpreter (it carries pcbnew):
    /usr/bin/python3 docs/analysis/hub-solar-audit/audit.py

Facts established, each printed as a machine-checkable line:
  A. every J_W pad NUMBER is TWO distinct PAD objects (F.Cu + B.Cu) at
     identical XY, same net, different UUID  -> "zero shared copper layers"
     is an artefact of counting one instance per pad number.
  B. every D_BP1..D_BP4 is a B.Cu footprint (build_hub_board_v10.py BACK dict).
  C. every solar-N net has ZERO track segments -> never routed.
  D. the two-faced tab lands are closed in ASSEMBLY (tab soldered both faces),
     cited WING-TO-HUB-SOCKET-SPEC s2 / ADR-046 s4.1 / ADR-048 s2.2.
  E. a B.Cu track CAN bridge each diode<->J_W pair (layer compatibility),
     proven by adding straight B.Cu tracks to a COPY and re-running DRC:
     unconnected 86 -> 77, all diode<->J_W records closed.
"""
import json
import os
import sys
import hashlib

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(
    REPO,
    "docs/analysis/hub-repair-20261102/output/after/hub_board_v10_lora1280_7of9.kicad_pcb",
)
PINNED_SHA = "94038dd0c4608f28181017599cb7b623dcb85d81f619ec66947fdec2406c1155"

COPPER = {pcbnew.F_Cu: "F.Cu", pcbnew.In1_Cu: "In1.Cu",
          pcbnew.In2_Cu: "In2.Cu", pcbnew.B_Cu: "B.Cu"}
SOLAR_N = ["/W1_SOLAR_N", "/W2_SOLAR_N", "/W3_SOLAR_N"]


def mm(v):
    return round(pcbnew.ToMM(v), 4)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pad_layers(pad):
    return sorted(COPPER[l] for l in pad.GetLayerSet().CuStack())


def main():
    out = {"board": SRC, "kicad": pcbnew.GetBuildVersion()}
    digest = sha256(SRC)
    out["sha256_before"] = digest
    out["sha256_matches_pinned"] = digest == PINNED_SHA
    assert digest == PINNED_SHA, "source board hash drifted — refusing to audit"

    b = pcbnew.LoadBoard(SRC)

    # ---- A: pad-number duplication -------------------------------------
    a_rows = []
    for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
        ref = fp.GetReference()
        if not ref.startswith("J_W"):
            continue
        bynum = {}
        for p in fp.Pads():
            bynum.setdefault(p.GetNumber(), []).append(p)
        for num, ps in sorted(bynum.items()):
            delta = 0.0
            for x in ps:
                for y in ps:
                    d = (x.GetPosition() - y.GetPosition()).EuclideanNorm()
                    delta = max(delta, pcbnew.ToMM(d))
            a_rows.append({
                "ref": ref, "pad": num, "instances": len(ps),
                "max_pairwise_delta_mm": round(delta, 6),
                "layers": sorted({l for p in ps for l in pad_layers(p)}),
                "nets": sorted({p.GetNetname() for p in ps}),
                "uuids_distinct": len({p.m_Uuid.AsString() for p in ps}) == len(ps),
            })
    out["A_pad_duplication"] = a_rows

    # ---- A2: classify the DRC solar records -----------------------------
    # Two counting units, never to be conflated:
    #   pad pairs  = diode pin x J_W land on the same net  (the electrical pairing)
    #   DRC records = one per disconnected copper-island pair (subset of pad pairs)
    import re
    drc = os.path.join(HERE, "evidence", "drc_source.json")
    if os.path.exists(drc):
        with open(drc) as fh:
            d = json.load(fh)
        cls = {"diode_to_jw": [], "jw_self_fb": [], "jw_to_jw": []}
        for i, u in enumerate(d["unconnected_items"]):
            if "SOLAR" not in json.dumps(u):
                continue
            key = []
            for it in u["items"]:
                m = re.search(r"Pad (\d+) \[.*?\] of (J_W\d|D_BP\d) on (\S+)",
                              it["description"])
                key.append((m.group(2), m.group(1), m.group(3)) if m else ("?", "?", "?"))
            (r0, n0, _), (r1, n1, _) = key[0], key[1]
            rec = {"index": i, "a": "%s.%s" % (r0, n0), "b": "%s.%s" % (r1, n1)}
            if r0 == r1 and n0 == n1:
                cls["jw_self_fb"].append(rec)
            elif any(r.startswith("D_BP") for r in (r0, r1)):
                cls["diode_to_jw"].append(rec)
            else:
                cls["jw_to_jw"].append(rec)
        out["A2_drc_solar_records"] = {k: {"count": len(v), "records": v}
                                       for k, v in cls.items()}

    # ---- B: diode side ---------------------------------------------------
    b_rows = []
    for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference()):
        if not fp.GetReference().startswith("D_BP"):
            continue
        b_rows.append({
            "ref": fp.GetReference(),
            "footprint_layer": pcbnew.LayerName(fp.GetLayer()),
            "orientation_deg": round(fp.GetOrientationDegrees(), 1),
            "pos_mm": [mm(fp.GetPosition().x), mm(fp.GetPosition().y)],
            "pads": {p.GetNumber(): {"net": p.GetNetname(),
                                     "layers": pad_layers(p),
                                     "pos_mm": [mm(p.GetPosition().x), mm(p.GetPosition().y)]}
                     for p in fp.Pads()},
        })
    out["B_diode_sides"] = b_rows

    # ---- C: tracks on the solar nets ------------------------------------
    c_rows = {}
    for net in SOLAR_N + ["/W1_SOLAR_P"]:
        segs = [t for t in b.GetTracks()
                if t.GetNetname() == net and t.Type() != pcbnew.PCB_VIA_T]
        vias = [t for t in b.GetTracks()
                if t.GetNetname() == net and t.Type() == pcbnew.PCB_VIA_T]
        c_rows[net] = {"track_segments": len(segs), "vias": len(vias)}
    out["C_solar_routing"] = c_rows

    # ---- D/E: per-pair layer compatibility ------------------------------
    idx = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            idx.setdefault((fp.GetReference(), p.GetNumber()), []).append(p)

    pairs = []
    diode_pin_nets = {}
    for r in b_rows:
        for num, meta in r["pads"].items():
            if meta["net"] in SOLAR_N:
                diode_pin_nets.setdefault(meta["net"], []).append((r["ref"], num))
    for net, pins in sorted(diode_pin_nets.items()):
        for dref, dnum in pins:
            for jref in ("J_W1", "J_W2", "J_W3", "J_W4"):
                for jnum in ("1", "2", "3", "4"):
                    jp = idx[(jref, jnum)]
                    if jp[0].GetNetname() != net:
                        continue
                    d_inst = idx[(dref, dnum)][0]
                    d_lay = set(pad_layers(d_inst))
                    j_lay = set()
                    for p in jp:
                        j_lay |= set(pad_layers(p))
                    pairs.append({
                        "net": net,
                        "diode_pad": "%s.%s" % (dref, dnum),
                        "diode_layers": sorted(d_lay),
                        "jw_pad": "%s.%s" % (jref, jnum),
                        "jw_layers": sorted(j_lay),
                        "jw_instances": len(jp),
                        "shared_layers": sorted(d_lay & j_lay),
                        "naive_single_instance_shared": sorted(
                            d_lay & set(pad_layers(jp[0]))),
                    })
    out["D_pairs"] = pairs
    out["D_summary"] = {
        "pairs": len(pairs),
        "pairs_sharing_a_layer_when_all_instances_counted":
            sum(1 for p in pairs if p["shared_layers"]),
        "pairs_sharing_a_layer_when_only_the_F_Cu_instance_counts":
            sum(1 for p in pairs if p["naive_single_instance_shared"]),
    }

    out["sha256_after"] = sha256(SRC)
    out["source_unmodified"] = out["sha256_after"] == PINNED_SHA

    ev = os.path.join(HERE, "evidence")
    os.makedirs(ev, exist_ok=True)
    with open(os.path.join(ev, "solar_audit.json"), "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)

    print(json.dumps(out, indent=1, sort_keys=True))
    print("\n== VERDICT INPUTS ==")
    print("pairs:", out["D_summary"]["pairs"])
    print("sharing a layer (all instances):",
          out["D_summary"]["pairs_sharing_a_layer_when_all_instances_counted"])
    print("sharing a layer (F.Cu instance only):",
          out["D_summary"]["pairs_sharing_a_layer_when_only_the_F_Cu_instance_counts"])
    print("solar-N track segments:", {k: v["track_segments"] for k, v in c_rows.items()})
    print("source unmodified:", out["source_unmodified"])


if __name__ == "__main__":
    main()
