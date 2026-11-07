# DRC JSON has TWO top-level arrays; counting opens from the wrong one gives 0

**2026-11-07, verified on `e00b98e7`.**

## The trap

`kicad-cli pcb drc --format json` writes opens and rule violations to **different top-level keys**:

```json
{
  "unconnected_items": [ ... ],   <- opens live HERE
  "violations":        [ ... ]    <- rule violations live HERE
}
```

`unconnected_items` entries do **not** also appear inside `violations`. So this idiom:

```python
u = [v for v in d['violations'] if v.get('type') == 'unconnected_items']
print(len(u))          # -> 0
```

**always returns 0 on a board with opens.** It looks like "no opens"; it means "wrong array".

## How this showed up

A run on the live board (15 opens) printed:

```
unconnected: 0
```

while the renderer reading the same JSON reported `opens=18` (it reads the top-level key). Two
readers of one file disagreeing is the tell.

## I nearly wrote the wrong explanation

My first instinct was that this was the missing-`.kicad_dru` sidecar artefact again. Measured as a
control, that is **not** the cause:

```
nodru:    unconnected_items=15  violations=48
withdru:  unconnected_items=15  violations=32
```

The sidecar changes the **violations** count (48 -> 32, the phantom `copper_edge_clearance` items).
It does **not** change the open count. Both report 15. The `0` was purely the wrong-array bug.

Worth recording because the sidecar artefact is real and has bitten this campaign four times, which
makes it a very attractive explanation to reach for — and this time it was wrong.

## Correct idiom

```python
opens  = d.get('unconnected_items', [])
rules  = d.get('violations', [])
```

## Reproduce

```
kicad-cli pcb drc --format json --severity-all --units mm --output d.json <board>
python3 -c "import json;d=json.load(open('d.json'));print(len(d['unconnected_items']), len(d['violations']))"
python3 -c "import json;d=json.load(open('d.json'));print(len([v for v in d['violations'] if v.get('type')=='unconnected_items']))"
```
