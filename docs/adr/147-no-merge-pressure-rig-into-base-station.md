# ADR-147 — Do not merge the pressure rig into the base station; order separate boards in one basket

**Status:** ACCEPTED · 2026-11-10 · supersedes the assumption that the base station carries an ESP32

## Context

Operator proposal, in full:

> 1. Pressure only (BMP280) — matches the existing firmware and protocol doc
> its safe to assume that the pressure will leak out so we can just run the pump to maintain the
> pressure without needing a release valve
> 3. Assembled, S3 module hand-fit by me (cheaper, Economic tier)
> ...
> How about we combine the pressurizing board with the base station board so that we dont need to
> manufacture as many boards. The pressure sensors for pressurizing the balloon could share the same
> esp32 s3 as the base station uses...
> How about we also put the solar panel hub circuits that connect the solar cells of the wing on the
> base station as well? Would it make sense to make them casselated so that we can break them off
> if needed?
> I would like to avoid a separate round of shipping costs just for the interconnects.

Four questions, one goal: **one order, one shipment, fewer boards.**

## Decision 1 — REJECT the merge. The base station has no ESP32.

Measured on `tracker/hardware/base_station/base_station_v1_placed_v2.kicad_pcb`:

```
board      70.2 x 50.1 mm
footprints 44      tracks 0      nets 44
U_MCU      RP2040 QFN-56                     70 pads
U_VGA      ADL5240 VGA (93 mA @ 4.75-5.25 V) 42 pads
U_DET      AD8318ACPZ-R7 log detector        21 pads
FLT_433_A  433 MHz BPF (ahead of LNA)         6 pads
FLT_433_B  433 MHz BPF #2 (before AD8318)     6 pads
TEE1/TEE2  ZFBT-4R2GW+ bias tees              3 pads
J_LNA_FEED coax feed to masthead LNA (SMA)
J_433_RX   433 MHz RX (SMA)
J_PWR      VIN_GS 9-18 V input
```

**The base station's MCU is an RP2040, not an ESP32.** An ESP32 search over every footprint returns
nothing. So the premise *"the pressure sensors could share the same ESP32-S3 as the base station
uses"* is not available — there is no S3 on that board, and the MCU it does carry is occupied driving
RF gain control (`ADL5240` gain from RP2040).

It is also a **433 MHz RF receive front end** with two band-pass filters, a masthead LNA feed and bias
tees. Merging a **330 mA WiFi transmitter** and a **0.5 mbar/h pressure instrument** onto the same
board as a low-noise RF receiver is the worst combination available in this project:

- the pressure rig's whole job is resolving sub-mbar pressure; a TX burst on the same ground plane
  is the noise source it most needs kept away from;
- the base station's whole job is low-noise 433 MHz receive; a 2.4 GHz radio beside it is the
  aggressor it most needs kept away from.

These are the two designs in the project that most want to be **apart**. Merging them would put a
WiFi radio next to an LNA.

## Decision 2 — The cost goal is met WITHOUT merging: separate boards, one basket, one shipment

From JLCPCB's own help centre, *"How to order multiple different PCBs together"*:

> JLCPCB allows you to order many different PCBs together. Just click '+Add new item' and add the PCBs
> to your cart one by one. Finally, proceed to pay for all of them together.

So **one order, one payment, one shipment** already supports many distinct designs. The operator's
stated objective — *"avoid a separate round of shipping costs just for the interconnects"* — is
satisfied by putting the interconnect in the same basket as the hub and the rig. **No merge needed.**

Conversely, merging designs into a single gerber set is the *expensive* path. JLCPCB support
documented it directly: *"Some customers would like to merge more than 1 PCB in the same gerber,
although by doing this, customers just have one order, this complicates the fabrication of the panel.
Meanwhile, this may make it hard to cut the board outline. So we usually charge more for this."*

## Decision 3 — REJECT castellated break-off wings

Four independent reasons, all measured or documented:

1. **Cost, twice.** JLCPCB charges extra for castellated holes and extra again for multiple designs
   in one file. Break-off wings pay both.
2. **Edge rails collide with edge-launched features.** Standard PCBA adds 5 mm rails on the short
   sides — the exact interaction flagged as an unresolved risk on the v10 order, where `J_W1`/`J_W3`
   castellations sit at x=0 and x=72.
3. **Assembly setup is not reduced.** PCBA setup is charged per side per design ($25 Standard). Moving
   a circuit onto another board's file does not merge that charge; the wing circuit is its own design
   either way.
4. **Debug cost is asymmetric.** A wrong break-off wastes the whole panel; a wrong small board wastes
   one small board. This phase is explicitly about *"testing our components and circuit boards"*.

## Decision 4 — Hand-fitting the S3 module: NOT recommended

Measured on `U1` (ESP32-S3-WROOM-1U, 62 pads):

```
thermal pad 41   3.90 x 3.90 mm = 15.2 mm2, net GND
castellated pads 1.50 x 0.90 mm, ~0.70 mm pitch on a row
module body      25.5 x 18.0 mm
```

The castellated edge pads are genuinely hand-solderable. **The 3.90 × 3.90 mm ground pad underneath
is not.** It carries no accessible edge, sits under the module body, and cannot be reached with an
iron — it requires hot air or reflow with paste and preheat. A partially-wetted 15 mm² thermal pad on
an RF module produces exactly the class of fault that costs a day to find: intermittent resets under
TX load, or a module that works cold and drops out warm.

**Recommendation: let JLCPCB place it.** The ESP32-S3-WROOM series is `Standard Only` per JLCPCB's own
part data, so Standard PCBA is required regardless; the incremental cost over Economic on a board this
small is far below the cost of one bad reflow. Assembly tier: **Standard**.

## Decision 5 — SUPERSEDED: pump-only control is not complete pressure protection

**Operator-approved correction, 2026-11-10:** [Differential pressure basis](../prestretch/DIFFERENTIAL-PRESSURE-BASIS.md) supersedes the safety reasoning in this section and corresponding consequences. Retain one electrically controlled pump, but require independent passive relief and a verified pump-off interlock. Natural leakage is not a safety mechanism; a pull-down does not stop firmware actively holding a GPIO high. The original rationale below is historical, NOT implementation authority. Other decisions remain unchanged.

### Historical rationale (withdrawn)

The operator's reasoning is sound and it simplifies the hardware:

> its safe to assume that the pressure will leak out so we can just run the pump to maintain the
> pressure without needing a release valve

A rig that can only add gas needs **one** actuator, not two, and the fail-safe direction is trivial:
**pump OFF is safe.** That is strictly better than the earlier valve-based design:

- no NC solenoid to source, so **the blocking question — valve voltage and coil current — disappears**;
- no flyback diode, no separate load supply sized for a solenoid;
- a low-side MOSFET with a **gate pull-down** gives the required fail-safe: at reset, brownout or hang
  the gate falls, the pump stops, and no gas is added. The pull-down is the interlock, exactly as
  before, but with one actuator instead of two.

**Retained from the interlock doc:** the pump enable must fail closed, and the alarm must be latched
and prove itself at boot. Both are cheap and both are about faults the MCU cannot report.

**Explicitly out of scope:** pressure is a **leak detector and gross over-inflation guard, never a
setpoint** (protocol §C.3 — a mbar/PSI unit confusion destroyed balloons JR01–JR06). A pump that
maintains pressure must still be gated by a hard ceiling, not by a control loop that trusts the sensor.

## Consequences

- **Board count is unchanged: three.** Hub v11, solar interconnect, pressure rig. All in **one
  JLCPCB basket, one shipment**.
- **The pressure rig gets simpler**, not larger: S3 module, 3.3 V regulator, USB-C, I²C sensor header,
  one pump driver with gate pull-down, latched alarm, no valve, no release valve, no separate
  solenoid supply.
- **The base station is untouched** by this ADR and remains unrouted (0 tracks / 44 footprints); it is
  a separate campaign and is NOT on the critical path for a first flight.
- **The blocking input changes.** The valve question is gone. What remains for the rig is the pump's
  voltage and current — a much easier answer, and the pump is already in the protocol's parts list.

## What would change this decision

- A base station redesign that puts an ESP32-S3 on it **and** moves the RF front end off-board to a
  masthead box. Then merging logic is plausible; the RF separation argument is what forbids it today.
- JLCPCB withdrawing same-cart multi-design ordering, which would make one file economically forced.
- A pump that cannot be switched by a low-side FET (e.g. mains-only), which would move the switching
  function off-board rather than change the board count.
