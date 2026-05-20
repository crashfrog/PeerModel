#!/usr/bin/env python

"""OperationRecord and canonical serialization for audit log operations.

This module defines the OperationRecord dataclass and provides canonical
CBOR serialization for signing and verification of operations.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import cbor2
import io


@dataclass
class OperationRecord:
    """Record of a single operation in the audit log.

    OperationRecords are immutable records of changes to the system,
    including document creation, updates, and deletion. Each operation
    is signed by the cohort and can be verified against the signature.

    Attributes:
        op_id: Unique identifier for this operation
        op_type: Type of operation (create, update, delete, etc.)
        cohort_id: ID of the cohort that performed the operation
        record_type: Type of document being operated on
        record_id: ID of the record being operated on
        sequence_number: Monotonic sequence number for this cohort
        payload: The operation data (None for delete/tombstone)
        previous_head_cid: CID of the previous operation (for chaining)
        timestamp: ISO format timestamp of the operation
        schema_version: Version of the operation schema
        signature: Ed25519 signature over canonical_op_bytes()
        signing_algorithm: Algorithm used for signing
            (ed25519, p256_ecdsa, etc.)
    """

    op_id: str
    op_type: str
    cohort_id: str
    record_type: str
    record_id: str
    sequence_number: int
    payload: Optional[Dict[str, Any]]
    previous_head_cid: Optional[str]
    timestamp: str
    schema_version: str
    signature: bytes
    signing_algorithm: str


def canonical_op_bytes(op: OperationRecord) -> bytes:
    """Generate canonical CBOR encoding of an OperationRecord for signing.

    This function produces a deterministic byte representation of an
    OperationRecord that is suitable for cryptographic signing. The
    encoding follows RFC 7049 section 3.9 for canonical CBOR format,
    which ensures:
    - Deterministic output (same input always produces same bytes)
    - Stable across different dictionary orderings
    - All fields except signature and signing_algorithm are included

    The signature and signing_algorithm fields are excluded because:
    - They will be computed/set after this function is called
    - Including them would create a circular dependency

    Args:
        op: OperationRecord to serialize

    Returns:
        Bytes containing the canonical CBOR encoding
    """
    # Create a dict with all fields except signature and signing_algorithm
    op_dict = {
        "op_id": op.op_id,
        "op_type": op.op_type,
        "cohort_id": op.cohort_id,
        "record_type": op.record_type,
        "record_id": op.record_id,
        "sequence_number": op.sequence_number,
        "payload": op.payload,
        "previous_head_cid": op.previous_head_cid,
        "timestamp": op.timestamp,
        "schema_version": op.schema_version,
    }

    # Encode to CBOR in canonical form (RFC 7049 section 3.9)
    # canonical=True ensures:
    # - Maps are sorted by keys
    # - Shortest encoding for each value
    # - Deterministic output
    output = io.BytesIO()
    cbor2.dump(op_dict, output, canonical=True)
    return output.getvalue()
