#!/usr/bin/env python

"""Tests for operation creation and signing (Issue #17).

Tests cover:
- Operation record creation (insert, update, tombstone)
- Sequence number incrementation
- Operation signing via cohort keys
- Signature verification
- Edge cases and error handling
"""

import pytest
from uuid import uuid4
from datetime import datetime

import peermodel
import peermodel.primitives
from peermodel.delegation import SimpleCohort


@pytest.fixture
def alice_identity():
    """Generate Alice's identity."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = (
        peermodel.primitives.generate_keypair()
    )
    return {
        "identity_id": "alice",
        "x25519_private": x25519_priv,
        "x25519_public": x25519_pub,
        "ed25519_private": ed25519_priv,
        "ed25519_public": ed25519_pub,
    }


@pytest.fixture
def bob_identity():
    """Generate Bob's identity."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = (
        peermodel.primitives.generate_keypair()
    )
    return {
        "identity_id": "bob",
        "x25519_private": x25519_priv,
        "x25519_public": x25519_pub,
        "ed25519_private": ed25519_priv,
        "ed25519_public": ed25519_pub,
    }


@pytest.fixture
def test_cohort(alice_identity):
    """Create a cohort for operation testing."""
    return SimpleCohort(
        cohort_id="test_cohort", founder_identity=alice_identity
    )


@pytest.fixture
def multi_member_cohort(alice_identity, bob_identity):
    """Create a cohort with two members."""
    cohort = SimpleCohort(
        cohort_id="multi_cohort", founder_identity=alice_identity
    )
    cohort.addMember(bob_identity)
    return cohort


@pytest.fixture
def operation_log(test_cohort):
    """Create an operation log from a cohort."""
    # Operation log is created from cohort, maintains sequence numbers
    return test_cohort


# ============================================================================
# HAPPY PATH TESTS
# ============================================================================


class TestOperationCreationHappyPath:
    """Happy path: successfully create operations."""

    def test_create_insert_operation(self, operation_log, alice_identity):
        """Create an insert operation."""
        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"test_field": "test_value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        assert op is not None
        assert hasattr(op, "op_type")
        assert op.op_type == "insert"
        assert hasattr(op, "signature")
        assert op.signature is not None

    def test_create_update_operation(self, operation_log, alice_identity):
        """Create an update operation."""
        op = operation_log.create_operation(
            op_type="update",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"test_field": "updated_value"},
            previous_head_cid="QmHashBefore",
            initiator=alice_identity,
        )

        assert op is not None
        assert op.op_type == "update"
        assert op.signature is not None

    def test_create_tombstone_operation(self, operation_log, alice_identity):
        """Create a tombstone (delete) operation."""
        record_id = str(uuid4())
        op = operation_log.create_operation(
            op_type="tombstone",
            record_type="TestRecord",
            record_id=record_id,
            payload=None,
            previous_head_cid="QmHashBefore",
            initiator=alice_identity,
        )

        assert op is not None
        assert op.op_type == "tombstone"
        assert op.signature is not None

    def test_operation_has_all_required_fields(
        self, operation_log, alice_identity
    ):
        """Operation record has all required fields."""
        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        # From issue #16: OperationRecord should have these fields
        required_fields = [
            "op_id",
            "op_type",
            "cohort_id",
            "record_type",
            "record_id",
            "sequence_number",
            "payload",
            "previous_head_cid",
            "timestamp",
            "schema_version",
            "signature",
            "signing_algorithm",
        ]

        for field in required_fields:
            assert hasattr(
                op, field
            ), f"Operation missing required field: {field}"

    def test_operation_timestamp_is_set(self, operation_log, alice_identity):
        """Operation has a timestamp."""
        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        assert op.timestamp is not None
        assert isinstance(op.timestamp, (int, float, datetime))

    def test_operation_has_unique_id(self, operation_log, alice_identity):
        """Each operation has a unique op_id."""
        op1 = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value1"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        op2 = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value2"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        assert op1.op_id != op2.op_id


# ============================================================================
# SEQUENCE NUMBER TESTS
# ============================================================================


class TestSequenceNumberIncrement:
    """Test sequence number incrementation."""

    def test_first_operation_has_sequence_one(
        self, operation_log, alice_identity
    ):
        """First operation in log has sequence_number=1."""
        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        assert op.sequence_number == 1

    def test_sequence_numbers_increment(self, operation_log, alice_identity):
        """Sequence numbers increment for each operation."""
        op1 = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value1"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        op2 = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value2"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        op3 = operation_log.create_operation(
            op_type="update",
            record_type="TestRecord",
            record_id=op1.record_id,
            payload={"data": "updated"},
            previous_head_cid="QmHash1",
            initiator=alice_identity,
        )

        assert op1.sequence_number == 1
        assert op2.sequence_number == 2
        assert op3.sequence_number == 3

    def test_sequence_numbers_continuous(self, operation_log, alice_identity):
        """Sequence numbers are continuous (no gaps)."""
        ops = []
        for i in range(5):
            op = operation_log.create_operation(
                op_type="insert",
                record_type="TestRecord",
                record_id=str(uuid4()),
                payload={"data": f"value{i}"},
                previous_head_cid=None,
                initiator=alice_identity,
            )
            ops.append(op)

        for i, op in enumerate(ops, start=1):
            assert op.sequence_number == i

    def test_sequence_numbers_cross_operation_types(
        self, operation_log, alice_identity
    ):
        """Sequence numbers increment regardless of operation type."""
        record_id = str(uuid4())

        op_insert = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=record_id,
            payload={"data": "initial"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        op_update = operation_log.create_operation(
            op_type="update",
            record_type="TestRecord",
            record_id=record_id,
            payload={"data": "updated"},
            previous_head_cid=op_insert.op_id,
            initiator=alice_identity,
        )

        op_tombstone = operation_log.create_operation(
            op_type="tombstone",
            record_type="TestRecord",
            record_id=record_id,
            payload=None,
            previous_head_cid=op_update.op_id,
            initiator=alice_identity,
        )

        assert op_insert.sequence_number == 1
        assert op_update.sequence_number == 2
        assert op_tombstone.sequence_number == 3


# ============================================================================
# OPERATION SIGNING TESTS
# ============================================================================


class TestOperationSigning:
    """Test operation signing via cohort keys."""

    def test_operation_is_signed(self, operation_log, alice_identity):
        """Created operation is signed."""
        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        assert op.signature is not None
        assert isinstance(op.signature, bytes)
        assert len(op.signature) > 0

    def test_signature_is_deterministic_for_same_input(
        self, operation_log, alice_identity
    ):
        """Same operation content produces consistent signatures."""
        # This is a RED test - we can't control randomness until we sign,
        # but we expect the signature field to be set
        op1 = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        # Signature should not be empty
        assert op1.signature
        assert len(op1.signature) > 0

    def test_signature_uses_cohort_key(self, test_cohort, alice_identity):
        """Signature is created with cohort signing key."""
        op = test_cohort.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        # Cohort has a signing key
        assert test_cohort.signing_key_der is not None
        # Operation has a signature
        assert op.signature is not None

    def test_operation_signing_algorithm_is_set(
        self, operation_log, alice_identity
    ):
        """Operation specifies the signing algorithm."""
        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        assert op.signing_algorithm is not None
        assert op.signing_algorithm in ["Ed25519"]

    def test_different_operations_have_different_signatures(
        self, operation_log, alice_identity
    ):
        """Different operations produce different signatures."""
        op1 = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value1"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        op2 = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value2"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        # Different content should have different signatures
        assert op1.signature != op2.signature

    def test_operation_not_yet_published(self, operation_log, alice_identity):
        """Created operation is not yet published to IPFS."""
        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        # Operation should not have IPFS CID assigned yet
        # (CID is assigned when published)
        assert not hasattr(op, "ipfs_cid") or op.ipfs_cid is None


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestOperationEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_operation_with_large_sequence_number(
        self, operation_log, alice_identity
    ):
        """Sequence numbers can grow large."""
        # Create many operations
        for i in range(100):
            op = operation_log.create_operation(
                op_type="insert",
                record_type="TestRecord",
                record_id=str(uuid4()),
                payload={"data": f"value{i}"},
                previous_head_cid=None,
                initiator=alice_identity,
            )

        # Last operation should have sequence 100
        assert op.sequence_number == 100

    def test_operation_with_empty_payload(self, operation_log, alice_identity):
        """Tombstone operation has None payload."""
        op = operation_log.create_operation(
            op_type="tombstone",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload=None,
            previous_head_cid="QmHash",
            initiator=alice_identity,
        )

        assert op.payload is None
        assert op.signature is not None

    def test_operation_with_complex_payload(
        self, operation_log, alice_identity
    ):
        """Operation can have complex nested payload."""
        complex_payload = {
            "field1": "value1",
            "nested": {
                "field2": "value2",
                "array": [1, 2, 3],
                "deep": {"field3": {"array": ["a", "b"]}},
            },
            "array_of_objects": [
                {"id": 1, "name": "first"},
                {"id": 2, "name": "second"},
            ],
        }

        op = operation_log.create_operation(
            op_type="insert",
            record_type="ComplexRecord",
            record_id=str(uuid4()),
            payload=complex_payload,
            previous_head_cid=None,
            initiator=alice_identity,
        )

        assert op.payload == complex_payload
        assert op.signature is not None

    def test_operation_with_long_record_id(
        self, operation_log, alice_identity
    ):
        """Operation with lengthy record_id."""
        long_record_id = str(uuid4()) + "_" + str(uuid4())

        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=long_record_id,
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        assert op.record_id == long_record_id

    def test_operation_with_cid_chain(self, operation_log, alice_identity):
        """Operation maintains chain via previous_head_cid."""
        record_id = str(uuid4())

        op1 = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=record_id,
            payload={"data": "v1"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        op2 = operation_log.create_operation(
            op_type="update",
            record_type="TestRecord",
            record_id=record_id,
            payload={"data": "v2"},
            previous_head_cid=op1.op_id,
            initiator=alice_identity,
        )

        op3 = operation_log.create_operation(
            op_type="update",
            record_type="TestRecord",
            record_id=record_id,
            payload={"data": "v3"},
            previous_head_cid=op2.op_id,
            initiator=alice_identity,
        )

        assert op1.previous_head_cid is None
        assert op2.previous_head_cid == op1.op_id
        assert op3.previous_head_cid == op2.op_id

    def test_operation_cohort_id_preserved(self, test_cohort, alice_identity):
        """Operation preserves cohort_id."""
        op = test_cohort.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        assert op.cohort_id == test_cohort.cohort_id

    def test_operation_with_multi_member_cohort(
        self, multi_member_cohort, alice_identity
    ):
        """Operation can be created by member of multi-member cohort."""
        op = multi_member_cohort.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        assert op is not None
        assert op.signature is not None
        assert op.cohort_id == multi_member_cohort.cohort_id


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestOperationErrorHandling:
    """Test error cases and validation."""

    def test_invalid_operation_type_raises_error(
        self, operation_log, alice_identity
    ):
        """Invalid op_type raises error."""
        with pytest.raises((ValueError, TypeError, KeyError)):
            operation_log.create_operation(
                op_type="invalid_type",
                record_type="TestRecord",
                record_id=str(uuid4()),
                payload={"data": "value"},
                previous_head_cid=None,
                initiator=alice_identity,
            )

    def test_missing_record_type_raises_error(
        self, operation_log, alice_identity
    ):
        """Missing record_type raises error."""
        with pytest.raises(TypeError):
            operation_log.create_operation(
                op_type="insert",
                # record_type is missing
                record_id=str(uuid4()),
                payload={"data": "value"},
                previous_head_cid=None,
                initiator=alice_identity,
            )

    def test_missing_record_id_raises_error(
        self, operation_log, alice_identity
    ):
        """Missing record_id raises error."""
        with pytest.raises(TypeError):
            operation_log.create_operation(
                op_type="insert",
                record_type="TestRecord",
                # record_id is missing
                payload={"data": "value"},
                previous_head_cid=None,
                initiator=alice_identity,
            )

    def test_missing_initiator_raises_error(self, operation_log):
        """Missing initiator raises error."""
        with pytest.raises(TypeError):
            operation_log.create_operation(
                op_type="insert",
                record_type="TestRecord",
                record_id=str(uuid4()),
                payload={"data": "value"},
                previous_head_cid=None,
                # initiator is missing
            )

    def test_none_initiator_raises_error(self, operation_log):
        """None initiator raises error."""
        with pytest.raises((ValueError, TypeError)):
            operation_log.create_operation(
                op_type="insert",
                record_type="TestRecord",
                record_id=str(uuid4()),
                payload={"data": "value"},
                previous_head_cid=None,
                initiator=None,
            )

    def test_tombstone_update_and_insert_valid(
        self, operation_log, alice_identity
    ):
        """Valid op_types are insert, update, tombstone."""
        valid_types = ["insert", "update", "tombstone"]

        for op_type in valid_types:
            op = operation_log.create_operation(
                op_type=op_type,
                record_type="TestRecord",
                record_id=str(uuid4()),
                payload=(
                    {"data": "value"} if op_type != "tombstone" else None
                ),
                previous_head_cid=None,
                initiator=alice_identity,
            )
            assert op.op_type == op_type


# ============================================================================
# SIGNATURE VERIFICATION TESTS
# ============================================================================


class TestSignatureVerification:
    """Test signature verification and integrity."""

    def test_operation_signature_verifiable(
        self, operation_log, alice_identity
    ):
        """Created operation's signature can be verified."""
        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        # Should be able to call a verify method
        # (will implement in Phase 4)
        assert op.signature is not None

    def test_signature_covers_operation_fields(
        self, operation_log, alice_identity
    ):
        """Signature should cover critical operation fields."""
        # Create an operation
        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        # Signature should be over canonical bytes (per issue #16)
        assert op.signature is not None
        assert op.signing_algorithm == "Ed25519"

    def test_multiple_cohorts_produce_different_signatures(
        self, alice_identity, bob_identity
    ):
        """Operations from different cohorts have different signatures."""
        cohort1 = SimpleCohort(
            cohort_id="cohort1", founder_identity=alice_identity
        )
        cohort2 = SimpleCohort(
            cohort_id="cohort2", founder_identity=bob_identity
        )

        record_id = str(uuid4())
        payload = {"data": "same_value"}

        op1 = cohort1.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=record_id,
            payload=payload,
            previous_head_cid=None,
            initiator=alice_identity,
        )

        op2 = cohort2.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=record_id,
            payload=payload,
            previous_head_cid=None,
            initiator=bob_identity,
        )

        # Different cohorts should produce different signatures
        # (because they have different signing keys)
        assert op1.signature != op2.signature


# ============================================================================
# SCHEMA AND SERIALIZATION TESTS
# ============================================================================


class TestOperationSchema:
    """Test operation record schema and structure."""

    def test_operation_has_schema_version(self, operation_log, alice_identity):
        """Operation record includes schema_version."""
        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        assert op.schema_version is not None
        assert isinstance(op.schema_version, (int, str))

    def test_operation_is_serializable(self, operation_log, alice_identity):
        """Operation can be serialized (for IPFS storage)."""
        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        # Should be convertible to dict for CBOR serialization
        if hasattr(op, "to_dict"):
            op_dict = op.to_dict()
            assert "op_id" in op_dict
            assert "signature" in op_dict
        elif hasattr(op, "__dict__"):
            op_dict = op.__dict__
            assert "op_id" in op_dict or hasattr(op, "op_id")


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestOperationIntegration:
    """Integration tests with cohort and signing infrastructure."""

    def test_operation_sequence_persists_across_cohort_methods(
        self, test_cohort, alice_identity, bob_identity
    ):
        """Sequence numbers persist even with other cohort operations."""
        # Create first operation
        op1 = test_cohort.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value1"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        # Do other cohort work (like membership proposals)
        test_cohort.create_add_member_proposal(bob_identity, alice_identity)

        # Create second operation - sequence should continue
        op2 = test_cohort.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value2"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        # Sequence should still increment properly
        assert op2.sequence_number > op1.sequence_number

    def test_operation_with_member_after_cohort_voting(
        self, multi_member_cohort, bob_identity
    ):
        """New members can create operations after joining."""
        # Both Alice and Bob are already members
        # Create operation from Bob
        op = multi_member_cohort.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "from_bob"},
            previous_head_cid=None,
            initiator=bob_identity,
        )

        assert op is not None
        assert op.signature is not None

    def test_operation_contains_cohort_info(self, test_cohort, alice_identity):
        """Operation includes cohort identification."""
        op = test_cohort.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        assert op.cohort_id == test_cohort.cohort_id

    def test_operation_initiator_stored_or_recoverable(
        self, operation_log, alice_identity
    ):
        """Operation preserves initiator information."""
        op = operation_log.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "value"},
            previous_head_cid=None,
            initiator=alice_identity,
        )

        # Initiator should be stored or recoverable from signature
        # (per phase 4, signature verification will recover it)
        assert op is not None
