"""Raw read-only rows used by the ACCUM C0 readiness projection."""

from __future__ import annotations

import sqlite3

from ml_saham.data.aisaham_read import table_columns, table_exists

OBSERVATION_COLUMNS = frozenset(
    {
        "observation_id",
        "artifact_digest",
        "schema_version",
        "contract_id",
        "purpose",
        "policy_contract",
        "horizon_contract",
        "compatibility_id",
        "cutoff_at",
        "universe_id",
        "window_id",
        "decision_payload_json",
        "captured_at",
        "artifact_json",
    }
)

LABEL_COLUMNS = frozenset(
    {
        "label_id",
        "artifact_digest",
        "schema_version",
        "contract_id",
        "observation_id",
        "outcome_basis",
        "availability",
        "outcome",
        "metrics_json",
        "fingerprint",
        "labeled_at",
        "artifact_json",
    }
)


def fetch_accum_readiness_rows(
    conn: sqlite3.Connection, compatibility_id: str
) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    """Load one exact cohort and its labels; never auto-select or write."""
    if not compatibility_id.strip():
        raise ValueError("explicit ACCUM compatibility_id is required")
    if not table_exists(conn, "learning_observations"):
        raise ValueError("learning_observations table missing")
    missing = OBSERVATION_COLUMNS - table_columns(conn, "learning_observations")
    if missing:
        raise ValueError(
            "learning_observations missing columns: " + ", ".join(sorted(missing))
        )
    observations = conn.execute(
        "SELECT "
        + ", ".join(sorted(OBSERVATION_COLUMNS))
        + " FROM learning_observations "
        "WHERE purpose = 'ACCUMULATION_DISCOVERY' AND compatibility_id = ? "
        "ORDER BY cutoff_at, observation_id",
        (compatibility_id,),
    ).fetchall()

    if not table_exists(conn, "learning_outcome_labels"):
        return observations, []
    missing = LABEL_COLUMNS - table_columns(conn, "learning_outcome_labels")
    if missing:
        raise ValueError(
            "learning_outcome_labels missing columns: " + ", ".join(sorted(missing))
        )
    labels = conn.execute(
        "SELECT "
        + ", ".join(f"l.{c}" for c in sorted(LABEL_COLUMNS))
        + " FROM learning_outcome_labels l "
        "JOIN learning_observations o ON o.observation_id = l.observation_id "
        "WHERE o.purpose = 'ACCUMULATION_DISCOVERY' AND o.compatibility_id = ? "
        "ORDER BY l.observation_id, l.contract_id",
        (compatibility_id,),
    ).fetchall()
    return observations, labels


def fetch_snapshot_binding_claims(
    conn: sqlite3.Connection, compatibility_id: str
) -> tuple[int, tuple[str, ...]]:
    """Return raw snapshot count/contracts only for status precedence."""
    if not table_exists(conn, "learning_policy_snapshots"):
        return 0, ()
    columns = table_columns(conn, "learning_policy_snapshots")
    required = {"compatibility_id", "purpose", "contract_id"}
    if not required.issubset(columns):
        return 0, ()
    rows = conn.execute(
        "SELECT contract_id, COUNT(*) AS n FROM learning_policy_snapshots "
        "WHERE purpose = 'ACCUMULATION_DISCOVERY' AND compatibility_id = ? "
        "GROUP BY contract_id ORDER BY contract_id",
        (compatibility_id,),
    ).fetchall()
    return sum(int(row["n"]) for row in rows), tuple(
        str(row["contract_id"]) for row in rows
    )
