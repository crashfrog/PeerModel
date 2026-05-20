#!/usr/bin/env python

"""OperationRecord and canonical serialization for distributed ledger.

Defines OperationRecord dataclass and canonical_op_bytes() function for
stable deterministic CBOR-encoded signatures (excluding signature fields).
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import cbor2
from io import BytesIO


@dataclass
class OperationRecord:
    """Record of a single operation in the distributed ledger.

    Fields:
        op_id: Unique operation identifier
        op_type: Type of operation (create, update, delete, etc.)
        cohort_id: ID of the cohort that owns this record
        record_type: Type of the record being operated on
        record_id: ID of the record being operated on
        sequence_number: Sequential number for ordering within cohort
        payload: Operation payload (data written, or None for tombstone)
        previous_head_cid: CID of previous record in chain (or None)
        timestamp: ISO 8601 timestamp of operation
        schema_version: Version of the record schema
        signature: Cryptographic signature (ed25519 or similar)
        signing_algorithm: Signature algorithm (ed25519, p256_ecdsa, etc.)
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
    """Produce stable, deterministic CBOR encoding for operation signing.

    Excludes signature and signing_algorithm fields (these are computed over
    the canonical bytes, so they cannot be included). Uses CBOR canonical
    encoding (RFC 7049 section 3.9) to ensure deterministic serialization.

    Args:
        op: OperationRecord to serialize

    Returns:
        Bytes containing canonical CBOR encoding of all fields except
        signature and signing_algorithm
    """
    # Create a dict with all fields except signature and signing_algorithm
    # Fields are ordered alphabetically for canonical encoding
    data = {
        "cohort_id": op.cohort_id,
        "op_id": op.op_id,
        "op_type": op.op_type,
        "payload": op.payload,
        "previous_head_cid": op.previous_head_cid,
        "record_id": op.record_id,
        "record_type": op.record_type,
        "schema_version": op.schema_version,
        "sequence_number": op.sequence_number,
        "timestamp": op.timestamp,
    }

    # Encode with CBOR canonical form
    # canonical=True ensures RFC 7049 section 3.9 deterministic encoding
    buf = BytesIO()
    cbor2.dump(data, buf, canonical=True)
    return buf.getvalue()
