#!/usr/bin/env python3
"""Prove BOTH consultant lanes serve what they claim. Exit non-zero if either is a lie.

Two lanes, two families, deliberately:
  ASTRA  gpt-6-astra            -> openai_codex (Responses API, ids start "resp_")
  KIMI   moonshotai/kimi-k3.1-pro -> the Moonshot/z.ai lane (ids start "chatcmpl-")

WHY A DOCTOR AND NOT JUST TRUST
Measured 2026-11-03: fourteen of fifteen `gpt-6-astra` calls were answered by
`moonshotai/kimi-k3.1-pro` -- the author's own family -- and the output was written up as an
independent spatial review. The router does not raise an error for that; it returns 200 with a
different model. So the only defence is to read back the SERVED id every time.

The Astra route is gated: PROVIDER_MODELS excludes gpt-6-astra from the general lanes on purpose
("only a pinned gpt-* slug from a spatial/vision/review tier reaches this lane"), and entry is
`drain_fallback.signaled(headers, tier_hint)` on the X-Model-Tier header. No header => not the
Astra lane. That is the bug this doctor catches.

Usage:  lane_doctor.py [--image path.png]
        exit 0 both lanes serve their identity
        exit 3 a lane returned a different model
        exit 4 a lane was unreachable
"""
import argparse
import base64
import json
import os
import sys
import urllib.request

ROUTER = os.environ.get("HERMES_ROUTER", "http://localhost:9099/v1/chat/completions")
ASTRA = "gpt-6-astra"
# The DECLARED id. Note `moonshotai/kimi-k3.1-pro` is what the router reports as the SERVED model
# when a general-lane request is answered from the Moonshot backend -- it is not a routable id and
# requesting it returns "no lane declares this model (flat router)" (measured 2026-11-03).
KIMI = os.environ.get("KIMI_MODEL", "kimi-k3")


def call(model, prompt, image=None, tier=None, timeout=180):
    content = [{"type": "text", "text": prompt}]
    if image:
        b64 = base64.b64encode(open(image, "rb").read()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    body = {"model": model, "messages": [{"role": "user", "content": content}],
            "max_tokens": 40}
    h = {"Content-Type": "application/json"}
    if tier:
        h["X-Model-Tier"] = tier
    req = urllib.request.Request(ROUTER, data=json.dumps(body).encode(), headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    a = ap.parse_args()
    prompt = "Reply with exactly: LANE-OK"
    if a.image:
        prompt = "Reply with exactly: LANE-OK after looking at the image."

    rows, bad = [], 0
    for name, model, tier, idpfx in (("ASTRA", ASTRA, "spatial", "resp_"),
                                     ("KIMI", KIMI, None, "chatcmpl-")):
        try:
            d = call(model, prompt, a.image, tier)
        except Exception as e:
            print(f"{name:6s} UNREACHABLE  {model}  {type(e).__name__}: {str(e)[:120]}")
            rows.append((name, model, None, None))
            bad = max(bad, 4)
            continue
        if "error" in d:
            print(f"{name:6s} ERROR        {model}  {str(d)[:160]}")
            rows.append((name, model, None, None))
            bad = max(bad, 4)
            continue
        served = d.get("model")
        rid = str(d.get("id", ""))
        ok = served == model
        print(f"{name:6s} {'OK          ' if ok else 'MISMATCH    '} requested={model} "
              f"served={served} id={rid[:14]}")
        rows.append((name, model, served, rid))
        if not ok:
            bad = max(bad, 3)

    # the two lanes must not be the same backend
    ids = [r[3] for r in rows if r[3]]
    if len(ids) == 2 and ids[0].startswith("resp_") and ids[1].startswith("chatcmpl-"):
        print("distinct backends: ASTRA=Responses API, KIMI=chat.completions   OK")
    elif len(ids) == 2:
        print("WARNING: could not distinguish backends by response id prefix")
    print(f"\nVERDICT: {'BOTH LANES SERVE THEIR IDENTITY' if bad == 0 else 'LANE DEFECT'}")
    return bad


if __name__ == "__main__":
    sys.exit(main())
