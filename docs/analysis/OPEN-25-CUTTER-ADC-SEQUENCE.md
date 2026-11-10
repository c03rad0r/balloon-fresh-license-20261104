# OPEN-25 power-sequence adjudication

> **BLOCKED — consultant analysis, not schematic approval.** Reject the shared collapsing-rail TMUX1511/ADS1115 architecture as a qualified arbitrary-ramp protection solution. Preserve its useful DC proposal. All v11 features remain in scope; no copper, actuation, merge, or v10 changes.

Base: e4704c63, branch pr/open25-independent-review, PR527 (draft, stacked on PR526).
Worktree: /home/c08r4d0r/worktrees/open25-independent-review.
Preflight: local clean, remote PR head matched, no other worktree owns this branch, no matching open25 worker process and no index lock observed. This is an observational ownership check, not a fleet-wide reservation. No cross-family approval obtained.

## Decision and exact failure

D1. **Reject TPS3808G33 + shared-rail TMUX1511 as closure.** A real candidate would connect SENSE to ADC 3V3, open-drain RESET to SEL (pull-up enabled only by measurement request; never a push-pull GPIO fighting RESET), CT open, common ground. RESET must dominate a stuck-high request. TPS3808 Rev N §6.6 specifies **20 us typical, no maximum** SENSE-to-RESET assertion delay. Its 12..28 ms CT-open delay is reset RELEASE, not fault assertion. Substituting 28 ms or 20 us as the guaranteed assertion delay would be a category error. Even a perfect zero-tolerance threshold cannot protect an arbitrarily fast collapsing ADC supply with finite latency.

D2. **Prefer a separately held-up ADC/protection domain as the safer candidate, not a qualified selection.** Feed ADS1115, switch and detector from an isolated retained rail; detect failure on the upstream rail, disconnect the analog input while retained supply is still valid, discharge the ADC input, then remove retained power. A reverse-blocking supply path is essential: a capacitor connected to the failing shared rail is not hold-up against its short circuit. Digital SDA/SCL also require power-domain isolation. This architecture creates a physical timing budget instead of assuming one. No exact hold-up regulator/supervisor BOM is approved here because maximum detector latency, maximum domain load, minimum capacitance under bias/temperature and input discharge/leakage guarantees are absent. A short of the retained rail remains outside that architecture's guarantee.

## Source-qualified numbers versus unsupported extrapolation

Primary sources retrieved directly from TI PDFs:
- [TPS3808 Rev N](https://www.ti.com/lit/ds/symlink/tps3808.pdf), §4, §6.5, §6.6.
- [TMUX1511 Rev B](https://www.ti.com/lit/ds/symlink/tmux1511.pdf), §5.3, §5.5, §5.7, §7.3.4.
- [ADS1115](https://www.ti.com/lit/ds/symlink/ads1115.pdf), operating/input limits and typical impedance as transcribed in the companion ADC-path report. ADS1115 PDF not independently re-extracted in this bounded pass.

| Quantity | Qualification and consequence |
|---|---|
| TPS3808G33 falling threshold | 3.07 V, ±1.5% over full specified temperature interval: 3.023950..3.116050 V. Fixed-version hysteresis max 2.5% of VIT; rising threshold must include it. No guaranteed hysteresis minimum is supplied. |
| Detector operating supply | 1.7..6.5 V; low-voltage reset behavior is load/ramp conditioned, not a blanket startup guarantee. VPOR 0.8 V max at 15 uA, with rise-time condition 15 us/V; do not transfer that result to a heavier SEL pull-up. |
| RESET sink | VOL <=0.4 V at 1 mA for VDD>=1.8 V, compatible with TMUX low <=0.45 V at that condition. Additional pull-up/pulldown loading and low-VDD operation need their own proof. |
| Fault latency | SENSE assertion 20 us typical only; **worst case unavailable**. MR 150 ns is also typical, and is not SENSE latency. |
| TMUX SEL transition | 55 ns max at VDD>=2.5 V, 80 ns below, specified VS=VDD, 200 ohm/15 pF load. Not a proved bound for this 10k bleed and unknown ADC capacitance. |
| TMUX supply-off isolation | 4 us max for a 1 us supply fall under its specified test load; not a general slow-ramp or brownout guarantee. |
| Off leakage | ±2 uA at VDD=0, VS<=3.6 V, VD=0, -40..125 C. Across 10.05k gives ±20.1 mV only conditionally. Neither nonzero VD nor intermediate supply is qualified by that one table row. |
| ADC loading | 710k differential / 100M common-mode are typical, not minimum guaranteed impedances. Typical extra loading loss 0.067024%; guaranteed total error remains unavailable. |

No specification here covers operation below -40 C. If intended electronics temperature reaches the project's -60 C ambient case, thermal control/evidence or differently rated parts are required; do not extrapolate leakage to it.

## Reproducible counterexample and required inequality

Run `python3 docs/analysis/check_cutter_adc_sequence.py` (stdlib; also executes existing DC corner assertions).

Measured script output: maximum loaded fault input **2.584901167 V** at VSCAP=5.4 V; detector minimum falling threshold **3.023950 V** gives **0.439048833 V** of DC headroom. The open-switch source node remains 2.7135 V; do not confuse that node with loaded ADC input.

For a bounded linear fall the necessary condition while ON is
`Vtrip_min - slew_max*(tdetect_max + tlogic_max + tswitch_max) >= VAIN_max + margin`.
Using **typical**, not guaranteed, 20 us + table-condition 55 ns gives an illustrative ceiling **21892.238 V/s**, with zero extra margin. At hypothetical 0.1 V/us collapse the rail reaches **1.018450 V** before disconnection: already below 2.584901167 V. This disproves universal safety; it is not a prediction of the actual board waveform. There is no documented slew_max here, and tdetect_max is missing, so no finite guaranteed capacitor value follows.

For the retained-domain candidate, the necessary hold-up relation is
`Cmin >= Imax * (tdetect_max+tlogic_max+tswitch_max+tdischarge_max) / (Vinitial_min - Vrequired_min - ESR_drop)`.
All quantities must cover temperature, tolerances, bias, leakage and supply reverse current. This is a sizing relation, **not a completed design**. AIN discharge additionally depends on the maximum effective capacitance, charge injection and leakage during the whole shutdown trajectory; their bounds are not established. Positive leakage into an unpowered ADC cannot be called within its operating input range simply because it is below VDD+0.3 V. Absolute maximum is not a functional target.

## Explicit unsupported corners / exact missing evidence

1. **Startup:** RESET low behavior at actual pull-up load, rapid/reversing power ramps, guaranteed enable threshold including hysteresis, and switch behavior below its 1.5 V supply minimum. CT release delay alone does not prove these.
2. **Shutdown/brownout:** maximum SENSE assertion delay and actual-load switch disconnect bound; qualified maximum rail collapse rate or an isolated hold-up domain with maximum load and minimum stored energy. These are absent, so shared-rail closure is rejected rather than deferred as an unspecified next step.
3. **Fully off and intermediate rails:** leakage versus nonzero drain voltage and every intermediate supply, ADC allowed off-state injection/backfeed, and maximum residual AIN voltage. The existing ±20.1 mV arithmetic proves none of those.
4. **Accuracy:** minimum ADS1115 input impedance and near-ground switch leakage over intended temperature are unavailable; calibration does not create those guarantees.
5. **Transient/fault scope:** negative source excursions, inductive overshoot above 5.4 V, loss of ground, resistor open/short, stuck switch, retained-rail short, and temperatures below -40 C are unsupported. No single-fault-tolerance claim.

**Final verdict: BLOCKED with a concrete rejected supervisor retrofit and a safer supply-domain architecture identified, not qualified.** No component-level circuit in this report is claimed ramp-safe. The missing manufacturer limits and missing supply-envelope bounds are the evidence preventing approval; the runnable tests deliberately PASS the counterexample, not the hardware.
