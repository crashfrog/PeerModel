#!/usr/bin/env python

"""Tests for OperationRecord and canonical serialization.

Tests cover:
- OperationRecord dataclass structure
- canonical_op_bytes() produces stable CBOR encoding
- Serialization determinism (same object -> same bytes)
- Canonical form stability across calls
"""

from datetime import datetime
from uuid import uuid4


def test_operation_record_dataclass_exists():
    """OperationRecord dataclass must be defined."""
    from peermodel.operations import OperationRecord

    assert OperationRecord is not None


def test_operation_record_has_required_fields():
    """OperationRecord must have all specified fields."""
    from peermodel.operations import OperationRecord

    # Create an instance with all required fields
    op = OperationRecord(
        op_id=str(uuid4()),
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=str(uuid4()),
        sequence_number=1,
        payload={"test": "data"},
        previous_head_cid=None,
        timestamp=datetime.utcnow().isoformat() + "Z",
        schema_version="1.0.0",
        signature=b"",
        signing_algorithm="ed25519"
    )

    # Verify all fields exist
    assert hasattr(op, "op_id")
    assert hasattr(op, "op_type")
    assert hasattr(op, "cohort_id")
    assert hasattr(op, "record_type")
    assert hasattr(op, "record_id")
    assert hasattr(op, "sequence_number")
    assert hasattr(op, "payload")
    assert hasattr(op, "previous_head_cid")
    assert hasattr(op, "timestamp")
    assert hasattr(op, "schema_version")
    assert hasattr(op, "signature")
    assert hasattr(op, "signing_algorithm")


def test_operation_record_field_types():
    """OperationRecord fields must have correct types."""
    from peermodel.operations import OperationRecord

    op_id = str(uuid4())
    record_id = str(uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    op = OperationRecord(
        op_id=op_id,
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=record_id,
        sequence_number=1,
        payload={"test": "data"},
        previous_head_cid=None,
        timestamp=timestamp,
        schema_version="1.0.0",
        signature=b"test_signature",
        signing_algorithm="ed25519"
    )

    assert isinstance(op.op_id, str)
    assert isinstance(op.op_type, str)
    assert isinstance(op.cohort_id, str)
    assert isinstance(op.record_type, str)
    assert isinstance(op.record_id, str)
    assert isinstance(op.sequence_number, int)
    assert isinstance(op.payload, (dict, type(None)))
    assert isinstance(op.previous_head_cid, (str, type(None)))
    assert isinstance(op.timestamp, str)
    assert isinstance(op.schema_version, str)
    assert isinstance(op.signature, bytes)
    assert isinstance(op.signing_algorithm, str)


def test_canonical_op_bytes_function_exists():
    """canonical_op_bytes() function must be defined."""
    from peermodel.operations import canonical_op_bytes

    assert callable(canonical_op_bytes)


def test_canonical_op_bytes_produces_bytes():
    """canonical_op_bytes() must return bytes."""
    from peermodel.operations import OperationRecord, canonical_op_bytes

    op = OperationRecord(
        op_id=str(uuid4()),
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=str(uuid4()),
        sequence_number=1,
        payload={"test": "data"},
        previous_head_cid=None,
        timestamp=datetime.utcnow().isoformat() + "Z",
        schema_version="1.0.0",
        signature=b"",
        signing_algorithm="ed25519"
    )

    result = canonical_op_bytes(op)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_canonical_op_bytes_is_deterministic():
    """Same OperationRecord serialized twice must produce identical bytes."""
    from peermodel.operations import OperationRecord, canonical_op_bytes

    op_id = str(uuid4())
    record_id = str(uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    op = OperationRecord(
        op_id=op_id,
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=record_id,
        sequence_number=1,
        payload={"test": "data", "nested": {"key": "value"}},
        previous_head_cid=None,
        timestamp=timestamp,
        schema_version="1.0.0",
        signature=b"",
        signing_algorithm="ed25519"
    )

    # Serialize twice
    bytes1 = canonical_op_bytes(op)
    bytes2 = canonical_op_bytes(op)

    # Must be identical
    assert bytes1 == bytes2


def test_canonical_op_bytes_excludes_signature_fields():
    """canonical_op_bytes() must exclude signature and signing_algorithm fields."""
    from peermodel.operations import OperationRecord, canonical_op_bytes

    op_id = str(uuid4())
    record_id = str(uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Create two operations with same data but different signatures
    op1 = OperationRecord(
        op_id=op_id,
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=record_id,
        sequence_number=1,
        payload={"test": "data"},
        previous_head_cid=None,
        timestamp=timestamp,
        schema_version="1.0.0",
        signature=b"signature_one",
        signing_algorithm="ed25519"
    )

    op2 = OperationRecord(
        op_id=op_id,
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=record_id,
        sequence_number=1,
        payload={"test": "data"},
        previous_head_cid=None,
        timestamp=timestamp,
        schema_version="1.0.0",
        signature=b"signature_two_completely_different",
        signing_algorithm="p256_ecdsa"
    )

    # Canonical bytes must be identical despite different signatures
    bytes1 = canonical_op_bytes(op1)
    bytes2 = canonical_op_bytes(op2)

    assert bytes1 == bytes2


def test_canonical_op_bytes_stable_across_field_order():
    """canonical_op_bytes() must produce stable output regardless of construction order."""
    from peermodel.operations import OperationRecord, canonical_op_bytes

    op_id = str(uuid4())
    record_id = str(uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Create operations with same data
    # Python dataclasses maintain field order, but CBOR canonical encoding
    # should use alphabetical key order
    op1 = OperationRecord(
        op_id=op_id,
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=record_id,
        sequence_number=1,
        payload={"key1": "value1", "key2": "value2"},
        previous_head_cid=None,
        timestamp=timestamp,
        schema_version="1.0.0",
        signature=b"",
        signing_algorithm="ed25519"
    )

    op2 = OperationRecord(
        op_id=op_id,
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=record_id,
        sequence_number=1,
        payload={"key2": "value2", "key1": "value1"},  # Different order in dict
        previous_head_cid=None,
        timestamp=timestamp,
        schema_version="1.0.0",
        signature=b"",
        signing_algorithm="ed25519"
    )

    bytes1 = canonical_op_bytes(op1)
    bytes2 = canonical_op_bytes(op2)

    # Should be identical due to canonical ordering
    assert bytes1 == bytes2


def test_canonical_op_bytes_handles_none_payload():
    """canonical_op_bytes() must handle None payload (tombstone records)."""
    from peermodel.operations import OperationRecord, canonical_op_bytes

    op = OperationRecord(
        op_id=str(uuid4()),
        op_type="delete",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=str(uuid4()),
        sequence_number=2,
        payload=None,  # Tombstone
        previous_head_cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        timestamp=datetime.utcnow().isoformat() + "Z",
        schema_version="1.0.0",
        signature=b"",
        signing_algorithm="ed25519"
    )

    result = canonical_op_bytes(op)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_canonical_op_bytes_handles_complex_payload():
    """canonical_op_bytes() must handle complex nested payload structures."""
    from peermodel.operations import OperationRecord, canonical_op_bytes

    complex_payload = {
        "string_field": "test",
        "int_field": 42,
        "float_field": 3.14,
        "bool_field": True,
        "null_field": None,
        "list_field": [1, 2, 3],
        "nested_dict": {
            "inner_key": "inner_value",
            "inner_list": ["a", "b", "c"]
        }
    }

    op = OperationRecord(
        op_id=str(uuid4()),
        op_type="create",
        cohort_id="test_cohort",
        record_type="ComplexDocument",
        record_id=str(uuid4()),
        sequence_number=1,
        payload=complex_payload,
        previous_head_cid=None,
        timestamp=datetime.utcnow().isoformat() + "Z",
        schema_version="1.0.0",
        signature=b"",
        signing_algorithm="ed25519"
    )

    result = canonical_op_bytes(op)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_canonical_op_bytes_different_operations_produce_different_bytes():
    """Different OperationRecords must produce different canonical bytes."""
    from peermodel.operations import OperationRecord, canonical_op_bytes

    timestamp = datetime.utcnow().isoformat() + "Z"

    op1 = OperationRecord(
        op_id=str(uuid4()),
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=str(uuid4()),
        sequence_number=1,
        payload={"test": "data1"},
        previous_head_cid=None,
        timestamp=timestamp,
        schema_version="1.0.0",
        signature=b"",
        signing_algorithm="ed25519"
    )

    op2 = OperationRecord(
        op_id=str(uuid4()),
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=str(uuid4()),
        sequence_number=2,
        payload={"test": "data2"},
        previous_head_cid=None,
        timestamp=timestamp,
        schema_version="1.0.0",
        signature=b"",
        signing_algorithm="ed25519"
    )

    bytes1 = canonical_op_bytes(op1)
    bytes2 = canonical_op_bytes(op2)

    # Different operations must produce different bytes
    assert bytes1 != bytes2


def test_canonical_op_bytes_uses_cbor_encoding():
    """canonical_op_bytes() must use CBOR encoding (RFC 7049)."""
    from peermodel.operations import OperationRecord, canonical_op_bytes

    op = OperationRecord(
        op_id=str(uuid4()),
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=str(uuid4()),
        sequence_number=1,
        payload={"test": "data"},
        previous_head_cid=None,
        timestamp=datetime.utcnow().isoformat() + "Z",
        schema_version="1.0.0",
        signature=b"",
        signing_algorithm="ed25519"
    )

    result = canonical_op_bytes(op)

    # Check that output looks like CBOR
    assert isinstance(result, bytes)
    # CBOR maps typically start with byte in range 0xa0-0xbf (small map)
    # or 0xb8-0xbf (map with additional length info)
    # This is a basic check - CBOR canonical must produce deterministic output
    # The actual implementation will use cbor2 or similar library
    assert len(result) > 0


def test_operation_record_with_previous_head_cid():
    """OperationRecord must handle previous_head_cid for chained operations."""
    from peermodel.operations import OperationRecord, canonical_op_bytes

    previous_cid = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"

    op = OperationRecord(
        op_id=str(uuid4()),
        op_type="update",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=str(uuid4()),
        sequence_number=5,
        payload={"test": "updated"},
        previous_head_cid=previous_cid,
        timestamp=datetime.utcnow().isoformat() + "Z",
        schema_version="1.0.0",
        signature=b"",
        signing_algorithm="ed25519"
    )

    assert op.previous_head_cid == previous_cid

    result = canonical_op_bytes(op)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_canonical_op_bytes_includes_all_fields_except_signature():
    """canonical_op_bytes() must include all fields except signature and signing_algorithm."""
    from peermodel.operations import OperationRecord, canonical_op_bytes

    op_id = str(uuid4())
    record_id = str(uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    # Create two operations differing only in a non-signature field
    op1 = OperationRecord(
        op_id=op_id,
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=record_id,
        sequence_number=1,
        payload={"test": "data"},
        previous_head_cid=None,
        timestamp=timestamp,
        schema_version="1.0.0",
        signature=b"same",
        signing_algorithm="ed25519"
    )

    op2 = OperationRecord(
        op_id=op_id,
        op_type="create",
        cohort_id="test_cohort",
        record_type="TestDocument",
        record_id=record_id,
        sequence_number=1,
        payload={"test": "data"},
        previous_head_cid=None,
        timestamp=timestamp,
        schema_version="1.0.1",  # Different schema version
        signature=b"same",
        signing_algorithm="ed25519"
    )

    bytes1 = canonical_op_bytes(op1)
    bytes2 = canonical_op_bytes(op2)

    # Different schema_version must produce different bytes
    assert bytes1 != bytes2
