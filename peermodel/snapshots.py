#!/usr/bin/env python

"""Snapshot infrastructure for PeerModel (Issue #22).

Provides snapshot creation, signing, and canonical encoding for
database state snapshots.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any
import sqlite3
import uuid
import io

import cbor2

from peermodel.primitives import sign_bytes


__all__ = [
    'Snapshot',
    'SnapshotManager',
    'canonical_snapshot_bytes',
    'serialize_snapshot_to_cbor',
    'deserialize_snapshot_from_cbor',
    'publish_snapshot',
    'update_ipns_pointer',
]


@dataclass
class Snapshot:
    """Snapshot of database state at a point in time.

    A snapshot captures all live (non-tombstoned) records in a cohort
    at a specific sequence number, along with metadata and cryptographic
    signatures for verification.

    Attributes:
        cohort_id: ID of the cohort this snapshot represents
        snapshot_id: Unique identifier for this snapshot
        record_type: Type of records included in snapshot
        log_head_cid: CID of the operation log head at snapshot time
        sequence_number: Sequence number of the operation log
        records: List of live record dicts (non-tombstoned)
        created_at: ISO format timestamp when snapshot was created
        signature: Ed25519 signature over canonical_snapshot_bytes()
        signing_algorithm: Algorithm used for signing (ed25519, p256, etc.)
    """

    cohort_id: str
    snapshot_id: str
    record_type: str
    log_head_cid: str
    sequence_number: int
    records: List[Dict[str, Any]]
    created_at: str
    signature: bytes
    signing_algorithm: str


def canonical_snapshot_bytes(snapshot: Snapshot) -> bytes:
    """Generate canonical CBOR encoding of a Snapshot for signing.

    This function produces a deterministic byte representation of a
    Snapshot that is suitable for cryptographic signing. The encoding
    follows RFC 7049 section 3.9 for canonical CBOR format, which ensures:
    - Deterministic output (same input always produces same bytes)
    - Stable across different dictionary orderings
    - All fields except signature are included

    The signature field is excluded because it will be computed/set
    after this function is called, which would create a circular dependency.

    Args:
        snapshot: Snapshot to serialize

    Returns:
        Bytes containing the canonical CBOR encoding
    """
    # Create a dict with all fields except signature
    snapshot_dict = {
        "cohort_id": snapshot.cohort_id,
        "snapshot_id": snapshot.snapshot_id,
        "record_type": snapshot.record_type,
        "log_head_cid": snapshot.log_head_cid,
        "sequence_number": snapshot.sequence_number,
        "records": snapshot.records,
        "created_at": snapshot.created_at,
        "signing_algorithm": snapshot.signing_algorithm,
    }

    # Encode to CBOR in canonical form (RFC 7049 section 3.9)
    # canonical=True ensures:
    # - Maps are sorted by keys
    # - Shortest encoding for each value
    # - Deterministic output
    output = io.BytesIO()
    cbor2.dump(snapshot_dict, output, canonical=True)
    return output.getvalue()


def serialize_snapshot_to_cbor(snapshot: Snapshot) -> bytes:
    """Serialize a Snapshot to CBOR bytes, including the signature field."""
    snapshot_dict = {
        "cohort_id": snapshot.cohort_id,
        "snapshot_id": snapshot.snapshot_id,
        "record_type": snapshot.record_type,
        "log_head_cid": snapshot.log_head_cid,
        "sequence_number": snapshot.sequence_number,
        "records": snapshot.records,
        "created_at": snapshot.created_at,
        "signature": snapshot.signature,
        "signing_algorithm": snapshot.signing_algorithm,
    }
    output = io.BytesIO()
    cbor2.dump(snapshot_dict, output, canonical=True)
    return output.getvalue()


def deserialize_snapshot_from_cbor(cbor_bytes: bytes) -> Snapshot:
    """Deserialize a Snapshot from CBOR bytes."""
    data = cbor2.loads(cbor_bytes)
    return Snapshot(
        cohort_id=data["cohort_id"],
        snapshot_id=data["snapshot_id"],
        record_type=data["record_type"],
        log_head_cid=data["log_head_cid"],
        sequence_number=data["sequence_number"],
        records=data["records"],
        created_at=data["created_at"],
        signature=data["signature"],
        signing_algorithm=data["signing_algorithm"],
    )


def publish_snapshot(snapshot: Snapshot, ipfs_client) -> str:
    """Serialize snapshot to CBOR and publish to IPFS. Returns CID string."""
    cbor_bytes = serialize_snapshot_to_cbor(snapshot)
    result = ipfs_client.add(cbor_bytes)
    return result["Hash"]


def update_ipns_pointer(cohort_id: str, record_type: str, cid: str, ipfs_client) -> str:
    """Publish snapshot CID to IPNS under canonical key name. Returns key name."""
    key_name = f"peermodel:{cohort_id}:{record_type}:snapshot"
    ipfs_client.name.publish(f"/ipfs/{cid}", key=key_name)
    return key_name


class SnapshotManager:
    """Manager for creating and signing snapshots."""

    def create_snapshot(
        self,
        db,
        model_class,
        cohort_id: str,
        record_type: str,
        log_head_cid: str,
        sequence_number: int,
        signing_private_key: bytes,
        signing_algorithm: str = "ed25519",
    ) -> Snapshot:
        """Create a snapshot of live records from the database.

        Reads all live (non-tombstoned) records from the SQLite table
        for the given model class, constructs a Snapshot dataclass,
        and signs it with the provided cohort private key.

        Args:
            db: IndexDB instance containing the records
            model_class: Model class defining the record type
            cohort_id: ID of the cohort
            record_type: Type of records (model name)
            log_head_cid: CID of the operation log head
            sequence_number: Current sequence number
            signing_private_key: DER-encoded private key for signing
            signing_algorithm: Algorithm to use for signing (default: ed25519)

        Returns:
            Snapshot: Signed snapshot with all live records

        Raises:
            Exception: If database query or signing fails
        """
        # Read live records from database
        records = self._read_live_records(db, model_class)

        # Generate unique snapshot ID
        snapshot_id = str(uuid.uuid4())

        # Create timestamp (timezone-aware UTC)
        created_at = datetime.now(timezone.utc).isoformat()

        # Create snapshot (without signature initially)
        snapshot = Snapshot(
            cohort_id=cohort_id,
            snapshot_id=snapshot_id,
            record_type=record_type,
            log_head_cid=log_head_cid,
            sequence_number=sequence_number,
            records=records,
            created_at=created_at,
            signature=b'',  # Placeholder
            signing_algorithm=signing_algorithm,
        )

        # Get canonical bytes for signing
        snapshot_bytes = canonical_snapshot_bytes(snapshot)

        # Sign the snapshot
        signature = sign_bytes(
            snapshot_bytes,
            signing_private_key,
            algorithm=signing_algorithm
        )

        # Update snapshot with signature
        snapshot.signature = signature

        return snapshot

    def _read_live_records(self, db, model_class) -> List[Dict[str, Any]]:
        """Read all live (non-tombstoned) records from the database.

        Queries the SQLite table for the given model class, filtering
        to only non-tombstoned records (_tombstoned = 0).

        Args:
            db: IndexDB instance
            model_class: Model class defining the table name

        Returns:
            List of record dicts, each containing all columns
        """
        table_name = model_class.__name__
        conn = sqlite3.connect(db.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dicts
        cursor = conn.cursor()

        try:
            # Query all non-tombstoned records
            cursor.execute(
                f"SELECT * FROM {table_name} WHERE _tombstoned = 0"
            )
            rows = cursor.fetchall()

            # Convert Row objects to dicts
            records = [dict(row) for row in rows]

            return records
        finally:
            conn.close()
