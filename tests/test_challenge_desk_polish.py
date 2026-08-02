"""UI polish helpers: cohort prefill index (no invented defaults)."""

from __future__ import annotations

from ml_saham.ui.streamlit_app import cohort_label_index


def test_cohort_index_defaults_to_none_token():
    opts = [
        "— no selection —",
        "ACCUM | sha256:aaa | n=10",
        "ACCUM | sha256:bbb | n=3",
    ]
    assert (
        cohort_label_index(
            opts,
            selected_label=None,
            purpose_family=None,
            compatibility_id=None,
        )
        == 0
    )


def test_cohort_index_never_auto_picks_only_cohort():
    opts = ["— no selection —", "ACCUM | sha256:only | n=99"]
    assert (
        cohort_label_index(
            opts,
            selected_label=None,
            purpose_family=None,
            compatibility_id=None,
        )
        == 0
    )


def test_cohort_index_prefers_explicit_label():
    opts = [
        "— no selection —",
        "ACCUM | sha256:aaa | n=10",
        "PRE_OPEN | sha256:pre | n=2",
    ]
    assert (
        cohort_label_index(
            opts,
            selected_label="PRE_OPEN | sha256:pre | n=2",
            purpose_family="ACCUM",
            compatibility_id="sha256:aaa",
        )
        == 2
    )


def test_cohort_index_matches_family_and_id():
    opts = [
        "— no selection —",
        "ACCUM | sha256:aaa | n=10",
        "ACCUM | sha256:bbb | n=3",
    ]
    assert (
        cohort_label_index(
            opts,
            selected_label=None,
            purpose_family="ACCUM",
            compatibility_id="sha256:bbb",
        )
        == 2
    )
