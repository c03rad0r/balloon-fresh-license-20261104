# Wing interconnect diode polarity evidence

Checked 2026-11-10 against source HEAD `299e37909a543767c4cb792c5653929483b06290`. Initial worktree clean; process command-line scan showed no other wing-fab writer (a snapshot, not an exclusive lock). No board/copper, carrier exports, or v10 tags changed.

## Component and physical polarity

[LCSC C50645](https://www.lcsc.com/product-detail/C50645.html) and [JLC C50645](https://jlcpcb.com/partdetail/MDD-SS24/C50645) identify **MDD SS24, SMA (DO-214AC), 2 A, 40 V** (not SS14).

Actual MDD manufacturer document obtained from [distributor-hosted C50645 PDF](https://robu-prod-media.s3.ap-south-1.amazonaws.com/uploads/2025/08/C50645.pdf): *SS22 THRU SS2200*, Rev 2024A3, p1, Mechanical Data: **“Polarity: Color band denotes cathode end.”** Opposite end is anode. The sheet labels the SS24 marking MDD SS24. PDF SHA256 `95e1d41248fcb4282cb35b5ec310b162fedf5df91980b2d705a420d66cedd1be` (1,344,954 bytes). The LCSC-linked PDF and unsigned JLC object URL returned HTTP 403; this is a manufacturer-authored document retrieved through a distributor mirror, not a successful manufacturer-domain fetch.

Do not infer a manufacturer pin number from this two-terminal mechanical drawing: **pad 1 = K is the board/footprint convention**, implemented by placing the physical banded end onto pad 1.

## Measured board mapping

Absolute PCB XY in mm, front face; all three native footprint rotations 0 degrees:

| Ref | anchor | pad 1 / required banded cathode | pad 2 / anode |
|---|---|---|---|
| D1 | (14,6) | (12.15,6) SOLAR_P | (15.85,6) SOLAR_MID1 |
| D2 | (22,6) | (20.15,6) SOLAR_MID1 | (23.85,6) SOLAR_MID2 |
| D3 | (30,6) | (28.15,6) SOLAR_MID2 | (31.85,6) SOLAR_N |

Thus banded ends must face decreasing board X. Cathodes connect to the more-positive node of each cell segment; anodes connect to the next lower node. With normal cell voltage these diodes are reverse biased; with a reversed/shaded segment they provide forward bypass from its lower node to upper node. This confirms the intended net-to-terminal topology, not a fresh copper-connectivity audit.

The existing native KiCad CPL writer preserves footprint anchor/angle and transforms board Y=6 to placement Y=-6: expected top placements `(14,-6,0)`, `(22,-6,0)`, `(30,-6,0)`. **Native 0 degrees does not establish JLC's package-model 0 degrees.** Public JLC text identifies the part but supplies no verified zero-angle polarity binding; no authenticated assembly preview was exercised.

### Still-required assembly acceptance

Upload the exact interconnect Gerbers/BOM/CPL to Standard PCBA preview and select **C50645/MDD SS24**. For EACH D1-D3, verify the model's banded cathode overlaps the pad-1 coordinates/nets in the table, looking from the front (not a mirrored bottom view). Save a preview screenshot/order revision or written JLC engineering confirmation naming all three refs and cathode nets. If the model is ambiguous, request that explicit terminal-to-land confirmation from JLC; do not guess a 180-degree correction from generic SMA conventions. This is the remaining assembly-orientation gate, not closed by this report.

## Regression gate

`verify_bypass_polarity()` checks all three K/pad1 and A/pad2 net mappings before interconnect build deletes/writes output. Tests load the real board as GREEN, then independently swap each diode's two pad nets in memory: each RED control raises the named polarity error. No mutated PCB is saved.

`/usr/bin/python3 tests/test_wing_order_export.py`: **4 tests passed**, exit 0, including all three reversed-polarity subcases and existing paste/native-origin tests. `/usr/bin/python3 -m pytest` could not run because that interpreter lacks pytest; unittest is the actual successful execution.

## 0.4 mm Standard assembly: supported category, acceptance pending

Primary [JLC assembly capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities), fetched 2026-11-10: Economic thickness **0.8–1.6 mm**; Standard thickness **“No limit”**. Standard single-board minimum **70×70 mm**, panel range **70×70–250×250 mm**, with **edge rails and fiducials necessary**. Hence 0.4 mm is not excluded by Standard's published thickness category, but this does NOT approve the bare 34.6×20 mm board for unsupported single-piece conveyance.

Require JLC acceptance of a repeated-board panel/rail arrangement within Standard dimensions, fiducials/tooling, thin-board support/fixture during paste and reflow, depanelization method compatible with 0.4 mm and the connector edge, and the actual 2-layer 0.4 mm fabrication stackup. Retain the accepted panel drawing and quotation/engineering response. Panelization is a plausible route, not an impossibility and not yet manufacturer acceptance. No purchase or readiness claim is made.
