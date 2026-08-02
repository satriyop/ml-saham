"""Streamlit Challenge Desk — thin adapter over ChallengeWorkbenchService.

Phases: foundation, Control Tower, cohorts, catalog, Run, Artifact History
(compare + promote handoff). No SQLite/CLI scrape/scoring in the UI layer.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from ml_saham.challenge.workbench import (
    CAPABILITY_NOT_IMPLEMENTED,
    ArtifactOpenView,
    ChallengeRunRequest,
    ChallengeRunView,
    ChallengeWorkbenchOverview,
    ChallengeWorkbenchService,
    CohortInventoryResult,
    ControlTowerSnapshot,
    DiagnosticCatalogRow,
    HealthRunView,
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
        "Weekly ritual: open last health pack → refresh health when needed → "
        "dig policy runs on Run Challenge. Diagnostics never set Action."
    )
    st.info(
        "Tracks: **tune** · **factor** · **champion** · **diagnostic** "
        "(display / PROMOTE_CANDIDATE only — never Action)."
    )

    # --- Weekly ritual: last health + optional run -------------------------
    st.subheader("Weekly ritual")
    latest = service.latest_health_pack()
    if latest.found and latest.artifact_path:
        st.markdown(
            f"**Last health pack:** `{latest.artifact_path}`  \n"
            f"created_at=`{latest.created_at or '—'}` · "
            f"engine=`{latest.engine_id or '—'}` · "
            f"diagnostics=`{latest.with_diagnostics}` · "
            f"factors=`{latest.with_factors}` · "
            f"champion=`{latest.with_champion}` · "
            f"n_index=`{latest.n_index}`"
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Open last health pack", key="tower_open_health"):
                opened = service.open_challenge_artifact(latest.artifact_path)
                st.session_state.opened_artifact = opened
                st.session_state.tower_opened_health = opened
        with c2:
            st.caption(
                "CLI refresh: "
                "`ml-saham challenge health --with-diagnostics "
                "--compatibility-id <exact>`"
            )
        opened_health = st.session_state.get("tower_opened_health")
        if opened_health is not None and opened_health.ok:
            st.success(f"Opened health pack ({opened_health.status})")
            if opened_health.summary_md:
                with st.expander("Last health summary.md"):
                    st.markdown(opened_health.summary_md[:8000])
            # Expand index rows if present via control tower already
        elif opened_health is not None and not opened_health.ok:
            st.error(opened_health.error or "open failed")
    else:
        st.warning(
            "No health pack yet. Run weekly health below (or CLI) to create "
            "`artifacts/challenge/health/<ts>/`."
        )
        for note in latest.notes:
            st.caption(note)

    st.markdown("**Run weekly health** (explicit submit only)")
    inv = service.list_cohort_inventory()
    cohort_labels = [
        f"{r.purpose_family} | {r.compatibility_id} | n={r.observation_count}"
        for r in inv.rows
    ]
    with st.form("health_run_form"):
        if cohort_labels:
            cohort_choice = st.selectbox(
                "Compatibility ID (exact; required)",
                options=["— no selection —", *cohort_labels],
                index=0,
            )
        else:
            cohort_choice = "— no selection —"
            st.caption("No cohorts in inventory — fix upstream DB or use CLI.")
        scenario = st.selectbox(
            "Scenario filter",
            options=["(all)", "accum", "pre-open"],
            index=0,
        )
        with_diagnostics = st.checkbox(
            "with-diagnostics (recommended weekly)",
            value=True,
            help="Display bags only — never Action authority.",
        )
        with_factors = st.checkbox("with-factors (deeper dig)", value=False)
        with_champion = st.checkbox("with-champion (deeper dig)", value=False)
        write_artifact = st.checkbox("Write health pack", value=True)
        health_submit = st.form_submit_button("Run health", type="primary")

    if health_submit:
        if cohort_choice == "— no selection —":
            st.error("Select an exact compatibility identity before running health.")
        else:
            parts = [p.strip() for p in cohort_choice.split("|")]
            cid = parts[1] if len(parts) > 1 else ""
            sc = "" if scenario == "(all)" else scenario
            try:
                hreq = service.build_health_run_request(
                    compatibility_id=cid,
                    scenario=sc,
                    with_diagnostics=with_diagnostics,
                    with_factors=with_factors,
                    with_champion=with_champion,
                    write_artifact=write_artifact,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                attempt = service.new_attempt_id()
                with st.spinner(
                    f"Running weekly health (attempt {attempt}) — may take a while…"
                ):
                    hview = service.execute_health_run(
                        hreq,
                        attempt_id=attempt,
                        executed_keys=_executed_keys(),
                    )
                st.session_state.last_health_view = hview
                st.session_state.last_health_request = hreq

    hview: HealthRunView | None = st.session_state.get("last_health_view")
    if hview is not None:
        st.markdown(
            f"**Health status:** {_format_status(hview.status)} · "
            f"elapsed `{hview.elapsed_seconds:.1f}s` · "
            f"attempt `{hview.attempt_id}`"
        )
        if hview.kind == "application_error":
            st.error(f"Application error (not a market verdict): {hview.error_reference}")
        if hview.artifact_dir:
            st.success(f"Health pack: {hview.artifact_dir}")
        if hview.index:
            st.dataframe(list(hview.index), use_container_width=True)
        for line in hview.lines[:40]:
            st.text(line)
        if hview.summary_md:
            with st.expander("Health summary"):
                st.markdown(hview.summary_md[:12000])
        st.info(hview.human_next_step)

    st.divider()
    st.subheader("All historical challenge rows")
    snap: ControlTowerSnapshot = service.control_tower_snapshot(limit=100)
    st.markdown(f"**Inventory status:** `{snap.status}`")
    if snap.by_track:
        st.write("Counts by track:", dict(snap.by_track))
    for note in snap.notes:
        st.caption(note)
    if not snap.rows:
        st.warning(
            "No historical challenge packs found under the configured artifacts "
            "root. Run health or policy challenges to populate this view."
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


def render_artifact_history(service: ChallengeWorkbenchService) -> None:
    st.title("Artifact History")
    st.caption(
        "Phase 3: service-validated reopen only. Historical schemas are "
        "display-only and never gain promotion eligibility."
    )
    items = service.list_challenge_artifacts(limit=100)
    if not items:
        st.warning("No challenge packs under the configured artifacts root.")
        return

    records = [
        {
            "path": i.artifact_path,
            "status": _format_status(i.status),
            "status_raw": i.status,
            "mode": i.mode,
            "track": i.track,
            "policy_id": i.policy_id or "",
            "protocol_id": i.protocol_id or "",
            "baseline_id": i.baseline_id or "",
            "against_id": i.against_id or "",
            "schema": i.schema_version,
            "created_at": i.created_at or "",
            "promo_hint": i.promotion_eligible_hint,
            "promo_block": i.promotion_block_reason or "",
        }
        for i in items
    ]
    st.dataframe(records, use_container_width=True)

    paths = [i.artifact_path for i in items]
    selected = st.selectbox("Open pack", options=paths, index=0, key="hist_open_path")
    if st.button("Open selected pack", key="hist_open_btn"):
        opened = service.open_challenge_artifact(selected)
        st.session_state.opened_artifact = opened

    opened: ArtifactOpenView | None = st.session_state.get("opened_artifact")
    if opened is None:
        return

    st.divider()
    st.subheader("Opened pack")
    if not opened.ok:
        st.error(opened.error or "open failed")
        return

    st.markdown(
        f"**Status:** {_format_status(opened.status)} · "
        f"**schema:** `{opened.schema_version}` · "
        f"**historical_display_only:** `{opened.historical_display_only}`"
    )
    if opened.promotion_eligible:
        st.success("Promote-reopen gate currently passes (still human-only).")
    else:
        st.warning(
            f"Not promotion-eligible: {opened.promotion_block_reason}"
        )
    for note in opened.notes:
        st.caption(note)

    st.json(
        {
            "path": opened.artifact_path,
            "mode": opened.mode,
            "track": opened.track,
            "policy_id": opened.policy_id,
            "protocol_id": opened.protocol_id,
            "baseline_id": opened.baseline_id,
            "against_id": opened.against_id,
            "primary_horizon": opened.primary_horizon,
            "n_rows": opened.n_rows,
            "primary_ic_baseline": opened.primary_ic_baseline,
            "primary_ic_against": opened.primary_ic_against,
            "observation_compatibility_id": opened.observation_compatibility_id,
            "population_identity_kind": opened.population_identity_kind,
            "population_identity_id": opened.population_identity_id,
            "production_snapshot_id": opened.production_snapshot_id,
            "challenge_adapter_id": opened.challenge_adapter_id,
        }
    )
    if opened.fold_metrics:
        st.markdown("**Fold metrics**")
        st.dataframe(list(opened.fold_metrics), use_container_width=True)
    if opened.summary_md:
        with st.expander("summary.md"):
            st.markdown(opened.summary_md)

    st.markdown("**Validated files (exact-byte download)**")
    for f in opened.files:
        data, err = service.read_artifact_file_bytes(opened.artifact_path, f.name)
        if err or data is None:
            st.caption(f"{f.name}: {err}")
            continue
        st.download_button(
            label=f"Download {f.name} ({f.size_bytes} B)",
            data=data,
            file_name=f.name,
            mime="application/json"
            if f.media_hint == "json"
            else "text/markdown"
            if f.media_hint == "markdown"
            else "application/octet-stream",
            key=f"dl_{opened.artifact_path}_{f.name}",
        )

    st.divider()
    st.subheader("Create human review packet")
    st.caption(
        "Uses existing promote-packet path. Never auto-applies to ai-saham."
    )
    if st.button("Create promote packet", key="promo_btn"):
        packet = service.create_promote_packet(
            opened.artifact_path, write_artifact=True
        )
        st.session_state.last_promote = packet

    packet = st.session_state.get("last_promote")
    if packet is not None:
        if packet.ok:
            st.success(
                f"Promote pack written (auto_applied={packet.auto_applied}): "
                f"{packet.artifact_dir}"
            )
        else:
            st.error(packet.error or "promote packet failed")
        for line in packet.lines:
            st.text(line)
        if packet.summary_md:
            with st.expander("PROMOTE checklist"):
                st.markdown(packet.summary_md)


def render_artifact_compare(service: ChallengeWorkbenchService) -> None:
    st.title("Compare Artifacts")
    st.caption(
        "Computed deltas and winner banners only when the service proves "
        "compatible policy, protocol, population, horizons, mode/track."
    )
    items = service.list_challenge_artifacts(limit=100)
    paths = [i.artifact_path for i in items]
    if len(paths) < 2:
        st.warning("Need at least two packs under the artifacts root to compare.")
        return
    left = st.selectbox("Left pack", options=paths, index=0, key="cmp_left")
    right = st.selectbox(
        "Right pack",
        options=paths,
        index=min(1, len(paths) - 1),
        key="cmp_right",
    )
    if st.button("Compare", key="cmp_btn"):
        view = service.compare_challenge_artifacts(left, right)
        st.session_state.compare_view = view

    view = st.session_state.get("compare_view")
    if view is None:
        return
    st.markdown(
        f"**Compatible axes:** `{view.compatible}` · "
        f"Left `{view.left_status}` vs Right `{view.right_status}`"
    )
    st.dataframe(
        [
            {
                "axis": a.name,
                "left": a.left,
                "right": a.right,
                "compatible": a.compatible,
            }
            for a in view.axes
        ],
        use_container_width=True,
    )
    if not view.compatible:
        st.warning(
            "Incompatible — inspect packs separately. No delta, no winner banner."
        )
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Left IC(against)", _fmt_ic(view.left_ic_against))
            st.metric("Left IC(baseline)", _fmt_ic(view.left_ic_baseline))
        with c2:
            st.metric("Right IC(against)", _fmt_ic(view.right_ic_against))
            st.metric("Right IC(baseline)", _fmt_ic(view.right_ic_baseline))
        with c3:
            st.metric(
                "Δ IC(against) right−left",
                _fmt_ic(view.delta_ic_against),
            )
        if view.winner_banner:
            st.info(f"**Descriptive banner (not promotion):** {view.winner_banner}")
    for note in view.notes:
        st.caption(note)


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


def page_artifact_history() -> None:
    service = _service()
    overview = service.describe()
    render_sidebar(overview)
    render_artifact_history(service)


def page_artifact_compare() -> None:
    service = _service()
    overview = service.describe()
    render_sidebar(overview)
    render_artifact_compare(service)


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
        st.Page(page_artifact_history, title="Artifact History", icon="📦"),
        st.Page(page_artifact_compare, title="Compare", icon="⚖️"),
    ]
    page = st.navigation(pages)
    page.run()


if __name__ == "__main__":
    main()
