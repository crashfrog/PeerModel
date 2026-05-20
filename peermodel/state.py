#!/usr/bin/env python

"""Node state tracking for per-cohort sync cursors (issue #24)."""

import sqlite3
from dataclasses import dataclass
from typing import Optional


@dataclass
class NodeState:
    """Tracks sync state for a specific cohort and record type.

    Attributes:
        cohort_id: Identifier for the cohort
        record_type: Type of record being tracked
        last_synced_head_cid: CID of last synced head
            (None if never synced)
        last_synced_sequence: Sequence number of last synced head
        snapshot_cid: CID of most recent snapshot (None if no snapshot)
        snapshot_sequence: Sequence number of the snapshot
        index_status: Current index status
            ('cold', 'building', 'current', 'stale')
        last_sync_at: ISO timestamp of last sync
            (None if never synced)
    """
    cohort_id: str
    record_type: str
    last_synced_head_cid: Optional[str]
    last_synced_sequence: int
    snapshot_cid: Optional[str]
    snapshot_sequence: int
    # 'cold', 'building', 'current', 'stale'
    index_status: str
    last_sync_at: Optional[str]


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Create _node_state table if it doesn't exist."""
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
    cursor.close()


def get_node_state(
    conn: sqlite3.Connection,
    cohort_id: str,
    record_type: str
) -> Optional[NodeState]:
    """Retrieve node state for a specific cohort and record type.

    Args:
        conn: SQLite database connection
        cohort_id: Identifier for the cohort
        record_type: Type of record

    Returns:
        NodeState instance if found, None otherwise
    """
    _ensure_table(conn)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT cohort_id, record_type, last_synced_head_cid,
               last_synced_sequence, snapshot_cid, snapshot_sequence,
               index_status, last_sync_at
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
    """Create or update node state (upsert).

    Args:
        conn: SQLite database connection
        state: NodeState instance to save
    """
    _ensure_table(conn)

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO _node_state (
            cohort_id, record_type, last_synced_head_cid,
            last_synced_sequence, snapshot_cid, snapshot_sequence,
            index_status, last_sync_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
