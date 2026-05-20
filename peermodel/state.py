"""Node state tracking for per-cohort sync cursors (issue #24)."""

import sqlite3
from dataclasses import dataclass
from typing import Optional


@dataclass
class NodeState:
    """Tracks per-cohort, per-record-type synchronization state.

    Fields:
        cohort_id: Unique identifier for the cohort
        record_type: Type of record this state tracks
        last_synced_head_cid: CID of last synced head (None if never)
        last_synced_sequence: Sequence number of the last sync
        snapshot_cid: CID of the latest snapshot (None if no snapshot)
        snapshot_sequence: Sequence number of the latest snapshot
        index_status: Status ("cold", "building", "current", "stale")
        last_sync_at: ISO8601 timestamp of last sync (None if never)
    """

    cohort_id: str
    record_type: str
    last_synced_head_cid: Optional[str]
    last_synced_sequence: int
    snapshot_cid: Optional[str]
    snapshot_sequence: int
    index_status: str
    last_sync_at: Optional[str]


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Create the _node_state table if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS _node_state (
            cohort_id TEXT NOT NULL,
            record_type TEXT NOT NULL,
            last_synced_head_cid TEXT,
            last_synced_sequence INTEGER NOT NULL,
            snapshot_cid TEXT,
            snapshot_sequence INTEGER NOT NULL,
            index_status TEXT NOT NULL,
            last_sync_at TEXT,
            PRIMARY KEY (cohort_id, record_type)
        )
    """)
    conn.commit()


def get_node_state(
    conn: sqlite3.Connection,
    cohort_id: str,
    record_type: str
) -> Optional[NodeState]:
    """Retrieve node state from the database.

    Args:
        conn: SQLite connection
        cohort_id: Cohort identifier
        record_type: Record type identifier

    Returns:
        NodeState instance if found, None otherwise
    """
    _ensure_table(conn)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            cohort_id, record_type, last_synced_head_cid, last_synced_sequence,
            snapshot_cid, snapshot_sequence, index_status, last_sync_at
        FROM _node_state
        WHERE cohort_id = ? AND record_type = ?
    """, (cohort_id, record_type))

    row = cursor.fetchone()
    cursor.close()

    if row is None:
        return None

    return NodeState(
        cohort_id=row[0],
        record_type=row[1],
        last_synced_head_cid=row[2],
        last_synced_sequence=row[3],
        snapshot_cid=row[4],
        snapshot_sequence=row[5],
        index_status=row[6],
        last_sync_at=row[7]
    )


def set_node_state(conn: sqlite3.Connection, state: NodeState) -> None:
    """Save or update node state in the database (upsert).

    Args:
        conn: SQLite connection
        state: NodeState instance to save
    """
    _ensure_table(conn)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO _node_state (
            cohort_id, record_type, last_synced_head_cid, last_synced_sequence,
            snapshot_cid, snapshot_sequence, index_status, last_sync_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(cohort_id, record_type) DO UPDATE SET
            last_synced_head_cid = excluded.last_synced_head_cid,
            last_synced_sequence = excluded.last_synced_sequence,
            snapshot_cid = excluded.snapshot_cid,
            snapshot_sequence = excluded.snapshot_sequence,
            index_status = excluded.index_status,
            last_sync_at = excluded.last_sync_at
    """, (
        state.cohort_id,
        state.record_type,
        state.last_synced_head_cid,
        state.last_synced_sequence,
        state.snapshot_cid,
        state.snapshot_sequence,
        state.index_status,
        state.last_sync_at
    ))
    conn.commit()
    cursor.close()
