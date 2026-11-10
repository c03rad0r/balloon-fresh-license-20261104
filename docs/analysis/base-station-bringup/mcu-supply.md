# Base MCU supply — logical block only, NOT FAB READY

Based on live master `85f0637e` (merged #533); isolated `pr/base-mcu-supply`.
Open PR census (limit 200) found no competing MCU-supply implementation;
legacy consolidation #420 is the D14 freeze, not this power block.

## DECISIONS

Select **AP2112K-3.3TRG1**, fixed 3.3 V, Diodes SOT25 (KiCad SOT-23-5),
for the existing 5 V-to-MCU branch. This is a bounded datasheet-qualified
part/pin/topology selection, NOT qualification of the entire assembled supply.
Unspecified/floating-enable LDO rejected. Separate buck alternative deferred:
at the intended 50 mA allowance LDO loss is small; this decision must be reopened
if measured load/ambient exceeds the envelope below. Do not substitute the
pressure-controller ESP32 load budget for this RP2040 AGC/telemetry controller.

[Diodes AP2112 DS39724 Rev 2-2, June 2017](https://www.diodes.com/assets/Datasheets/AP2112.pdf):
pp1–2 top-view pinout and typical circuit; p3 recommended/absolute ratings;
p8 3.3 V electrical characteristics; p12 ordering code; p16 SOT25 outline.
Pins **1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT**. Pin4 omitted from connected
netlist nodes, not grounded. EN tied to +5V_PCBA, not MCU software or output:
EN high 1.5–6 V, recommended VIN 2.5–6 V; 6.5 V absolute maximum is not
an operating allowance. Nominal 5 V, RF operating envelope 4.75–5.25 V,
leaves adequate dropout headroom; overshoot/load transient qualification open.

Input/output each have dedicated 2.2 µF/16 V/X7R/10% 0805 design values;
manufacturer recommends 1 µF input/output and X5R/X7R ceramics. Require
**at least 1 µF effective** at 5.25 V input / 3.3 V output after bias,
tolerance, temperature, aging. Exact capacitor MPN/bias curves remain an
explicit BOM release blocker; nominal values do not prove this condition.

[Raspberry Pi Hardware design with RP2040](https://datasheets.raspberrypi.com/rp2040/hardware-design-with-rp2040.pdf),
§2.1.2 pp7–8 and §2.1.3 p8/Figure5 (manufacturer PDF downloaded/text-read):
100 nF per power pin; 1 µF local to VREG_IN and VREG_OUT. Reference shares
48/49 but explicitly identifies that as a compromise; ours provides each.
[RP2040 datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf),
§1.4 Figure3 and §2.9 own physical pads and power domains.

| Supply pin(s) | Rail | Dedicated bypass |
|---|---|---|
| IOVDD 1,10,22,33,42,49 | +3V3_MCU | C_MCU1 at1; C_MCU_Pnn at others, 100 nF each |
| ADC_AVDD43, USB_VDD48 | +3V3_MCU | C_MCU_P43/P48, 100 nF each |
| VREG_IN44 | +3V3_MCU | existing C_MCU2 1 µF |
| VREG_OUT45 | +1V1_CORE | new C_VREG_OUT 1 µF |
| DVDD23,50 | +1V1_CORE | C_MCU_P23/P50 100 nF each |
| flash VCC8 | +3V3_MCU | C_FLASH 100 nF; final flash datasheet still required |

Locality is a **future placement requirement**, not proven by a common-net
capacitor count. No layout was generated or touched.

## What the safety proof does and does not establish

Generated-netlist tests establish no direct 5 V/raw-input/SW connection to ANY
MCU pin, no resistor/bead/inductor direct bridge to an MCU net, correct AP2112
input/output/enable assignment, 3.3 V PG pullup and flash, and exclusive core
supply via VREG_OUT. Thus the intended regulator power-tree topology cannot
**directly wire** 5 V to MCU I/O or core. It is NOT a fault-proof overvoltage
protection design: a failed LDO, back-powered debug probe, incorrect placeholder
RF pinout/DET_VOUT or LNA_FLT interface can still expose the MCU to excess
voltage. Those interfaces and ADC protection remain release blockers. Do not
convert this bounded connectivity proof into a claim of whole-board safety.

## Thermal/load budget: intended load, not invented guarantees

D14/spec.json allocates **50 mA** to RP2040 digital/ADC/SPI. Actual firmware
load is unmeasured; unspecified flash current, GPIO loading, startup charging,
probe current and fault behaviour are not bounded. RF VGA/detector/masthead
loads remain on 5 V, NOT on this LDO. RUN10k contributes up to 0.33 mA when
low; PG100k up to 0.033 mA. Treat 50 mA as the historical MCU allowance,
100/150 mA as sensitivity cases, NOT newly guaranteed maxima.

Use nominal Vout=3.3 V and Vin=5.25 V: P=(Vin−Vout)*I; ΔT=184*P.
Datasheet p3 quotes SOT25 θJA=184°C/W (no heatsink), ambient −40..85°C;
150°C junction is ABSOLUTE maximum. 125°C below is our planning ceiling,
not a manufacturer guarantee. Actual copper/enclosure must be measured.

| Total 3V3 load case | Loss W | Rise °C | Tj at 85°C | Ambient for Tj≤125°C |
|---|---:|---:|---:|---:|
| 50 mA allowance (excluding unbounded extras) | .0975 | 17.94 | 102.94 | 107.06 (still respect 85°C datasheet ambient) |
| 100 mA sensitivity | .195 | 35.88 | 120.88 | 89.12 (still ≤85°C) |
| 150 mA sensitivity | .2925 | 53.82 | 138.82 | 71.18 |

Including −1.5% output accuracy alone gives Vout=3.2505 V and rises
18.40/36.79/55.19°C; this is still not an all-corner model. Ground current
and line/load regulation add loss. Datasheet no-load IQ 55µA typ/80µA max is
specified at 4.3 V: do not advertise it as a worst-case loaded 5.25 V bound.
At 600 mA nominal output rating, simple rise would be 215°C: **not usable here**.
A 150 mA/high-ambient application needs reconsideration/measurement, not a
claim that the 600 mA label establishes thermal margin.

Upstream #533 budget `322.5+50=372.5 mA`, ×1.25=465.625 mA omitted extras.
At total 3V3 100/150 mA, it becomes **528.125/590.625 mA** with that same
25% margin (LDO input approximately equals output current, NOT power-ratio
scaled). Detector hot slope adds another 11.25 mA to margined figures.
So higher MCU allocations no longer fit the earlier 0.5 A design envelope;
1 A buck nameplate does not close passive/thermal/fault qualification.

## Blockers preserved

**9–18 V input requirement remains mandatory and unresolved. TPS62163 allows
only 17 V recommended maximum. Unspecified reverse/TVS protection does not
prove it. Do not energize or order this board.** No deletion/narrowing of the
18 V requirement. Native PCB geometry remains rejected, no PCB regeneration,
no routing, no v10 changes, no purchase/actuation. Still no authoritative
native base schematic/ERC. Exact flash, capacitor qualification, RF pinmaps,
analog interfaces, load limiting and no-LNA-fault MCU survival remain open.

## Observed tests / reproduce

New test runs the actual generator in a temporary directory and parses its
output, then checks committed-netlist parity. RED: 7 tests, **5 failures**
(wrong part, floating EN/grounded NC, underspecified caps, missing per-pin and
VREG_OUT bypass); unchanged isolation/parity checks passed. GREEN: **7/7**;
existing buck tests **7/7**; package-pin tests **9/9**; legacy topology **25/25**.
Generator now **53 components, 40 nets**. Legacy test labels claiming fault
survival and historical 316 mA budget are not electrical signoff.

```
python3 tracker/hardware/base_station/gen_base_station_netlist.py
python3 tracker/hardware/base_station/test_mcu_supply.py
python3 tracker/hardware/base_station/test_5v_supply.py
python3 -m unittest discover -s tracker/hardware/base_station -p 'test_*pinmap.py'
python3 tracker/hardware/base_station/test_netlist_implements_spec.py
```

Read-only pre-decision consultant verified pinout, capacitance and thermal
limits. Runtime reports `tier/delegation` only: no served family identity,
so **not claimed as cross-family review**; independent parent review required.
