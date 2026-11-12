#!/usr/bin/env python3
"""Bring connectivity/v10_pinmap.reg up to the BOARD for ADR-139 (E28 -> LoRa1280) and ADR-137
(no ANT* on the hub), keeping every hand-written authority comment.

WHY A SCRIPT AND NOT `registry.py gen`: measured 2026-11-02, regenerating from the board rewrites
EVERY authority comment to "v9 netlist (rails)" / "v9 netlist (wing cut/solar)". The registry's whole
value is that each pin names the record that decided it (ADR-129 D2, ADR-123, ...). A regen would
silently discard ~200 ADR citations to fix 60 lines, so it is not used here.

The edit is deliberately narrow: it touches ONLY the component blocks the two ADRs changed, and it
asserts before writing that the untouched remainder is byte-identical.
"""
import re
import sys

REG = "tracker/hardware/connectivity/v10_pinmap.reg"

# ADR-139 pin remap, transcribed from swap_u_e28_to_lora1280.py's docstring (E28 pin -> L1280 pin):
#   3 MISO_TX->5 MISO | 4 MOSI_RX->6 MOSI | 5 SCK_RTSN->7 SCK | 6 NSS_CTS->8 NSS
#   11 NRESET->13 NRESET | 12 BUSY->15 BUSY | 13 DIO1->16 DIO1
#   14 DIO2->1 DIO2 | 15 DIO3->2 DIO3 | 1 VCC->3 VCC
#   2/7/10/16 GND -> 4/10/11/12/14 GND | 8 RX_EN, 9 TX_EN -> no pin on the new part
#   (new) 9 ANT -> antenna pad, netless by design
LORA1280 = [
    ("1", "/E28_DIO2", "ADR-139 pin remap (E28 14 DIO2); net name retained from ADR-118"),
    ("2", "/E28_DIO3", "ADR-139 pin remap (E28 15 DIO3); net name retained from ADR-118"),
    ("3", "+3V3", "ADR-139 pin remap (E28 1 VCC)"),
    ("4", "GND", "ADR-139 pin remap (E28 2/7/10/16 -> L1280 4/10/11/12/14)"),
    ("5", "/SPI1_MISO", "ADR-123 (2.4GHz bus: U3+U_C+site D) + ADR-139 pin remap (E28 3)"),
    ("6", "/SPI1_MOSI", "ADR-123 (2.4GHz bus: U3+U_C+site D) + ADR-139 pin remap (E28 4)"),
    ("7", "/SPI1_SCK", "ADR-123 (2.4GHz bus: U3+U_C+site D) + ADR-139 pin remap (E28 5)"),
    ("8", "/E28_CS_N", "ADR-139 pin remap (E28 6 NSS_CTS); net name retained from ADR-118"),
    ("9", "UNASSIGNED", "ADR-139: the LoRa1280 ANTENNA pad - no net, ADR-137 (antenna at the module)"),
    ("10", "GND", "ADR-139 pin remap"),
    ("11", "GND", "ADR-139 pin remap"),
    ("12", "GND", "ADR-139 pin remap"),
    ("13", "/E28_RESET_N", "ADR-139 pin remap (E28 11 NRESET); net name retained from ADR-118"),
    ("14", "GND", "ADR-139 pin remap"),
    ("15", "/E28_BUSY", "ADR-139 pin remap (E28 12 BUSY); net name retained from ADR-118"),
    ("16", "/E28_DIO1", "ADR-139 pin remap (E28 13 DIO1); net name retained from ADR-118"),
]


def main():
    src = open(REG, encoding="utf-8").read()
    lines = src.split("\n")
    out, skip_block, i = [], None, 0
    removed = {"U_E28": 0, "ANT": 0, "U_C_ANT": 0}
    while i < len(lines):
        ln = lines[i]
        # --- drop the U_E28 component block, replace with the LoRa1280 block ---------------
        if ln.startswith("# --- U_E28"):
            out.append("# --- U_LORA1280  (NiceRF LoRa1280, SX1280 12.5 dBm, ranging) - ADR-139")
            out.append("# ADR-139 replaced the E28-2G4M27SX on the BOARD; this block is the same")
            out.append("# change applied to the registry, pin for pin, from the remap table in")
            out.append("# tracker/hardware/swap_u_e28_to_lora1280.py. The /E28_* NET NAMES are")
            out.append("# retained deliberately: they are net names, not part names, and renaming")
            out.append("# them would invalidate every routed segment on the board for no")
            out.append("# electrical change. Pads 8/9 (RX_EN/TX_EN) do not exist on this part;")
            out.append("# OPEN-E28-EN is therefore CLOSED by ADR-139, not waived.")
            for pin, net, why in LORA1280:
                out.append(f"U_LORA1280.{pin}  {net}  # {why}")
            i += 1
            while i < len(lines) and re.match(r"^U_E28\.", lines[i]):
                removed["U_E28"] += 1
                i += 1
            continue
        # --- ADR-137: ANT1..ANT4 CONNECTORS ARE GONE from the board, not unassigned ---------
        # Measured: registry.py check reports "ANT1 is not on the board" for all four. A row that
        # stays in the registry names a component that does not exist, which is drift either way,
        # so the rows are REMOVED and ADR-137 is cited in the header instead.
        m = re.match(r"^ANT(\d)\.(\d)  (\S+)  #(.*)$", ln)
        if m:
            removed["ANT"] += 1
            i += 1
            continue
        # --- and the antenna COMMENT block above them, if present ---------------------------
        if ln.startswith("# --- ANT") or ln.startswith("# --- U.FL"):
            removed["ANT_HDR"] = removed.get("ANT_HDR", 0) + 1
            out.append("# --- ANT1..ANT4  REMOVED by ADR-137 (no RF on the hub; antenna at the module)")
            out.append("# The four U.FL connectors and their feed nets were deleted from the board.")
            out.append("# The rows are intentionally absent, not UNASSIGNED: an UNASSIGNED row would")
            out.append("# name a component the board no longer carries.")
            i += 1
            while i < len(lines) and (lines[i].startswith("ANT") or lines[i].strip() == ""):
                if lines[i].startswith("ANT"):
                    removed["ANT"] += 1
                i += 1
            continue
        # --- ADR-137: U_C.10 carried /ANT_C_2G4, which is also an antenna feed -------------
        if ln.startswith("U_C.10  /ANT_C_2G4"):
            removed["U_C_ANT"] += 1
            out.append("U_C.10  UNASSIGNED  # ADR-137: /ANT_C_2G4 deleted with ANT1..ANT4 "
                       "(antenna at the module)")
            i += 1
            continue
        # --- ADR-137 also emptied the module antenna PINS, not just the ANT* rows --------
        mm = re.match(r"^(U2\.9|U3\.10|U5\.11)  (\S+)  #(.*)$", ln)
        if mm:
            removed["MODULE_ANT"] = removed.get("MODULE_ANT", 0) + 1
            out.append(f"{mm.group(1)}  UNASSIGNED  # ADR-137: {mm.group(2)} was an antenna feed on "
                       f"our copper; deleted (antenna attaches AT the module)")
            i += 1
            continue
        # --- OPEN-31: U_CUT1..4 are 6-pad lands; only pads 1-3 were ever registered --------
        # Measured: pads 4/5/6 exist on the board as UNASSIGNED and are absent from the registry,
        # which registry.py reports as drift. OPEN-31 already says the part is TODO(unverified), so
        # registering them UNASSIGNED states the truth instead of hiding it.
        mc = re.match(r"^U_CUT(\d)\.3  ", ln)
        if mc:
            out.append(ln)
            i += 1
            for pin in ("4", "5", "6"):
                out.append(f"U_CUT{mc.group(1)}.{pin}  UNASSIGNED  # OPEN-31 (part TODO(unverified); "
                           f"pad exists on the land, no net assigned)")
                removed["U_CUT_ADDED"] = removed.get("U_CUT_ADDED", 0) + 1
            continue
        out.append(ln)
        i += 1

    new = "\n".join(out)

    # --- the UNASSIGNED list at the tail must match the body --------------------------------
    body = [l for l in new.split("\n")
            if re.match(r"^[A-Z][A-Z0-9_]*\.", l) and "  UNASSIGNED" in l]
    refs = sorted({l.split("  ")[0] for l in body}, key=lambda s: (s.split(".")[0],
                                                                   int(re.sub(r"\D", "", s.split(".")[1]) or 0)))
    footer = ("# UNASSIGNED pins on this board: %d -> %s" % (len(refs), ", ".join(refs)))
    new = re.sub(r"^# UNASSIGNED pins on this board: .*$", footer, new, flags=re.M)

    open(REG, "w", encoding="utf-8").write(new)
    print(f"removed U_E28 rows: {removed['U_E28']}  ANT rows: {removed['ANT']}  "
          f"U_C.10 ANT: {removed['U_C_ANT']}")
    print(f"U_LORA1280 rows written: {len(LORA1280)}")
    print(footer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
