#!/usr/bin/env bash
# route_one.sh -- route ONE pair, save it, and gate it. Crash-safe by construction.
#
# WHY ONE PAIR. Measured: a four-pair batch hit its outer `timeout` during the fourth pair and
# wrote NEITHER the board NOR the report -- three already-routed nets were lost with no artefact
# to show they had ever been routed. A router that only saves at the end of a long batch
# publishes nothing when the batch is cut short. One pair per process means the unit of work
# equals the unit of saving, and a kill costs at most the pair in flight.
#
# Each accepted pair is promoted to latest.kicad_pcb, so a chain of route_one.sh calls is
# cumulative and every intermediate board is a verified artefact that survives a crash.
#
#   ./route_one.sh /F33_IRQ:U2.18:U1.17
set -uo pipefail
PY=/usr/bin/python3
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
SPEC=$1
LABEL=${2:-$(echo "$SPEC" | sed 's|^/||; s|:.*||')}
DEADLINE=${DEADLINE:-900}

W="$HERE/batches/$LABEL"
prev="$HERE/latest.kicad_pcb"
[ -f "$prev" ] || prev="$HERE/batches/A/board.kicad_pcb"

mkdir -p "$W"
for ext in kicad_pcb kicad_pro kicad_dru; do
  cp "${prev%.kicad_pcb}.$ext" "$W/board.$ext"
done
before_sha=$(sha256sum "$W/board.kicad_pcb" | cut -d' ' -f1)
echo "=== $LABEL   from ${before_sha:0:16}"

$PY "$REPO/tracker/hardware/route_batch.py" "$W/board.kicad_pcb" \
    --pair "$SPEC" --out "$W/routed.kicad_pcb" --report "$W/report.json" \
    --deadline "$DEADLINE" 2>&1 | grep -v "Debug:" | tail -6

if [ ! -f "$W/routed.kicad_pcb" ]; then
  echo "$LABEL: NOTHING WRITTEN -- tree untouched, latest.kicad_pcb unchanged"
  exit 2
fi

# native DRC on the routed board (its own .kicad_pro/.kicad_dru sit beside it)
timeout 900 kicad-cli pcb drc --format json --severity-all --units mm \
        --output "$W/drc.json" "$W/routed.kicad_pcb" 2>&1 | grep -viE "debug" | tail -2

# via-in-pad: the check kicad-cli cannot do. Foreign-net overlap always blocks; same-net is
# reported against the baseline so the delta is never hidden inside a total.
$PY "$REPO/tracker/hardware/verify_via_in_pad.py" "$W/routed.kicad_pcb" \
    --baseline "$W/board.kicad_pcb" 2>&1 | grep -v "Debug:" | tail -6
vrc=${PIPESTATUS[0]}

$PY "$REPO/tracker/hardware/proof.py" "$W/board.kicad_pcb" "$W/routed.kicad_pcb" \
    --drc-before "$HERE/batches/A/drc.json" --drc-after "$W/drc.json" \
    --pair "$SPEC" --regress-all --report "$W/proof.json" 2>&1 | grep -v "Debug:" | tail -12
prc=${PIPESTATUS[0]}

if [ $vrc -ne 0 ] || [ $prc -ne 0 ]; then
  echo "$LABEL: GATE FAILED (via-in-pad rc=$vrc, proof rc=$prc) -- latest.kicad_pcb UNCHANGED"
  exit 3
fi

cp "$W/routed.kicad_pcb" "$HERE/latest.kicad_pcb"
cp "$W/board.kicad_pro"  "$HERE/latest.kicad_pro"
cp "$W/board.kicad_dru"  "$HERE/latest.kicad_dru"
echo "$LABEL: ACCEPTED  ${before_sha:0:16} -> $(sha256sum "$W/routed.kicad_pcb" | cut -c1-16)"
echo "        opens: see $W/proof.json"
