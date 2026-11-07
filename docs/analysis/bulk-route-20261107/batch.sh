#!/usr/bin/env bash
# batch.sh -- run ONE bounded routing batch with the repo's proven toolchain and gate it.
#
#   ./batch.sh B "/PAD_SPEC" "/PAD_SPEC" ...
#
# Each batch is a directory holding its own board copy. The batch route is attempted on that
# copy only; the accepted copy is promoted to `latest.kicad_pcb` and nothing else in the tree
# moves. A batch that fails any gate is rejected whole -- partial routing is kept only when it
# still passes every gate (opens strictly down, zero broken pairs, no new electrical item),
# because a small verified gain is worth a commit and an unverified one is not.
set -uo pipefail
PY=/usr/bin/python3
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LABEL=$1; shift
DEADLINE=${DEADLINE:-240}

B="$HERE/batches/$LABEL"
prev="$HERE/latest.kicad_pcb"
[ -f "$prev" ] || prev="$HERE/batches/A/board.kicad_pcb"
mkdir -p "$B"
for ext in kicad_pcb kicad_pro kicad_dru; do
  cp "${prev%.kicad_pcb}.$ext" "$B/board.$ext"
done

echo "=== batch $LABEL  from $(sha256sum "$B/board.kicad_pcb" | cut -c1-16)"

args=()
for p in "$@"; do args+=(--pair "$p"); done

$PY "$HERE/route_batch.py" "$B/board.kicad_pcb" "${args[@]}" \
    --out "$B/routed.kicad_pcb" --report "$B/report.json" \
    --deadline "$DEADLINE" 2>&1 | grep -v "Debug:" | tail -30
rc=${PIPESTATUS[0]}

if [ ! -f "$B/routed.kicad_pcb" ]; then
  echo "batch $LABEL: NOTHING ROUTED (rc=$rc) -- tree untouched"
  exit 2
fi

# native DRC on BOTH boards, measured here rather than inherited from an earlier batch: a
# "before" number copied from another directory is not evidence about this batch's input.
timeout 900 kicad-cli pcb drc --format json --severity-all --units mm \
        --output "$B/before-drc.json" "$B/board.kicad_pcb" 2>&1 | grep -vi "debug:" | tail -2
timeout 900 kicad-cli pcb drc --format json --severity-all --units mm \
        --output "$B/drc.json" "$B/routed.kicad_pcb" 2>&1 | grep -vi "debug:" | tail -2

# graph proof over ALL nets, not only the routed ones
$PY "$HERE/proof.py" "$B/board.kicad_pcb" "$B/routed.kicad_pcb" \
    --drc-before "$B/before-drc.json" --drc-after "$B/drc.json" \
    $(for p in "$@"; do printf -- '--pair %s ' "$p"; done) \
    --regress-all --report "$B/proof.json" 2>&1 | grep -v "Debug:" | tail -25
prc=${PIPESTATUS[0]}

if [ $prc -ne 0 ]; then
  echo "batch $LABEL: PROOF FAILED -- tree untouched"
  exit 3
fi

cp "$B/routed.kicad_pcb" "$HERE/latest.kicad_pcb"
cp "$B/routed.kicad_pro"  "$HERE/latest.kicad_pro" 2>/dev/null || true
cp "$B/routed.kicad_dru"  "$HERE/latest.kicad_dru" 2>/dev/null || true
echo "batch $LABEL: ACCEPTED -> latest.kicad_pcb $(sha256sum "$HERE/latest.kicad_pcb" | cut -c1-16)"
