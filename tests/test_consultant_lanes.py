"""Both consultant lanes must serve the model they claim, or say so loudly.

WHY THIS EXISTS
Measured 2026-11-03: `ask_astra.py` reported "SERVED MODEL: ..." and carried on regardless, so
fourteen of fifteen `gpt-6-astra` requests were answered by `moonshotai/kimi-k3.1-pro` — the SAME
FAMILY that authors most of this board's work — and the output was presented as an independent
spatial review. A lane that silently substitutes a same-family model is worse than a lane that is
down, because the review LOOKS done (D-128 requires a different family; a same-family reviewer does
not satisfy the gate).

THE MECHANISM, so the fix is not cargo-culted
`zai_proxy.PROVIDER_MODELS` deliberately excludes `gpt-6-astra` from the general lanes: its own
comment says "only a pinned gpt-* slug from a spatial/vision/review tier reaches this lane". The
route in is `drain_fallback.allowed(...)` gated on `drain_fallback.signaled(headers, tier_hint)`.
No `X-Model-Tier` header => no spatial signal => the codex lane is never entered => the request is
served by whatever general lane answers. Sending the header makes the same call return
`model="gpt-6-astra"` with a `resp_*` Responses-API id instead of a `chatcmpl-*` id.

These tests are offline: they assert the CONTRACT in the source (header present, mismatch fatal),
because asserting against the live router would make the suite depend on the operator's quota.
"""
import pathlib
import re

import pytest

ASK_ASTRA = pathlib.Path(__file__).resolve().parents[1] / "tracker" / "hardware" / "ask_astra.py"


@pytest.fixture(scope="module")
def src():
    assert ASK_ASTRA.exists(), f"missing {ASK_ASTRA}"
    return ASK_ASTRA.read_text()


def test_astra_sends_the_spatial_tier_header(src):
    """Without `X-Model-Tier: spatial` the codex lane is unreachable and a substitute answers."""
    m = re.search(r"urllib\.request\.Request\((.*?)\)\s*\n\s*try:", src, re.S)
    assert m, "could not locate the Request construction in ask_astra.py"
    assert "X-Model-Tier" in m.group(1), (
        "ask_astra.py builds its request WITHOUT X-Model-Tier; the flat router will not consider "
        "openai_codex and a different family will answer (measured 2026-11-03)"
    )
    assert "spatial" in m.group(1).lower(), "the tier header must carry the spatial signal"


def test_astra_treats_a_served_mismatch_as_failure(src):
    """A served-model mismatch must exit non-zero BEFORE the verdict is interpreted."""
    assert "SERVED MISMATCH" in src, "no mismatch branch; a substitute answer would read as a review"
    tail = src[src.index("SERVED MISMATCH"):]
    assert "return 5" in tail, (
        "the mismatch branch must return 5, not 3 -- 3 means DEFECTS_PRESENT, and a lane lie must "
        "not be indistinguishable from a real defect verdict"
    )
    # the return must come BEFORE the verdict parsing, or a substitute's verdict still lands
    assert tail.index("return 5") < tail.index('"VERDICT: CLEAN"'), (
        "mismatch must be fatal before VERDICT parsing"
    )


def test_astra_names_the_same_family_substitution(src):
    """The most dangerous substitution is the author's own family; it must be called out by name."""
    assert "moonshot" in src.lower(), (
        "ask_astra.py does not recognise moonshot/kimi as a same-family substitution, which is the "
        "one that silently invalidated every earlier 'Astra' review"
    )
    assert "SAME-FAMILY" in src.upper()


def test_lane_identities_are_distinct():
    """The two lanes must be different providers, not two names for one model."""
    # Astra speaks the Responses API (resp_*); Kimi's lane returns chatcmpl-*.
    # This is the cheap structural assertion; the live check is scripts/lane_doctor.py.
    assert "gpt-6-astra" in ASK_ASTRA.read_text(), "the Astra lane must pin a gpt-* model"
