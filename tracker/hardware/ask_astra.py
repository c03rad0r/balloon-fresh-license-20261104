#!/usr/bin/env python3
"""Ask the gpt-6-astra visual consultant ANY question about ANY image(s).

WHY THIS EXISTS. test_astra_vision.py hardcodes a prompt about F.Cu routing plots. When it was pointed
at a connector cross-section, Astra correctly refused to answer the routing question -- so the call
produced a verdict about the wrong thing and looked like an answer. A hardcoded prompt is a question
you cannot change, and therefore a question you will ask wrongly.

This tool takes the prompt and the images as arguments, so the question always matches the artefact.

Usage:
    ask_astra.py "your question" image.png [image2.png ...]
    ask_astra.py --prompt-file q.txt image.png
    ask_astra.py --review   image.png      # runs the standing visual-review rubric

Always prints the SERVED model id, because the request alias and the served model can differ (the live
router serves gpt-6-astra for several aliases, and has silently served other families for others).
"""
import argparse
import base64
import json
import os
import sys
import urllib.request

ROUTER = "http://localhost:9099/v1/chat/completions"
MODEL = "gpt-6-astra"

# The standing rubric. Written to force DISAGREEMENT rather than agreement, because the recurring
# failure in this project was accepting a plausible-looking artefact as finished.
REVIEW_PROMPT = """You are reviewing a diagram, drawing or plot before it is shown to the operator or to a
fabricator. Your job is to find what is WRONG, not to confirm what is right.

Answer each literally. If a check passes, say so in one clause. If it fails, name the exact location
and the defect.

1. OVERLAP: is any text overlapping other text, or overlapping a drawn element?
2. CLIPPING: is any text or graphic cut off by the image boundary, or running under another block?
3. LEGIBILITY: is every label readable at the size shown? Name any that are not.
4. CONSISTENCY: do dimensions, labels and callouts agree with each other? Any contradiction is a defect.
5. COMPLETENESS: is anything named in the text but NOT drawn (or vice versa)? Say which.
6. ARROW / DIMENSION CONVENTION: are arrows and dimension lines drawn the standard way (extension lines,
   opposed arrowheads, arrows pointing AT the extension lines)? Name any that read wrongly.
7. TECHNICAL CORRECTNESS: does the drawing show what it claims to show? Would a fabricator or engineer
   be misled by anything?
8. TYPOS: quote any misspelled word or wrong unit verbatim.

Then: list every defect as a numbered, actionable item a person could fix without further explanation.

Finish with EXACTLY one line:
VERDICT: CLEAN
or
VERDICT: DEFECTS_PRESENT <count>
or
VERDICT: WRONG_QUESTION <one line saying what the image actually is, if it is not what the prompt assumed>
"""


def build_body(prompt, images, max_tokens):
    content = [{"type": "text", "text": prompt}]
    for p in images:
        if not os.path.exists(p):
            print(f"ask_astra: image not found: {p}", file=sys.stderr)
            return None
        with open(p, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        ext = os.path.splitext(p)[1].lstrip(".").lower() or "png"
        mime = "image/png" if ext == "png" else f"image/{ext}"
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"}})
    return {"model": MODEL, "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?", help="the question")
    ap.add_argument("images", nargs="*", help="image paths")
    ap.add_argument("--prompt-file")
    ap.add_argument("--review", action="store_true", help="use the standing review rubric")
    ap.add_argument("--out", help="also write the answer here")
    ap.add_argument("--max-tokens", type=int, default=2000)
    a = ap.parse_args()

    if a.review:
        prompt, images = REVIEW_PROMPT, (([a.prompt] if a.prompt else []) + a.images)
    elif a.prompt_file:
        prompt = open(a.prompt_file).read()
        images = ([a.prompt] if a.prompt else []) + a.images
    else:
        prompt, images = a.prompt, a.images

    if not prompt or not images:
        print(__doc__)
        return 2

    body = build_body(prompt, images, a.max_tokens)
    if body is None:
        return 1
    req = urllib.request.Request(ROUTER, data=json.dumps(body).encode(),
                                headers={
                                    "Content-Type": "application/json",
                                    # THE SPATIAL SIGNAL. Without this header the flat router never
                                    # considers openai_codex: gpt-6-astra is deliberately excluded
                                    # from the general lanes (PROVIDER_MODELS comment, 2026-10-10 --
                                    # "only a pinned gpt-* slug from a spatial/vision/review tier
                                    # reaches this lane"), and the drain fallback that WOULD reach it
                                    # is gated on drain_fallback.signaled(headers, tier_hint).
                                    # Measured 2026-11-03: unheaded requests were served by
                                    # moonshotai/kimi-k3.1-pro (a DIFFERENT FAMILY) and earlier 503'd
                                    # with candidates_tried=["openai_codex"], i.e. the right lane was
                                    # known and never entered. With this header the same call returns
                                    # model="gpt-6-astra" and a resp_* Responses-API id.
                                    "X-Model-Tier": "spatial",
                                })
    try:
        with urllib.request.urlopen(req, timeout=420) as r:
            d = json.loads(r.read())
    except Exception as e:
        print(f"ask_astra: request failed: {type(e).__name__} {str(e)[:300]}")
        return 1

    served = d.get("model")
    answer = d["choices"][0]["message"]["content"]
    print(f"SERVED MODEL: {served}")
    print(f"IMAGES: {', '.join(images)}")
    print("=" * 78)
    print(answer)
    if a.out:
        with open(a.out, "w") as fh:
            fh.write(f"# Astra visual review\n\nServed model: {served}\n"
                     f"Images: {', '.join(images)}\n\n{answer}\n")
        print(f"\n(written to {a.out})")

    # A DIFFERENT FAMILY IS NOT A REVIEW. The router has served moonshotai/kimi-k3.1-pro for
    # gpt-6-astra requests (measured 2026-11-03: 14 of 15 attempts). Kimi is the family that
    # authors most of this board's work, so its "review" is not cross-family and must never be
    # presented as Astra's spatial verdict. Print the mismatch loudly and exit non-zero BEFORE the
    # verdict is interpreted, so a loop cannot mistake a substitute's answer for the lane's.
    family = (served or "").split("/")[0].lower()
    if served != MODEL:
        same_family = family in ("moonshotai", "moonshot")
        print()
        print("!" * 78)
        print(f"SERVED MISMATCH: requested {MODEL!r}, served {served!r}")
        if same_family:
            print("This is a SAME-FAMILY-AS-AUTHOR substitution: the answer is NOT an independent")
            print("spatial review and must not be cited as one.")
        else:
            print("The served model is not the requested model; treat the answer with caution.")
        print("!" * 78)
        # Exit 5, NOT 3. 3 is already DEFECTS_PRESENT below, and a lane lie must be distinguishable
        # from a real defect verdict -- otherwise a substituted review reads as a passing review.
        return 5

    # a non-zero exit on defects, so a loop can branch on it
    up = answer.upper()
    if "VERDICT: CLEAN" in up:
        return 0
    if "VERDICT: DEFECTS_PRESENT" in up:
        return 3
    if "VERDICT: WRONG_QUESTION" in up:
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
