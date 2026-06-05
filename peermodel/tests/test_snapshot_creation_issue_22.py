#!/usr/bin/env python

"""Acceptance tests for Snapshot infrastructure (Issue #22)."""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime

import peermodel
from peermodel.peermodel import DocumentObj
from peermodel.index import IndexDB
from peermodel.operations import OperationRecord
from peermodel.primitives import generate_software_keypair


@pytest.fixture
def peer():
    """Create test App instance."""
    return peermodel.App("test_snapshot_creation")


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def index_db(temp_db):
    """Create an IndexDB instance with a temporary database."""
    return IndexDB(temp_db)


@pytest.fixture
def test_model(peer):
    """Create a test model for snapshots."""
    @peer.model
    class TestRecord:
        name: str
        value: int
        description: str

    return DocumentObj.Meta._reg['TestRecord']


@pytest.fixture
def cohort_keypair():
    """Generate a test cohort keypair for signing."""
    kp = generate_software_keypair("ed25519")
    signing_private_der, signing_public_der = kp[0], kp[1]
    return {
        "private": signing_private_der,
        "public": signing_public_der,
        "algorithm": "ed25519"
    }


def create_test_operation(
    op_type='insert',
    record_id='test-record-1',
    op_id='op-1',
    payload=None,
    sequence_number=1
):
    """Helper to create test OperationRecords."""
    if payload is None:
        payload = {
            'name': 'Test Name',
            'value': 42,
            'description': 'Test Description',
        }

    return OperationRecord(
        op_id=op_id,
        op_type=op_type,
        cohort_id='test-cohort',
        record_type='TestRecord',
        record_id=record_id,
        sequence_number=sequence_number,
        payload=payload if op_type != 'tombstone' else None,
        previous_head_cid=None,
        timestamp=datetime.utcnow().isoformat() + 'Z',
        schema_version='1.0.0',
        signature=b'test_signature',
        signing_algorithm='ed25519',
    )


def insert_live_records(index_db, test_model):
    """Insert live (non-tombstoned) records into the database for testing."""
    index_db.ensure_schema(test_model)

    test_records = [
        ('rec-1', 'op-1', 1, 'Alice', 100, 'First user'),
        ('rec-2', 'op-2', 2, 'Bob', 200, 'Second user'),
        ('rec-3', 'op-3', 3, 'Charlie', 300, 'Third user'),
    ]

    conn = sqlite3.connect(index_db.db_path)
    cursor = conn.cursor()

    for rec_id, op_id, seq, name, value, desc in test_records:
        sql = """
            INSERT INTO TestRecord  # noqa: E501
            (_record_id, _op_id, _sequence, _timestamp, _head_cid,
             _tombstoned, _schema_version,
             name, value, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        cursor.execute(
            sql,
            (rec_id, op_id, seq, 1000000000, f'cid-{seq}', 0, 1,
             name, value, desc)
        )

    conn.commit()
    conn.close()


@pytest.mark.issue_22
class TestSnapshotDataclass:
    """Test Snapshot dataclass definition and structure."""

    def test_snapshot_dataclass_exists(self, peer, index_db, test_model, cohort_keypair):  # noqa: E501
        """Test that Snapshot dataclass is defined."""
        from peermodel.snapshots import Snapshot

        # Snapshot should be importable
        assert Snapshot is not None

    def test_snapshot_has_required_fields(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that Snapshot has all required fields."""
        from peermodel.snapshots import Snapshot
        from dataclasses import fields

        field_names = {f.name for f in fields(Snapshot)}

        required_fields = {
            'cohort_id', 'snapshot_id', 'record_type', 'log_head_cid',
            'sequence_number', 'records', 'created_at', 'signature',
            'signing_algorithm'
        }

        missing = required_fields - field_names
        assert required_fields.issubset(field_names), \
            f"Missing fields: {missing}"

    def test_snapshot_field_types(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that Snapshot fields have correct types."""
        from peermodel.snapshots import Snapshot
        from dataclasses import fields

        field_types = {f.name: f.type for f in fields(Snapshot)}

        # Verify key field types
        assert field_types.get('cohort_id') == str
        assert field_types.get('snapshot_id') == str
        assert field_types.get('record_type') == str
        assert field_types.get('sequence_number') == int
        assert field_types.get('signature') == bytes
        assert field_types.get('signing_algorithm') == str

    def test_snapshot_records_field_is_list(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that Snapshot.records is a list."""
        from peermodel.snapshots import Snapshot
        from dataclasses import fields
        from typing import get_origin

        records_field = next(
            f for f in fields(Snapshot) if f.name == 'records'
        )
        field_type = records_field.type

        # Should be a list type (List[...])
        origin = get_origin(field_type)
        assert origin is list, \
            f"records field should be list, got {field_type}"


@pytest.mark.issue_22
class TestSnapshotCreation:
    """Test snapshot creation from live records."""

    def test_snapshot_manager_exists(self, peer, index_db, test_model, cohort_keypair):  # noqa: E501
        """Test that SnapshotManager class exists."""
        from peermodel.snapshots import SnapshotManager

        assert SnapshotManager is not None

    def test_snapshot_manager_create_snapshot_method_exists(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that SnapshotManager has create_snapshot method."""
        from peermodel.snapshots import SnapshotManager

        manager = SnapshotManager()
        assert hasattr(manager, 'create_snapshot')
        assert callable(manager.create_snapshot)

    def test_create_snapshot_reads_live_records(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that create_snapshot reads all live (non-tombstoned) records."""  # noqa: E501
        from peermodel.snapshots import SnapshotManager

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        # Snapshot should have records list
        assert snapshot.records is not None
        assert isinstance(snapshot.records, list)
        # Should have 3 live records
        assert len(snapshot.records) == 3

    def test_create_snapshot_excludes_tombstoned_records(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that create_snapshot excludes tombstoned records."""
        from peermodel.snapshots import SnapshotManager

        index_db.ensure_schema(test_model)

        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()

        # Insert 3 live records
        sql = """
            INSERT INTO TestRecord  # noqa: E501
            (_record_id, _op_id, _sequence, _timestamp, _head_cid,
             _tombstoned, _schema_version,
             name, value, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        for i in range(1, 4):
            cursor.execute(
                sql,
                (f'rec-{i}', f'op-{i}', i, 1000000000, f'cid-{i}', 0, 1,
                 f'User {i}', i * 100, f'User {i}')
            )

        # Insert 1 tombstoned record
        cursor.execute(
            sql,
            ('rec-tombstoned', 'op-tomb', 4, 1000000000, 'cid-tomb', 1, 1,
             'Deleted User', 999, 'Deleted')
        )

        conn.commit()
        conn.close()

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=4,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        # Should have exactly 3 records (tombstoned excluded)
        assert len(snapshot.records) == 3

    def test_create_snapshot_includes_all_record_fields(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that snapshot includes all fields from each record."""
        from peermodel.snapshots import SnapshotManager

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        # Each record in snapshot should be a dict with expected fields
        assert len(snapshot.records) > 0
        for record in snapshot.records:
            assert isinstance(record, dict)
            assert '_record_id' in record
            assert '_sequence' in record
            assert 'name' in record
            assert 'value' in record
            assert 'description' in record  # noqa: E501


@pytest.mark.issue_22
class TestSnapshotStructure:
    """Test snapshot structure and content."""

    def test_snapshot_has_correct_cohort_id(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that snapshot stores correct cohort_id."""
        from peermodel.snapshots import SnapshotManager

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort-xyz',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        assert snapshot.cohort_id == 'test-cohort-xyz'  # noqa: E501

    def test_snapshot_has_correct_record_type(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that snapshot stores correct record_type."""
        from peermodel.snapshots import SnapshotManager

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        assert snapshot.record_type == 'TestRecord'

    def test_snapshot_has_correct_log_head_cid(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that snapshot stores correct log_head_cid."""
        from peermodel.snapshots import SnapshotManager

        insert_live_records(index_db, test_model)

        head_cid = 'bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi'  # noqa: E501

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid=head_cid,
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        assert snapshot.log_head_cid == head_cid

    def test_snapshot_has_correct_sequence_number(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that snapshot stores correct sequence_number."""
        from peermodel.snapshots import SnapshotManager

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=42,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        assert snapshot.sequence_number == 42

    def test_snapshot_has_unique_snapshot_id(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that each snapshot has a unique snapshot_id."""
        from peermodel.snapshots import SnapshotManager

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot1 = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        snapshot2 = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        assert snapshot1.snapshot_id != snapshot2.snapshot_id
        assert snapshot1.snapshot_id is not None
        assert snapshot2.snapshot_id is not None

    def test_snapshot_has_created_at_timestamp(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that snapshot has created_at timestamp."""
        from peermodel.snapshots import SnapshotManager

        insert_live_records(index_db, test_model)

        before = datetime.utcnow().isoformat()

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        after = datetime.utcnow().isoformat()

        assert snapshot.created_at is not None
        assert isinstance(snapshot.created_at, str)
        # Verify it's within the time window
        assert before <= snapshot.created_at <= after


@pytest.mark.issue_22
class TestSnapshotSigning:
    """Test snapshot signing with cohort key."""

    def test_snapshot_has_signature(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that snapshot has a signature."""
        from peermodel.snapshots import SnapshotManager

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        assert snapshot.signature is not None
        assert isinstance(snapshot.signature, bytes)
        assert len(snapshot.signature) > 0

    def test_snapshot_signature_is_not_empty(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that snapshot signature is not empty."""
        from peermodel.snapshots import SnapshotManager

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        # Ed25519 signatures are 64 bytes
        assert len(snapshot.signature) == 64

    def test_snapshot_signing_algorithm_stored(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that signing_algorithm is stored in snapshot."""
        from peermodel.snapshots import SnapshotManager

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        assert snapshot.signing_algorithm == 'ed25519'

    def test_snapshot_signature_differs_for_different_records(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that different snapshots have different signatures."""
        from peermodel.snapshots import SnapshotManager

        index_db.ensure_schema(test_model)

        # Create first snapshot with one record
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO TestRecord  # noqa: E501
            (_record_id, _op_id, _sequence, _timestamp, _head_cid, _tombstoned, _schema_version,  # noqa: E501
             name, value, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('rec-1', 'op-1', 1, 1000000000, 'cid-1', 0, 1, 'Alice', 100, 'User 1')  # noqa: E501
        )
        conn.commit()
        conn.close()

        manager = SnapshotManager()
        snapshot1 = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head-1',
            sequence_number=1,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        # Add another record
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO TestRecord  # noqa: E501
            (_record_id, _op_id, _sequence, _timestamp, _head_cid, _tombstoned, _schema_version,  # noqa: E501
             name, value, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ('rec-2', 'op-2', 2, 1000000000, 'cid-2', 0, 1, 'Bob', 200, 'User 2')  # noqa: E501
        )
        conn.commit()
        conn.close()

        snapshot2 = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head-2',
            sequence_number=2,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        # Signatures should be different (different content)
        assert snapshot1.signature != snapshot2.signature

    def test_snapshot_signature_verification_possible(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that snapshot signature can be verified with public key."""
        from peermodel.snapshots import SnapshotManager, canonical_snapshot_bytes  # noqa: E501
#         from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        # Get canonical bytes for verification
        snapshot_bytes = canonical_snapshot_bytes(snapshot)

        # Load public key
        public_key = serialization.load_der_public_key(cohort_keypair['public'])  # noqa: E501

        # Verify signature (should not raise)
        public_key.verify(snapshot.signature, snapshot_bytes)

    def test_snapshot_signature_fails_with_wrong_public_key(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that snapshot verification fails with wrong public key."""
        from peermodel.snapshots import SnapshotManager, canonical_snapshot_bytes  # noqa: E501
#         from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        from cryptography.exceptions import InvalidSignature

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        # Generate a different keypair
        _, wrong_public_der, _, _ = generate_software_keypair("ed25519")
        wrong_public_key = serialization.load_der_public_key(wrong_public_der)

        # Get canonical bytes
        snapshot_bytes = canonical_snapshot_bytes(snapshot)

        # Verification should fail
        with pytest.raises(InvalidSignature):
            wrong_public_key.verify(snapshot.signature, snapshot_bytes)


@pytest.mark.issue_22
class TestSnapshotCanonicalEncoding:
    """Test snapshot canonical encoding for signing."""

    def test_canonical_snapshot_bytes_function_exists(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that canonical_snapshot_bytes function exists."""
        from peermodel.snapshots import canonical_snapshot_bytes

        assert callable(canonical_snapshot_bytes)

    def test_canonical_snapshot_bytes_deterministic(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that canonical_snapshot_bytes produces deterministic output."""
        from peermodel.snapshots import SnapshotManager, canonical_snapshot_bytes  # noqa: E501

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        bytes1 = canonical_snapshot_bytes(snapshot)
        bytes2 = canonical_snapshot_bytes(snapshot)

        assert bytes1 == bytes2

    def test_canonical_snapshot_bytes_returns_bytes(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that canonical_snapshot_bytes returns bytes."""
        from peermodel.snapshots import SnapshotManager, canonical_snapshot_bytes  # noqa: E501

        insert_live_records(index_db, test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        snapshot_bytes = canonical_snapshot_bytes(snapshot)

        assert isinstance(snapshot_bytes, bytes)
        assert len(snapshot_bytes) > 0


@pytest.mark.issue_22
class TestSnapshotEmptyRecords:
    """Test snapshot creation with empty record sets."""

    def test_create_snapshot_with_empty_database(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test creating snapshot from empty database."""
        from peermodel.snapshots import SnapshotManager

        index_db.ensure_schema(test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=0,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        assert snapshot is not None
        assert snapshot.records == []
        assert len(snapshot.records) == 0

    def test_empty_snapshot_is_still_signed(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test that empty snapshot is still properly signed."""
        from peermodel.snapshots import SnapshotManager

        index_db.ensure_schema(test_model)

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=0,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        assert snapshot.signature is not None
        assert len(snapshot.signature) == 64  # Ed25519 signature


@pytest.mark.issue_22
class TestSnapshotWithTombstones:
    """Test snapshot behavior with tombstoned records."""

    def test_snapshot_with_all_tombstoned_records(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test snapshot when all records are tombstoned."""
        from peermodel.snapshots import SnapshotManager

        index_db.ensure_schema(test_model)

        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()

        # Insert only tombstoned records
        for i in range(1, 4):
            cursor.execute(
                """
                INSERT INTO TestRecord  # noqa: E501
                (_record_id, _op_id, _sequence, _timestamp, _head_cid, _tombstoned, _schema_version,  # noqa: E501
                 name, value, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (f'rec-{i}', f'op-{i}', i, 1000000000, f'cid-{i}', 1, 1,
                 f'Deleted {i}', i * 100, f'Deleted record {i}')
            )

        conn.commit()
        conn.close()

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=3,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        # Should have empty records list
        assert snapshot.records == []

    def test_snapshot_mixed_live_and_tombstoned_records(
        self, peer, index_db, test_model, cohort_keypair
    ):
        """Test snapshot with mix of live and tombstoned records."""
        from peermodel.snapshots import SnapshotManager

        index_db.ensure_schema(test_model)

        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()

        # Insert 2 live records
        for i in range(1, 3):
            cursor.execute(
                """
                INSERT INTO TestRecord  # noqa: E501
                (_record_id, _op_id, _sequence, _timestamp, _head_cid, _tombstoned, _schema_version,  # noqa: E501
                 name, value, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (f'rec-live-{i}', f'op-{i}', i, 1000000000, f'cid-{i}', 0, 1,
                 f'Live {i}', i * 100, f'Live record {i}')
            )

        # Insert 2 tombstoned records
        for i in range(3, 5):
            cursor.execute(
                """
                INSERT INTO TestRecord  # noqa: E501
                (_record_id, _op_id, _sequence, _timestamp, _head_cid, _tombstoned, _schema_version,  # noqa: E501
                 name, value, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (f'rec-tomb-{i}', f'op-{i}', i, 1000000000, f'cid-{i}', 1, 1,
                 f'Deleted {i}', i * 100, f'Deleted record {i}')
            )

        conn.commit()
        conn.close()

        manager = SnapshotManager()
        snapshot = manager.create_snapshot(
            db=index_db,
            model_class=test_model,
            cohort_id='test-cohort',
            record_type='TestRecord',
            log_head_cid='cid-head',
            sequence_number=4,
            signing_private_key=cohort_keypair['private'],
            signing_algorithm='ed25519'
        )

        # Should have exactly 2 records (live only)
        assert len(snapshot.records) == 2
        record_ids = {r['_record_id'] for r in snapshot.records}
        assert record_ids == {'rec-live-1', 'rec-live-2'}
