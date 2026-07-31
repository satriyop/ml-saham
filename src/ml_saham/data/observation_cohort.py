"""Single-cohort discipline for learning_observations (never mix rulebooks).

ai-saham stamps ``compatibility_id`` when material scoring/config forks.
Pooling multiple ids is like combining exam scores under different rulebooks.

When ``preferred`` is omitted and multiple cohorts exist, loaders may
auto-select the **largest n** (ties → newest max ``captured_at``). That
auto-select is for exploratory/curriculum paths only; production-facing
challenges require an explicit id via
``ml_saham.challenge.runner.require_production_compatibility_id`` before
calling resolve/fetch. Schemas without the column load unfiltered (legacy
fixtures).
"""

from __future__ import annotations

import sqlite3
from typing import Any, Sequence

from ml_saham.data.aisaham_read import table_exists

ACCUM_PURPOSES: tuple[str, ...] = (
    "ACCUMULATION_DISCOVERY",
    "ACCUM_PATH",
    "accum_10d",
)
ACCUM_PURPOSE_LIKE: tuple[str, ...] = ("%ACCUM%", "%accum%")

PRE_OPEN_PURPOSES: tuple[str, ...] = ("PRE_OPEN_AUCTION_DIRECTION",)
PRE_OPEN_PURPOSE_LIKE: tuple[str, ...] = ("%PRE_OPEN%", "%pre_open%")


def observation_columns(conn: sqlite3.Connection) -> set[str]:
    if not table_exists(conn, "learning_observations"):
        return set()
    return {
        r[1]
        for r in conn.execute("PRAGMA table_info(learning_observations)").fetchall()
    }


def list_compatibility_cohorts(
    conn: sqlite3.Connection,
    *,
    purposes: Sequence[str],
    purpose_like: Sequence[str] | None = None,
) -> list[tuple[str, int, str | None]]:
    """Return ``(compatibility_id, n_rows, max_captured_at)`` ordered largest first.

    Empty string stands for null/blank ids. Returns ``[]`` if table/column missing.
    """
    cols = observation_columns(conn)
    if "decision_payload_json" not in cols or "compatibility_id" not in cols:
        return []
    if not purposes:
        return []
    purpose_filter = ",".join("?" * len(purposes))
    sql = (
        "SELECT COALESCE(NULLIF(TRIM(compatibility_id), ''), '') AS cid, "
        "COUNT(*) AS n, MAX(captured_at) AS max_cap "
        "FROM learning_observations "
        f"WHERE purpose IN ({purpose_filter}) "
        "GROUP BY cid ORDER BY n DESC, max_cap DESC"
    )
    rows = conn.execute(sql, tuple(purposes)).fetchall()
    if not rows and purpose_like:
        like_clause = " OR ".join("purpose LIKE ?" for _ in purpose_like)
        sql_like = (
            "SELECT COALESCE(NULLIF(TRIM(compatibility_id), ''), '') AS cid, "
            "COUNT(*) AS n, MAX(captured_at) AS max_cap "
            "FROM learning_observations "
            f"WHERE ({like_clause}) "
            "GROUP BY cid ORDER BY n DESC, max_cap DESC"
        )
        rows = conn.execute(sql_like, tuple(purpose_like)).fetchall()
    out: list[tuple[str, int, str | None]] = []
    for r in rows:
        if isinstance(r, sqlite3.Row):
            cid, n, max_cap = r["cid"], int(r["n"]), r["max_cap"]
        else:
            cid, n, max_cap = str(r[0] or ""), int(r[1]), r[2]
        out.append((str(cid or ""), n, str(max_cap) if max_cap is not None else None))
    return out


def count_other_purpose_rows(
    conn: sqlite3.Connection,
    *,
    compatibility_id: str,
    selected_purpose: str,
) -> int:
    """Count rows sharing a cohort id but outside the selected purpose.

    Raw ``learning_observations`` SQL stays centralized in this module. Schema
    or query errors intentionally propagate so callers cannot report a false
    zero exclusion count.
    """
    row = conn.execute(
        """
        SELECT COUNT(*) FROM learning_observations
        WHERE compatibility_id = ?
          AND purpose != ?
        """,
        (compatibility_id, selected_purpose),
    ).fetchone()
    return int(row[0] or 0) if row else 0


def resolve_compatibility_id(
    conn: sqlite3.Connection,
    *,
    purposes: Sequence[str],
    purpose_like: Sequence[str] | None = None,
    preferred: str | None = None,
    family: str = "observations",
) -> tuple[str | None, list[str]]:
    """Pick exactly one ``compatibility_id`` (never mix).

    Returns ``(selected_id, notes)``:
    - ``None`` with empty notes → column missing (no filter).
    - string (possibly ``""``) → filter to that cohort only.
    """
    notes: list[str] = []
    cols = observation_columns(conn)
    if "compatibility_id" not in cols:
        return None, notes

    cohorts = list_compatibility_cohorts(
        conn, purposes=purposes, purpose_like=purpose_like
    )
    if not cohorts:
        notes.append(f"compatibility_id column present but no {family} rows")
        return None, notes

    if preferred is not None:
        pref = preferred.strip()
        match = next((c for c in cohorts if c[0] == pref), None)
        if match is None:
            avail = ", ".join(f"{_short(c[0])} n={c[1]}" for c in cohorts[:6])
            notes.append(
                f"compatibility_id={pref!r} not found among {family} cohorts "
                f"(available: {avail or 'none'})"
            )
            return pref, notes
        notes.append(f"compatibility_id={pref or '(untagged)'} (explicit) n={match[1]}")
        if len(cohorts) > 1:
            excluded = sum(c[1] for c in cohorts if c[0] != pref)
            notes.append(
                f"excluded {len(cohorts) - 1} other cohort(s) totaling n={excluded}"
            )
        return pref, notes

    if len(cohorts) == 1:
        cid, n, _ = cohorts[0]
        notes.append(f"compatibility_id={cid or '(untagged)'} (single cohort) n={n}")
        return cid, notes

    cid, n, _ = cohorts[0]
    others = ", ".join(f"{_short(c[0])} n={c[1]}" for c in cohorts[1:6])
    more = f" (+{len(cohorts) - 6} more)" if len(cohorts) > 6 else ""
    notes.append(
        f"compatibility_id auto-selected largest cohort "
        f"{_short(cid, 24)} n={n} of {len(cohorts)} {family} cohorts; "
        f"excluded: {others}{more}"
    )
    return cid, notes


def _short(cid: str, n: int = 16) -> str:
    if not cid:
        return "(untagged)"
    return (cid[:n] + "…") if len(cid) > n else cid


def _cohort_sql_fragment(
    resolved: str | None,
    cols: set[str],
) -> tuple[str, list[Any]]:
    if resolved is None or "compatibility_id" not in cols:
        return "", []
    if resolved == "":
        return " AND (compatibility_id IS NULL OR TRIM(compatibility_id) = '')", []
    return " AND compatibility_id = ?", [resolved]


def fetch_observation_raw(
    conn: sqlite3.Connection,
    *,
    purposes: Sequence[str],
    purpose_like: Sequence[str] | None = None,
    compatibility_id: str | None = None,
    preferred_compatibility_id: str | None = None,
    select: str = "purpose, captured_at, decision_payload_json",
    family: str = "observations",
    order: str = "ASC",
    limit: int | None = None,
) -> tuple[list[Any], list[str], str | None]:
    """Fetch learning_observations under a single compatibility cohort.

    Returns ``(rows, notes, resolved_id)``. ``resolved_id is None`` means no
    cohort filter (legacy schema).
    """
    notes: list[str] = []
    cols = observation_columns(conn)
    if "decision_payload_json" not in cols:
        return [], ["learning_observations.decision_payload_json missing"], None

    resolved = compatibility_id
    if resolved is None and "compatibility_id" in cols:
        resolved, cnotes = resolve_compatibility_id(
            conn,
            purposes=purposes,
            purpose_like=purpose_like,
            preferred=preferred_compatibility_id,
            family=family,
        )
        notes.extend(cnotes)
    elif resolved is not None:
        notes.append(f"compatibility_id={resolved or '(untagged)'} (caller-selected)")
    elif preferred_compatibility_id is not None and "compatibility_id" not in cols:
        notes.append(
            "compatibility_id preferred but column missing — loading unfiltered"
        )

    purpose_filter = ",".join("?" * len(purposes))
    where = f"purpose IN ({purpose_filter})"
    params: list[Any] = list(purposes)
    frag, frag_params = _cohort_sql_fragment(resolved, cols)
    where += frag
    params.extend(frag_params)

    order_sql = "ASC" if str(order).upper() != "DESC" else "DESC"
    limit_sql = f" LIMIT {int(limit)}" if limit is not None else ""
    sql = (
        f"SELECT {select} FROM learning_observations "
        f"WHERE {where} ORDER BY captured_at {order_sql}{limit_sql}"
    )
    rows = conn.execute(sql, params).fetchall()
    if not rows and purpose_like:
        like_clause = " OR ".join("purpose LIKE ?" for _ in purpose_like)
        where_like = f"({like_clause})"
        params_like: list[Any] = list(purpose_like)
        frag2, frag_params2 = _cohort_sql_fragment(resolved, cols)
        where_like += frag2
        params_like.extend(frag_params2)
        rows = conn.execute(
            f"SELECT {select} FROM learning_observations "
            f"WHERE {where_like} ORDER BY captured_at {order_sql}{limit_sql}",
            params_like,
        ).fetchall()
    return rows, notes, resolved


def fetch_accum_observation_raw(
    conn: sqlite3.Connection,
    *,
    compatibility_id: str | None = None,
    preferred_compatibility_id: str | None = None,
    select: str = "purpose, captured_at, decision_payload_json",
    order: str = "ASC",
    limit: int | None = None,
) -> tuple[list[Any], list[str], str | None]:
    """ACCUM family convenience wrapper."""
    return fetch_observation_raw(
        conn,
        purposes=ACCUM_PURPOSES,
        purpose_like=ACCUM_PURPOSE_LIKE,
        compatibility_id=compatibility_id,
        preferred_compatibility_id=preferred_compatibility_id,
        select=select,
        family="ACCUM",
        order=order,
        limit=limit,
    )


def fetch_pre_open_observation_raw(
    conn: sqlite3.Connection,
    *,
    compatibility_id: str | None = None,
    preferred_compatibility_id: str | None = None,
    select: str = "purpose, captured_at, decision_payload_json",
    order: str = "ASC",
    limit: int | None = None,
) -> tuple[list[Any], list[str], str | None]:
    """PRE_OPEN family convenience wrapper."""
    return fetch_observation_raw(
        conn,
        purposes=PRE_OPEN_PURPOSES,
        purpose_like=PRE_OPEN_PURPOSE_LIKE,
        compatibility_id=compatibility_id,
        preferred_compatibility_id=preferred_compatibility_id,
        select=select,
        family="PRE_OPEN",
        order=order,
        limit=limit,
    )


def payload_json_from_row(row: Any, *, has_oid: bool = False) -> Any:
    """Extract decision_payload_json from a fetch row (with/without observation_id)."""
    if isinstance(row, sqlite3.Row):
        return row["decision_payload_json"]
    # select order: [observation_id,] purpose, captured_at, decision_payload_json
    if has_oid:
        return row[3]
    return row[2]


def curriculum_payload_rows(
    conn: sqlite3.Connection,
    purpose: str,
    *,
    limit: int = 1000,
    include_captured_at: bool = False,
    preferred_compatibility_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Curriculum/chapter helper: one cohort of payload dicts (newest first).

    Returns rows shaped like ``{"decision_payload_json": ..., "captured_at": ...}``
    so existing chapter loops keep working.
    """
    purpose = str(purpose or "").strip()
    if not purpose:
        return [], ["purpose required"]

    # Exact purpose first; LIKE fallback only if empty (legacy purpose spellings).
    up = purpose.upper()
    if "PRE_OPEN" in up:
        purpose_like: Sequence[str] | None = PRE_OPEN_PURPOSE_LIKE
    elif "ACCUM" in up:
        purpose_like = ACCUM_PURPOSE_LIKE
    else:
        purpose_like = None

    select = (
        "decision_payload_json, captured_at"
        if include_captured_at
        else "decision_payload_json"
    )
    rows, notes, _ = fetch_observation_raw(
        conn,
        purposes=(purpose,),
        purpose_like=purpose_like,
        preferred_compatibility_id=preferred_compatibility_id,
        select=select,
        family=purpose,
        order="DESC",
        limit=limit,
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        if isinstance(r, sqlite3.Row):
            keys = r.keys()
            payload = (
                r["decision_payload_json"] if "decision_payload_json" in keys else r[0]
            )
            cap = (
                r["captured_at"]
                if include_captured_at and "captured_at" in keys
                else None
            )
        else:
            payload = r[0]
            cap = r[1] if include_captured_at and len(r) > 1 else None
        item: dict[str, Any] = {"decision_payload_json": payload}
        if include_captured_at:
            item["captured_at"] = cap
        out.append(item)
    return out, notes
