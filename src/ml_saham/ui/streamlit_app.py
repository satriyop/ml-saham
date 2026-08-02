"""Streamlit Challenge Desk — Phase 1A read-only workspaces.

Thin presentation adapter over ChallengeWorkbenchService. No SQLite, no CLI
scraping, no scoring, no Run action, no C0 readiness inference.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from ml_saham.challenge.workbench import (
    CAPABILITY_NOT_IMPLEMENTED,
    ChallengeRunRequest,
    ChallengeRunView,
    ChallengeWorkbenchOverview,
    ChallengeWorkbenchService,
    CohortInventoryResult,
    ControlTowerSnapshot,
    DiagnosticCatalogRow,
    HistoricalResultRow,
    PolicyCatalogRow,
    build_challenge_workbench,
)

# Challenge verdict / blocked states — text + icon + color (never success soft).
_STATUS_STYLE: dict[str, tuple[str, str]] = {
    "WIN": ("✅", "green"),
    "LOSE": ("❌", "red"),
    "INCONCLUSIVE": ("➖", "orange"),
    "BLOCKED_DATA": ("🚫", "violet"),
    "BLOCKED_POLICY": ("🔒", "violet"),
    "KEEP": ("✅", "green"),
    "DEMOTE": ("⬇️", "orange"),
    "DROP_CANDIDATE": ("🗑️", "red"),
    "KEEP_DISPLAY": ("👁️", "blue"),
    "DEMOTE_DISPLAY": ("👁️", "orange"),
    "PROMOTE_CANDIDATE": ("⬆️", "blue"),
    "UNKNOWN": ("❓", "gray"),
}


def _service() -> ChallengeWorkbenchService:
    if "workbench_service" not in st.session_state:
        st.session_state.workbench_service = build_challenge_workbench()
    return st.session_state.workbench_service  # type: ignore[no-any-return]


def _format_status(status: str) -> str:
    icon, _color = _STATUS_STYLE.get(status, _STATUS_STYLE["UNKNOWN"])
    return f"{icon} {status}"


def render_sidebar(overview: ChallengeWorkbenchOverview) -> None:
    st.sidebar.title("Challenge Desk")
    st.sidebar.caption("Local single-user · English challenge surface")
    st.sidebar.markdown(f"**Role:** {overview.product_role}")
    st.sidebar.markdown(f"**Upstream:** `{overview.upstream_access_mode}`")
    st.sidebar.text(str(overview.upstream_db_path))
    st.sidebar.markdown("**Artifacts**")
    st.sidebar.text(str(overview.artifacts_root))
    st.sidebar.caption(
        "Phase 2: Run Challenge for explicit policy tournaments. "
        "CLI remains automation/recovery."
    )
    st.sidebar.info(overview.production_changes)
    st.sidebar.caption(overview.curriculum_authority)


def render_foundation(overview: ChallengeWorkbenchOverview) -> None:
    st.title(overview.product_name)
    st.caption(
        "Phase 2 desk — Control Tower, cohorts, catalog, and explicit Run."
    )
    st.info(
        "This is an offline challenge lab for deterministic human decision "
        "support. It is not a trading cockpit."
    )
    product_col, authority_col = st.columns(2)
    with product_col:
        st.subheader("Product boundary")
        st.markdown(f"**Role:** {overview.product_role}")
        st.markdown(f"**Upstream access:** {overview.upstream_access_mode}")
        st.markdown(f"**Production changes:** {overview.production_changes}")
    with authority_col:
        st.subheader("Authority")
        st.markdown(f"**Challenge:** {overview.challenge_authority}")
        st.markdown(f"**Curriculum:** {overview.curriculum_authority}")
    st.subheader("Configured paths")
    st.text(f"Upstream SQLite (read-only): {overview.upstream_db_path}")
    st.text(f"ml-saham artifacts: {overview.artifacts_root}")
    st.info(
        "Run Challenge requires an explicit form submit. Selector changes never "
        "start work. BLOCKED_* and INCONCLUSIVE are product states."
    )


def render_control_tower(service: ChallengeWorkbenchService) -> None:
    st.title("Control Tower")
    st.caption(
        "Historical challenge packs only — no live health/run execution in Phase 1A."
    )
    st.info(
        "Tracks: **tune** · **factor** · **champion** · **diagnostic** "
        "(display / PROMOTE_CANDIDATE only — never Action)."
    )
    snap: ControlTowerSnapshot = service.control_tower_snapshot(limit=100)
    st.markdown(f"**Inventory status:** `{snap.status}`")
    if snap.by_track:
        st.write("Counts by track:", dict(snap.by_track))
    for note in snap.notes:
        st.caption(note)
    if not snap.rows:
        st.warning(
            "No historical challenge packs found under the configured artifacts "
            "root. Run challenges via CLI to populate this view."
        )
        return

    tracks = sorted({r.track for r in snap.rows})
    selected_tracks = st.multiselect(
        "Filter tracks",
        options=tracks,
        default=tracks,
        key="tower_track_filter",
    )
    filtered = [r for r in snap.rows if r.track in selected_tracks]

    # Separate diagnostic display from Action-adjacent tracks visually.
    tune_rows = [r for r in filtered if r.track in {"tune", "health"}]
    factor_rows = [r for r in filtered if r.track == "factor"]
    champion_rows = [r for r in filtered if r.track == "champion"]
    diagnostic_rows = [r for r in filtered if r.track == "diagnostic"]

    _tower_section("Tune / engine (policy tournaments)", tune_rows)
    _tower_section("Factor validity", factor_rows)
    _tower_section("Champion", champion_rows)
    st.subheader("Diagnostic (display / promote-candidate only — never Action)")
    if diagnostic_rows:
        st.dataframe(_rows_to_records(diagnostic_rows), use_container_width=True)
    else:
        st.caption("No diagnostic historical rows in filter.")


def _tower_section(title: str, rows: list[HistoricalResultRow]) -> None:
    st.subheader(title)
    if not rows:
        st.caption("No rows.")
        return
    st.dataframe(_rows_to_records(rows), use_container_width=True)


def _rows_to_records(rows: list[HistoricalResultRow]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "status": _format_status(r.status),
                "status_raw": r.status,
                "track": r.track,
                "mode": r.mode,
                "policy_id": r.policy_id or "",
                "protocol_id": r.protocol_id or "",
                "baseline_id": r.baseline_id or "",
                "against_id": r.against_id or "",
                "factor": r.factor or "",
                "diagnostic_id": r.diagnostic_id or "",
                "created_at": r.created_at or "",
                "artifact_path": r.artifact_path,
                "diagnostic_display_only": r.is_diagnostic_display,
            }
        )
    return out


def render_cohort_discovery(service: ChallengeWorkbenchService) -> None:
    st.title("Cohort Discovery")
    st.caption(
        "Factual purpose-family inventory only. No auto-select of largest/latest/"
        "only cohort. Selection here does not grant eligibility."
    )
    inv: CohortInventoryResult = service.list_cohort_inventory()
    st.markdown(f"**Inventory status:** `{inv.status}`")
    for note in inv.notes:
        st.caption(note)

    if not inv.rows:
        st.warning(
            "No cohorts available. Check the read-only upstream DB path and "
            "observation purpose families ACCUM / PRE_OPEN."
        )
        st.session_state.pop("selected_compatibility_id", None)
        st.session_state.pop("selected_purpose_family", None)
        return

    records = [
        {
            "purpose_family": r.purpose_family,
            "compatibility_id": r.compatibility_id,
            "observation_count": r.observation_count,
            "max_captured_at": r.max_captured_at or "",
            "distinct_sessions": r.distinct_sessions.status,
            "economic_date_range": r.economic_date_range.status,
            "readiness": r.readiness_capability.status,
        }
        for r in inv.rows
    ]
    st.dataframe(records, use_container_width=True)
    st.caption(
        f"distinct_sessions / economic_date_range / readiness = "
        f"`{CAPABILITY_NOT_IMPLEMENTED}` until C0 / inventory projection ships."
    )

    options = [
        f"{r.purpose_family} | {r.compatibility_id} | n={r.observation_count}"
        for r in inv.rows
    ]
    # Explicit empty default — never preselect, including single-cohort case.
    choice = st.selectbox(
        "Explicit compatibility identity (optional display selection)",
        options=["— no selection —", *options],
        index=0,
        key="cohort_selectbox",
    )
    if choice == "— no selection —":
        st.session_state.pop("selected_compatibility_id", None)
        st.session_state.pop("selected_purpose_family", None)
        st.info(
            "No compatibility ID selected. Phase 2 Run will require an exact "
            "explicit selection; nothing is preselected."
        )
    else:
        # Parse "FAMILY | cid | n=..."
        parts = [p.strip() for p in choice.split("|")]
        family = parts[0] if parts else ""
        cid = parts[1] if len(parts) > 1 else ""
        st.session_state.selected_purpose_family = family
        st.session_state.selected_compatibility_id = cid
        st.success(
            f"Selected for display only: family=`{family}` "
            f"compatibility_id=`{cid}` (not production authority by itself)."
        )

    st.warning(
        "No Run control on this page. Selection does not start a challenge."
    )


def render_policy_catalog(service: ChallengeWorkbenchService) -> None:
    st.title("Policy Catalog")
    st.caption(
        "Same registry as `ml-saham challenge list`. No parallel inventory. "
        "No cohort-specific readiness in Phase 1A."
    )
    rows: tuple[PolicyCatalogRow, ...] = service.list_policy_catalog()
    records = [
        {
            "policy_id": r.policy_id,
            "decision_type": r.decision_type,
            "protocol_id": r.protocol_id,
            "version": r.version,
            "panel_kind": r.panel_kind,
            "score_kind": r.score_kind,
            "adapter_id": r.adapter_id or "",
            "adapter_version": r.adapter_version or "",
            "baselines": ", ".join(r.supported_baselines),
            "challengers": ", ".join(r.supported_challengers)
            if r.supported_challengers
            else "(see adapter / dig docs)",
            "support_status": r.support_status,
            "support_reason": r.support_reason,
            "readiness": r.readiness_capability.status,
        }
        for r in rows
    ]
    st.dataframe(records, use_container_width=True)
    st.caption(
        f"Readiness column is `{CAPABILITY_NOT_IMPLEMENTED}` — not a challenge "
        "verdict and not producer/Protocol readiness."
    )

    st.subheader("Diagnostic bags (explain-only)")
    diags: tuple[DiagnosticCatalogRow, ...] = service.list_diagnostic_catalog()
    st.dataframe(
        [
            {
                "diagnostic_id": d.diagnostic_id,
                "version": d.version,
                "protocol": d.protocol_id,
                "engine": d.engine,
                "scenario": d.scenario,
                "n_features": d.n_features,
                "authority": d.authority_note,
            }
            for d in diags
        ],
        use_container_width=True,
    )
    st.warning(
        "Diagnostics never authorize Action / ENTER. PROMOTE_CANDIDATE only "
        "opens a human PolicySpec design path."
    )


def _executed_keys() -> set[str]:
    if "executed_attempt_keys" not in st.session_state:
        st.session_state.executed_attempt_keys = set()
    return st.session_state.executed_attempt_keys  # type: ignore[no-any-return]


def render_run_challenge(service: ChallengeWorkbenchService) -> None:
    st.title("Run Challenge")
    st.caption(
        "Phase 2: explicit immutable policy tournament only. "
        "Selector changes never start work — only the submit button does."
    )
    st.info(
        "Verb scope: `policy_run` via existing `run_policy_challenge`. "
        "Factor / engine / champion / diagnostic / health runs stay on CLI "
        "until separately exposed."
    )

    catalog = service.list_policy_catalog()
    policy_ids = [r.policy_id for r in catalog]
    if not policy_ids:
        st.error("Policy catalog is empty.")
        return
    catalog_by_id = {r.policy_id: r for r in catalog}

    inv = service.list_cohort_inventory()
    cohort_labels = [
        f"{r.purpose_family} | {r.compatibility_id} | n={r.observation_count}"
        for r in inv.rows
    ]

    with st.form("policy_run_form", clear_on_submit=False):
        policy_id = st.selectbox("Policy ID", options=policy_ids, index=0)
        row = catalog_by_id[policy_id]
        challengers = list(row.supported_challengers) or ["equal_sleeves"]
        against = st.selectbox("Challenger (against)", options=challengers, index=0)
        baseline = st.selectbox(
            "Baseline",
            options=["production", "static_reference"],
            index=0,
            help="production requires verified snapshot identity; "
            "static_reference is never promotion-eligible as production.",
        )
        if cohort_labels:
            cohort_choice = st.selectbox(
                "Compatibility ID (exact; no default)",
                options=["— no selection —", *cohort_labels],
                index=0,
            )
        else:
            cohort_choice = "— no selection —"
            st.warning(
                "No cohorts in inventory. Entering a free-form ID is not offered "
                "in v1 — fix upstream DB or use CLI."
            )
        write_artifact = st.checkbox(
            "Write artifact pack",
            value=True,
            help="Default matches product CLI write behavior.",
        )
        st.markdown("**Protocol (read-only)**")
        proto = service.describe_protocol(row.protocol_id)
        if proto:
            st.json(
                {
                    "protocol_id": proto.protocol_id,
                    "primary_horizon": proto.primary_horizon,
                    "horizons_report": list(proto.horizons_report),
                    "n_folds": proto.n_folds,
                    "min_folds_for_win": proto.min_folds_for_win,
                    "embargo_sessions": proto.embargo_sessions,
                    "min_n_total": proto.min_n_total,
                    "label": proto.label,
                    "costs": proto.costs,
                }
            )
        else:
            st.caption(f"Protocol {row.protocol_id!r} not in local registry.")
        st.caption(
            f"Readiness preview: `{row.readiness_capability.status}` — "
            "not eligibility; C0 deferred."
        )
        submitted = st.form_submit_button("Run challenge", type="primary")

    if submitted:
        if cohort_choice == "— no selection —":
            st.error(
                "Select an exact compatibility identity before running. "
                "Nothing is auto-selected."
            )
        else:
            parts = [p.strip() for p in cohort_choice.split("|")]
            family = parts[0] if parts else ""
            cid = parts[1] if len(parts) > 1 else ""
            try:
                request = service.build_policy_run_request(
                    policy_id=policy_id,
                    baseline_id=baseline,
                    against_id=against,
                    compatibility_id=cid,
                    purpose_family=family,
                    write_artifact=write_artifact,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                attempt_id = service.new_attempt_id()
                with st.spinner(
                    f"Running {request.policy_id} (attempt {attempt_id})…"
                ):
                    view = service.execute_policy_run(
                        request,
                        attempt_id=attempt_id,
                        executed_keys=_executed_keys(),
                    )
                st.session_state.last_run_request = request
                st.session_state.last_run_view = view

    # Run again: same request, new attempt
    last_req: ChallengeRunRequest | None = st.session_state.get("last_run_request")
    if last_req is not None:
        st.divider()
        st.markdown(
            f"**Last request_id:** `{last_req.request_id}` · "
            f"policy=`{last_req.policy_id}` against=`{last_req.against_id}`"
        )
        if st.button("Run again (new attempt_id)", key="run_again_btn"):
            attempt_id = service.new_attempt_id()
            with st.spinner(f"Re-running attempt {attempt_id}…"):
                view = service.execute_policy_run(
                    last_req,
                    attempt_id=attempt_id,
                    executed_keys=_executed_keys(),
                )
            st.session_state.last_run_view = view

    view: ChallengeRunView | None = st.session_state.get("last_run_view")
    if view is not None:
        st.divider()
        render_result_inspector(view)


def render_result_inspector(view: ChallengeRunView) -> None:
    st.subheader("Result Inspector")
    st.markdown(
        f"**Kind:** `{view.kind}` · **Status:** {_format_status(view.status)} · "
        f"**Elapsed:** {view.elapsed_seconds:.2f}s"
    )
    st.caption(
        f"request_id=`{view.request_id}` · attempt_id=`{view.attempt_id}`"
    )
    if view.kind == "application_error":
        st.error(
            f"Application/programmer error (not a market BLOCKED_* verdict). "
            f"Reference: `{view.error_reference}`"
        )
    elif view.status in {"BLOCKED_DATA", "BLOCKED_POLICY", "INCONCLUSIVE"}:
        st.warning(
            f"Completed product state: **{view.status}** "
            "(not a UI exception; not a soft success)."
        )
    elif view.status == "WIN":
        st.success("WIN under protocol — human review only; never auto-promote.")
    elif view.status == "LOSE":
        st.info("LOSE under protocol.")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Primary IC baseline", _fmt_ic(view.primary_ic_baseline))
        st.metric("n_rows", view.n_rows)
    with c2:
        st.metric("Primary IC against", _fmt_ic(view.primary_ic_against))
        st.metric("Primary horizon", view.primary_horizon)
    with c3:
        st.metric("Folds reported", view.n_folds_reported)
        st.metric("min_folds_for_win", view.min_folds_for_win or "—")

    st.markdown("**Identities**")
    st.json(
        {
            "policy_id": view.policy_id,
            "protocol_id": view.protocol_id,
            "baseline_id": view.baseline_id,
            "against_id": view.against_id,
            "policy_hash": view.policy_hash,
            "observation_compatibility_id": view.observation_compatibility_id,
            "population_identity_kind": view.population_identity_kind,
            "population_identity_id": view.population_identity_id,
            "population_identity_detail": view.population_identity_detail,
            "production_snapshot_id": view.production_snapshot_id,
            "production_snapshot_digest": view.production_snapshot_digest,
            "production_policy_id": view.production_policy_id,
            "production_policy_version": view.production_policy_version,
            "production_semantic_engine_contract_id": (
                view.production_semantic_engine_contract_id
            ),
            "challenge_adapter_id": view.challenge_adapter_id,
            "challenge_adapter_version": view.challenge_adapter_version,
            "artifact_dir": view.artifact_dir,
        }
    )

    if view.fold_metrics:
        st.markdown("**Fold metrics**")
        st.dataframe(list(view.fold_metrics), use_container_width=True)
    if view.horizon_metrics:
        st.markdown("**Horizon metrics**")
        st.json(view.horizon_metrics)
    if view.weights:
        st.markdown("**Weights**")
        st.json(view.weights)

    st.markdown("**Notes / lines**")
    for line in view.lines:
        st.text(line)
    if view.notes:
        with st.expander("All notes"):
            for n in view.notes:
                st.markdown(f"- {n}")

    if view.summary_md:
        with st.expander("Summary markdown"):
            st.markdown(view.summary_md)

    st.info(f"**Human next step:** {view.human_next_step}")


def _fmt_ic(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.4f}"


def page_foundation() -> None:
    service = _service()
    overview = service.describe()
    render_sidebar(overview)
    render_foundation(overview)


def page_control_tower() -> None:
    service = _service()
    overview = service.describe()
    render_sidebar(overview)
    render_control_tower(service)


def page_cohort_discovery() -> None:
    service = _service()
    overview = service.describe()
    render_sidebar(overview)
    render_cohort_discovery(service)


def page_policy_catalog() -> None:
    service = _service()
    overview = service.describe()
    render_sidebar(overview)
    render_policy_catalog(service)


def page_run_challenge() -> None:
    service = _service()
    overview = service.describe()
    render_sidebar(overview)
    render_run_challenge(service)


def main() -> None:
    st.set_page_config(
        page_title="ml-saham Challenge Desk",
        page_icon="🧪",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    pages = [
        st.Page(page_foundation, title="Foundation", icon="🧱", default=True),
        st.Page(page_control_tower, title="Control Tower", icon="🗼"),
        st.Page(page_cohort_discovery, title="Cohort Discovery", icon="🧭"),
        st.Page(page_policy_catalog, title="Policy Catalog", icon="📚"),
        st.Page(page_run_challenge, title="Run Challenge", icon="▶️"),
    ]
    page = st.navigation(pages)
    page.run()


if __name__ == "__main__":
    main()
