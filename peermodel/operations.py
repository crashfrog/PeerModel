#!/usr/bin/env python

"""OperationRecord and canonical serialization for audit log operations.

This module defines the OperationRecord dataclass and provides canonical
CBOR serialization for signing and verification of operations.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import cbor2
import io
import asyncio
import logging

from peermodel.exceptions import LogIntegrityError
import peermodel.primitives

logger = logging.getLogger(__name__)


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


def verify_operation(op: OperationRecord) -> bool:
    """Verify the signature on an OperationRecord.

    This is a placeholder that always returns True for now.
    Full signature verification requires cohort public key lookup.

    Args:
        op: OperationRecord to verify

    Returns:
        True if signature is valid, False otherwise
    """
    # TODO: Implement actual signature verification
    # Need to look up cohort public key from cohort_id
    return True


async def traverse(
    head_cid: Optional[str],
    stop_at_cid: Optional[str] = None,
    ipfs_client=None,
    concurrency: int = 50,
) -> List[OperationRecord]:
    """Traverse operation log from head to genesis.

    Fetches the operation log chain starting from head_cid and following
    previous_head_cid links until reaching genesis (None) or stop_at_cid.

    Operations are fetched concurrently with a semaphore limiting parallel
    requests. Signatures are verified and invalid signatures are skipped
    with warnings logged.

    Args:
        head_cid: CID of the head operation (most recent)
        stop_at_cid: Optional CID to stop traversal at (exclusive)
        ipfs_client: Client with async fetch(cid) method
        concurrency: Max concurrent IPFS fetches (default 50)

    Returns:
        List of OperationRecords in chronological order
        (oldest first, ascending sequence_number)

    Raises:
        LogIntegrityError: If log has serious integrity issues:
            - >10% of operations have invalid signatures
            - Non-contiguous sequence numbers (gaps in chain)
            - Missing CIDs that cannot be fetched
    """
    if head_cid is None:
        return []

    # Phase 1: Sequential discovery - build CID chain
    cids_to_fetch = []
    current_cid = head_cid

    # Special behavior when stop_at_cid is set:
    # Skip the head and start from its previous
    if stop_at_cid is not None:
        try:
            op = await ipfs_client.fetch(current_cid)
            current_cid = op.previous_head_cid
        except Exception as e:
            raise LogIntegrityError(
                f"Missing CID {head_cid}: {e}"
            )

    # Traverse backwards
    while current_cid is not None:
        cids_to_fetch.append(current_cid)
        # Stop after adding stop_at_cid (it's the last one to include)
        if current_cid == stop_at_cid:
            break
        # Fetch this operation to get next CID
        try:
            op = await ipfs_client.fetch(current_cid)
            current_cid = op.previous_head_cid
        except Exception as e:
            raise LogIntegrityError(
                f"Missing CID {current_cid}: {e}"
            )

    # Phase 2: Parallel fetch all operations
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_with_semaphore(cid):
        async with semaphore:
            return await ipfs_client.fetch(cid)

    operations = await asyncio.gather(
        *[fetch_with_semaphore(cid) for cid in cids_to_fetch]
    )

    # Phase 3: Verify signatures
    valid_ops = []
    invalid_count = 0

    for op in operations:
        if verify_operation(op):
            valid_ops.append(op)
        else:
            invalid_count += 1
            logger.warning(
                f"Invalid signature on op {op.op_id} "
                f"(seq {op.sequence_number})"
            )

    # Check integrity threshold (only for chains >= 10 operations)
    if len(operations) >= 10:
        invalid_percentage = (invalid_count / len(operations)) * 100
        if invalid_percentage > 10:
            raise LogIntegrityError(
                f"Log integrity failure: {invalid_percentage:.1f}% "
                f"invalid signatures ({invalid_count}/{len(operations)})"
            )

    operations = valid_ops

    # Phase 4: Sort by sequence_number (chronological order)
    operations.sort(key=lambda op: op.sequence_number)

    # Phase 5: Verify sequence contiguity (only if no ops were skipped)
    if invalid_count == 0 and len(operations) > 1:
        for i in range(len(operations) - 1):
            current_seq = operations[i].sequence_number
            next_seq = operations[i + 1].sequence_number
            if next_seq != current_seq + 1:
                raise LogIntegrityError(
                    f"Non-contiguous sequence numbers: "
                    f"{current_seq} -> {next_seq}"
                )

    return operations
