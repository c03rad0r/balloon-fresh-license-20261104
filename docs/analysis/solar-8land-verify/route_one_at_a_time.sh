#!/bin/bash
# Route the remaining pad-pairs ONE AT A TIME, each in its own process.
#
# WHY per-process: the A* open/closed frontier over a 60mm span does not fit in this box's ~4GB.
# Run as one process, the run dies with rc=137 (OOM) part-way through the set and nothing is saved.
# One pair per process means peak memory is one pair's frontier, and every completed pair is written
# out and can be validated before the next starts.
#
# Each step: route onto the PREVIOUS step's board, so copper accumulates. If a step's DRC shows a
# new violation class or a worse unconnected count, that step is DISCARDED and the chain continues
# from the last good board. Nothing is force-kept.
set -u
cd /home/c08r4d0r/worktrees/flight-readiness-20261102 || exit 1
R=/home/c08r4d0r/reports/flight-readiness-20261102
W=$R/onepair
DRU=tracker/hardware/jlcpcb-s1-frozen.kicad_dru
PY="env PYTHONPATH=/usr/lib/python3/dist-packages /usr/bin/python3"
mkdir -p "$W"

PAIRS="C10.1->U1.2 U2.18->U1.17 U1.4->U2.12 U1.21->R_MON2.1 D_HUB1.2->D_HUB2.1 D_HUB1.1->U_HUB_CVT.1 U_C.4->U3.4 U_C.5->U3.5 U1.19->U3.15 D_BP2.2->J_W2.4 J_W4.1->D_BP4.1"

cp "$R/merge/out.kicad_pcb" "$W/cur.kicad_pcb"
cp "$R/v9/V9.kicad_pro"     "$W/cur.kicad_pro"
cp "$R/v9/V9.kicad_dru"     "$W/cur.kicad_dru"

n=0
for P in $PAIRS; do
  n=$((n+1))
  safe=$(echo "$P" | tr -c 'A-Za-z0-9._-' '_')
  echo "=== [$n] $P"
  $PY docs/analysis/solar-8land-verify/route_scoped.py \
      "$W/cur.kicad_pcb" "$W/try-$safe.kicad_pcb" \
      --dru "$DRU" --report "$W" --only "$P" --max-pairs 1 \
      --per-pair-s 90 --budget-s 200 > "$W/log-$safe" 2>&1
  rc=$?
  routed=$(grep -c "^routed: 1" "$W/log-$safe" 2>/dev/null || true)
  if [ "$rc" -ne 0 ] || [ "${routed:-0}" -eq 0 ]; then
    echo "    no route (rc=$rc) -- kept chain as-is"
    grep -E "no path|REFUSE|MemoryError|Killed" "$W/log-$safe" | head -2 | sed 's/^/    /'
    continue
  fi
  cp "$W/try-$safe.kicad_pro" "$W/cur.kicad_pro" 2>/dev/null
  cp "$W/try-$safe.kicad_dru" "$W/cur.kicad_dru" 2>/dev/null
  if grep -q "KEPT" "$W/log-$safe"; then
    cp "$W/try-$safe.kicad_pcb" "$W/cur.kicad_pcb"
    echo "    KEPT -> unconnected $(grep -oE 'unconnected [0-9]+ -> [0-9]+' "$W/log-$safe" | tail -1)"
  else
    echo "    ROUTE REJECTED by its own DRC gate"
    grep -E "REFUSE|new classes" "$W/log-$safe" | head -2 | sed 's/^/    /'
  fi
done

echo "=== final"
kicad-cli pcb drc --format json --severity-all -o "$W/final-drc.json" "$W/cur.kicad_pcb" >/dev/null 2>&1
jq -r '"violations=\(.violations|length) errors=\([.violations[]|select(.severity=="error")]|length) unconnected=\(.unconnected_items|length)"' "$W/final-drc.json"
sha256sum "$W/cur.kicad_pcb"
