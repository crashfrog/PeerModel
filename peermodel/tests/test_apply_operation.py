#!/usr/bin/env python

"""Tests for IndexDB.apply_operation() implementation (Issue #20)."""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime

import peermodel
from peermodel.peermodel import DocumentObj
from peermodel.index import IndexDB
from peermodel.operations import OperationRecord


@pytest.fixture
def peer():
    """Create test App instance."""
    return peermodel.App("test_apply_operation")


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
    """Create a test model for operations."""
    @peer.model
    class TestDocument:
        name: str
        value: int
        description: str

    return DocumentObj.Meta._reg['TestDocument']


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
            'description': 'Test Description'
        }

    return OperationRecord(
        op_id=op_id,
        op_type=op_type,
        cohort_id='test-cohort',
        record_type='TestDocument',
        record_id=record_id,
        sequence_number=sequence_number,
        payload=payload if op_type != 'tombstone' else None,
        previous_head_cid=None,
        timestamp=datetime.utcnow().isoformat() + 'Z',
        schema_version='1.0.0',
        signature=b'test_signature',
        signing_algorithm='ed25519'
    )


@pytest.mark.issue_20
class TestApplyInsertOperation:
    """Test INSERT operation application."""

    def test_apply_insert_operation_creates_row(self, peer, index_db, test_model):
        """Test that apply_operation inserts a new row for insert op_type."""
        # Setup: ensure schema
        index_db.ensure_schema(test_model)

        # Create insert operation
        op = create_test_operation(
            op_type='insert',
            record_id='rec-1',
            op_id='op-1',
            payload={'name': 'Alice', 'value': 100, 'description': 'First user'}
        )

        # Apply operation
        index_db.apply_operation(test_model, op)

        # Verify row was inserted
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT _record_id, name, value, description FROM TestDocument "
            "WHERE _record_id = ?",
            ('rec-1',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 'rec-1'
        assert result[1] == 'Alice'
        assert result[2] == 100
        assert result[3] == 'First user'

    def test_apply_insert_operation_sets_system_columns(self, peer, index_db, test_model):
        """Test that system columns (_op_id, _sequence, etc) are set."""
        index_db.ensure_schema(test_model)

        op = create_test_operation(
            op_type='insert',
            record_id='rec-sys-1',
            op_id='op-sys-1',
            sequence_number=5
        )

        index_db.apply_operation(test_model, op)

        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT _op_id, _sequence, _timestamp, _tombstoned FROM TestDocument "
            "WHERE _record_id = ?",
            ('rec-sys-1',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 'op-sys-1'
        assert result[1] == 5
        assert result[2] is not None
        assert result[3] == 0  # _tombstoned should be 0 for insert

    def test_apply_insert_operation_replaces_existing_row(self, peer, index_db, test_model):
        """Test that INSERT OR REPLACE replaces existing row with same _record_id."""
        index_db.ensure_schema(test_model)

        # Insert first version
        op1 = create_test_operation(
            op_type='insert',
            record_id='rec-replace',
            op_id='op-1',
            payload={'name': 'Version 1', 'value': 10, 'description': 'First'}
        )
        index_db.apply_operation(test_model, op1)

        # Insert second version with same record_id (INSERT OR REPLACE)
        op2 = create_test_operation(
            op_type='insert',
            record_id='rec-replace',
            op_id='op-2',
            payload={'name': 'Version 2', 'value': 20, 'description': 'Second'}
        )
        index_db.apply_operation(test_model, op2)

        # Verify only one row exists with latest data
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*), name, value FROM TestDocument "
            "WHERE _record_id = ? GROUP BY _record_id",
            ('rec-replace',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 1  # Only one row
        assert result[1] == 'Version 2'
        assert result[2] == 20

    def test_apply_multiple_insert_operations(self, peer, index_db, test_model):
        """Test applying multiple insert operations creates multiple rows."""
        index_db.ensure_schema(test_model)

        # Insert three different records
        for i in range(1, 4):
            op = create_test_operation(
                op_type='insert',
                record_id=f'rec-{i}',
                op_id=f'op-{i}',
                payload={'name': f'User {i}', 'value': i * 10, 'description': f'User {i}'}
            )
            index_db.apply_operation(test_model, op)

        # Verify all three rows exist
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM TestDocument WHERE _tombstoned = 0")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 3


@pytest.mark.issue_20
class TestApplyUpdateOperation:
    """Test UPDATE operation application."""

    def test_apply_update_operation_modifies_existing_row(self, peer, index_db, test_model):
        """Test that apply_operation updates an existing row for update op_type."""
        index_db.ensure_schema(test_model)

        # First insert a row
        insert_op = create_test_operation(
            op_type='insert',
            record_id='rec-update',
            op_id='op-1',
            payload={'name': 'Original', 'value': 50, 'description': 'Original'}
        )
        index_db.apply_operation(test_model, insert_op)

        # Then update it
        update_op = create_test_operation(
            op_type='update',
            record_id='rec-update',
            op_id='op-2',
            sequence_number=2,
            payload={'name': 'Updated', 'value': 75, 'description': 'Updated'}
        )
        index_db.apply_operation(test_model, update_op)

        # Verify the row was updated
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, value, description FROM TestDocument "
            "WHERE _record_id = ?",
            ('rec-update',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 'Updated'
        assert result[1] == 75
        assert result[2] == 'Updated'

    def test_apply_update_operation_only_one_row_exists(self, peer, index_db, test_model):
        """Test that UPDATE doesn't create duplicates (only one row per record_id)."""
        index_db.ensure_schema(test_model)

        # Insert
        insert_op = create_test_operation(
            op_type='insert',
            record_id='rec-dup-check',
            op_id='op-1',
            payload={'name': 'V1', 'value': 1, 'description': 'V1'}
        )
        index_db.apply_operation(test_model, insert_op)

        # Update
        update_op = create_test_operation(
            op_type='update',
            record_id='rec-dup-check',
            op_id='op-2',
            sequence_number=2,
            payload={'name': 'V2', 'value': 2, 'description': 'V2'}
        )
        index_db.apply_operation(test_model, update_op)

        # Verify only one row exists
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM TestDocument WHERE _record_id = ?",
            ('rec-dup-check',)
        )
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1

    def test_apply_update_operation_updates_system_columns(self, peer, index_db, test_model):
        """Test that update operation updates _op_id and _sequence."""
        index_db.ensure_schema(test_model)

        # Insert
        insert_op = create_test_operation(
            op_type='insert',
            record_id='rec-sys-update',
            op_id='op-1',
            sequence_number=1
        )
        index_db.apply_operation(test_model, insert_op)

        # Update with different op_id and sequence
        update_op = create_test_operation(
            op_type='update',
            record_id='rec-sys-update',
            op_id='op-2-new',
            sequence_number=10,
            payload={'name': 'Updated Name', 'value': 999, 'description': 'Updated'}
        )
        index_db.apply_operation(test_model, update_op)

        # Verify system columns were updated
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT _op_id, _sequence FROM TestDocument WHERE _record_id = ?",
            ('rec-sys-update',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 'op-2-new'
        assert result[1] == 10

    def test_apply_update_operation_sets_tombstoned_to_zero(self, peer, index_db, test_model):
        """Test that update operation sets _tombstoned to 0."""
        index_db.ensure_schema(test_model)

        # Insert
        insert_op = create_test_operation(
            op_type='insert',
            record_id='rec-tombstone-zero',
            op_id='op-1',
            payload={'name': 'Test', 'value': 1, 'description': 'Test'}
        )
        index_db.apply_operation(test_model, insert_op)

        # Update
        update_op = create_test_operation(
            op_type='update',
            record_id='rec-tombstone-zero',
            op_id='op-2',
            sequence_number=2,
            payload={'name': 'Updated', 'value': 2, 'description': 'Updated'}
        )
        index_db.apply_operation(test_model, update_op)

        # Check _tombstoned
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT _tombstoned FROM TestDocument WHERE _record_id = ?",
            ('rec-tombstone-zero',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 0


@pytest.mark.issue_20
class TestApplyTombstoneOperation:
    """Test TOMBSTONE operation application."""

    def test_apply_tombstone_operation_sets_tombstoned_flag(self, peer, index_db, test_model):
        """Test that apply_operation sets _tombstoned=1 for tombstone op_type."""
        index_db.ensure_schema(test_model)

        # Insert a row
        insert_op = create_test_operation(
            op_type='insert',
            record_id='rec-tombstone',
            op_id='op-1',
            payload={'name': 'To Delete', 'value': 99, 'description': 'Will be deleted'}
        )
        index_db.apply_operation(test_model, insert_op)

        # Apply tombstone operation
        tombstone_op = create_test_operation(
            op_type='tombstone',
            record_id='rec-tombstone',
            op_id='op-2',
            sequence_number=2,
            payload=None  # Tombstone has no payload
        )
        index_db.apply_operation(test_model, tombstone_op)

        # Verify _tombstoned flag is set
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT _tombstoned, _op_id FROM TestDocument WHERE _record_id = ?",
            ('rec-tombstone',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 1  # _tombstoned should be 1
        assert result[1] == 'op-2'

    def test_apply_tombstone_operation_preserves_record_data(self, peer, index_db, test_model):
        """Test that tombstone operation preserves the original record data."""
        index_db.ensure_schema(test_model)

        # Insert
        insert_op = create_test_operation(
            op_type='insert',
            record_id='rec-preserve',
            op_id='op-1',
            payload={'name': 'Preserve Me', 'value': 123, 'description': 'Important data'}
        )
        index_db.apply_operation(test_model, insert_op)

        # Tombstone
        tombstone_op = create_test_operation(
            op_type='tombstone',
            record_id='rec-preserve',
            op_id='op-2',
            sequence_number=2,
            payload=None
        )
        index_db.apply_operation(test_model, tombstone_op)

        # Verify data is still there but marked as tombstoned
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, value, description, _tombstoned FROM TestDocument "
            "WHERE _record_id = ?",
            ('rec-preserve',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 'Preserve Me'
        assert result[1] == 123
        assert result[2] == 'Important data'
        assert result[3] == 1

    def test_apply_tombstone_operation_can_be_restored(self, peer, index_db, test_model):
        """Test that a tombstoned record can be restored with insert/update."""
        index_db.ensure_schema(test_model)

        # Insert
        insert_op = create_test_operation(
            op_type='insert',
            record_id='rec-restore',
            op_id='op-1',
            payload={'name': 'Original', 'value': 1, 'description': 'Original'}
        )
        index_db.apply_operation(test_model, insert_op)

        # Tombstone
        tombstone_op = create_test_operation(
            op_type='tombstone',
            record_id='rec-restore',
            op_id='op-2',
            sequence_number=2,
            payload=None
        )
        index_db.apply_operation(test_model, tombstone_op)

        # Restore with insert (INSERT OR REPLACE)
        restore_op = create_test_operation(
            op_type='insert',
            record_id='rec-restore',
            op_id='op-3',
            sequence_number=3,
            payload={'name': 'Restored', 'value': 999, 'description': 'Restored'}
        )
        index_db.apply_operation(test_model, restore_op)

        # Verify record is restored (not tombstoned)
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, _tombstoned FROM TestDocument WHERE _record_id = ?",
            ('rec-restore',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 'Restored'
        assert result[1] == 0  # No longer tombstoned

    def test_apply_tombstone_operation_updates_sequence(self, peer, index_db, test_model):
        """Test that tombstone operation updates _sequence and _op_id."""
        index_db.ensure_schema(test_model)

        # Insert
        insert_op = create_test_operation(
            op_type='insert',
            record_id='rec-tomb-seq',
            op_id='op-1',
            sequence_number=1
        )
        index_db.apply_operation(test_model, insert_op)

        # Tombstone with different sequence
        tombstone_op = create_test_operation(
            op_type='tombstone',
            record_id='rec-tomb-seq',
            op_id='op-tombstone-99',
            sequence_number=99,
            payload=None
        )
        index_db.apply_operation(test_model, tombstone_op)

        # Verify
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT _op_id, _sequence FROM TestDocument WHERE _record_id = ?",
            ('rec-tomb-seq',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 'op-tombstone-99'
        assert result[1] == 99


@pytest.mark.issue_20
class TestIdempotentReplay:
    """Test that duplicate op_id replays are no-ops."""

    def test_apply_operation_duplicate_op_id_is_noop_insert(self, peer, index_db, test_model):
        """Test that replaying an operation with same op_id is idempotent."""
        index_db.ensure_schema(test_model)

        # Apply operation
        op = create_test_operation(
            op_type='insert',
            record_id='rec-idempotent',
            op_id='op-idempotent-1',
            payload={'name': 'First', 'value': 1, 'description': 'First'}
        )
        index_db.apply_operation(test_model, op)

        # Get initial state
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, value, _op_id FROM TestDocument WHERE _record_id = ?",
            ('rec-idempotent',)
        )
        first_result = cursor.fetchone()
        conn.close()

        # Replay the same operation with same op_id
        index_db.apply_operation(test_model, op)

        # Get state after replay
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, value, _op_id FROM TestDocument WHERE _record_id = ?",
            ('rec-idempotent',)
        )
        second_result = cursor.fetchone()
        conn.close()

        # State should be identical (no-op)
        assert first_result == second_result

    def test_apply_operation_duplicate_op_id_with_different_payload_is_noop(
        self, peer, index_db, test_model
    ):
        """Test that op_id identity matters more than payload (idempotent)."""
        index_db.ensure_schema(test_model)

        # Apply first operation
        op1 = create_test_operation(
            op_type='insert',
            record_id='rec-dup-payload',
            op_id='op-dup-check',
            payload={'name': 'Original', 'value': 1, 'description': 'Original'}
        )
        index_db.apply_operation(test_model, op1)

        # Try to replay with same op_id but different payload
        op2 = create_test_operation(
            op_type='insert',
            record_id='rec-dup-payload',
            op_id='op-dup-check',  # Same op_id
            payload={'name': 'Modified', 'value': 999, 'description': 'Modified'}
        )
        index_db.apply_operation(test_model, op2)

        # Verify first payload is preserved (no-op)
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, value FROM TestDocument WHERE _record_id = ?",
            ('rec-dup-payload',)
        )
        result = cursor.fetchone()
        conn.close()

        # Should have original values (no-op on replay)
        assert result[0] == 'Original'
        assert result[1] == 1

    def test_apply_operation_duplicate_op_id_with_update_is_noop(
        self, peer, index_db, test_model
    ):
        """Test that duplicate op_id on update is idempotent."""
        index_db.ensure_schema(test_model)

        # Insert
        insert_op = create_test_operation(
            op_type='insert',
            record_id='rec-dup-update',
            op_id='op-1',
            payload={'name': 'V1', 'value': 1, 'description': 'V1'}
        )
        index_db.apply_operation(test_model, insert_op)

        # First update
        update_op = create_test_operation(
            op_type='update',
            record_id='rec-dup-update',
            op_id='op-update-dup',
            sequence_number=2,
            payload={'name': 'V2', 'value': 2, 'description': 'V2'}
        )
        index_db.apply_operation(test_model, update_op)

        # Get state after first update
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, value FROM TestDocument WHERE _record_id = ?",
            ('rec-dup-update',)
        )
        first_result = cursor.fetchone()
        conn.close()

        # Replay the same update operation (same op_id)
        index_db.apply_operation(test_model, update_op)

        # Get state after replay
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, value FROM TestDocument WHERE _record_id = ?",
            ('rec-dup-update',)
        )
        second_result = cursor.fetchone()
        conn.close()

        # State should be identical
        assert first_result == second_result

    def test_apply_operation_duplicate_op_id_with_tombstone_is_noop(
        self, peer, index_db, test_model
    ):
        """Test that duplicate op_id on tombstone is idempotent."""
        index_db.ensure_schema(test_model)

        # Insert
        insert_op = create_test_operation(
            op_type='insert',
            record_id='rec-dup-tombstone',
            op_id='op-1',
            payload={'name': 'Test', 'value': 1, 'description': 'Test'}
        )
        index_db.apply_operation(test_model, insert_op)

        # First tombstone
        tombstone_op = create_test_operation(
            op_type='tombstone',
            record_id='rec-dup-tombstone',
            op_id='op-tombstone-dup',
            sequence_number=2,
            payload=None
        )
        index_db.apply_operation(test_model, tombstone_op)

        # Get state
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT _tombstoned, _op_id, _sequence FROM TestDocument "
            "WHERE _record_id = ?",
            ('rec-dup-tombstone',)
        )
        first_result = cursor.fetchone()
        conn.close()

        # Replay the same tombstone (same op_id)
        index_db.apply_operation(test_model, tombstone_op)

        # Get state after replay
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT _tombstoned, _op_id, _sequence FROM TestDocument "
            "WHERE _record_id = ?",
            ('rec-dup-tombstone',)
        )
        second_result = cursor.fetchone()
        conn.close()

        # State should be identical
        assert first_result == second_result


@pytest.mark.issue_20
class TestOperationSequenceHandling:
    """Test operation sequencing and ordering."""

    def test_apply_operations_in_sequence_order(self, peer, index_db, test_model):
        """Test applying operations maintains sequence integrity."""
        index_db.ensure_schema(test_model)

        # Apply operations in sequence
        for seq in range(1, 6):
            op = create_test_operation(
                op_type='insert' if seq == 1 else 'update',
                record_id='rec-seq',
                op_id=f'op-{seq}',
                sequence_number=seq,
                payload={'name': f'Update {seq}', 'value': seq * 10, 'description': f'Seq {seq}'}
            )
            index_db.apply_operation(test_model, op)

        # Verify final state has highest sequence
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT _sequence, _op_id, value FROM TestDocument WHERE _record_id = ?",
            ('rec-seq',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 5  # Highest sequence
        assert result[1] == 'op-5'
        assert result[2] == 50  # value = 5 * 10

    def test_apply_out_of_order_operations(self, peer, index_db, test_model):
        """Test applying operations out of sequence order (should still update)."""
        index_db.ensure_schema(test_model)

        # Apply operation 3
        op3 = create_test_operation(
            op_type='insert',
            record_id='rec-out-of-order',
            op_id='op-3',
            sequence_number=3,
            payload={'name': 'Third', 'value': 30, 'description': 'Third'}
        )
        index_db.apply_operation(test_model, op3)

        # Apply operation 1
        op1 = create_test_operation(
            op_type='update',
            record_id='rec-out-of-order',
            op_id='op-1',
            sequence_number=1,
            payload={'name': 'First', 'value': 10, 'description': 'First'}
        )
        index_db.apply_operation(test_model, op1)

        # Verify the record exists
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM TestDocument WHERE _record_id = ?",
            ('rec-out-of-order',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None

    def test_apply_operation_sets_head_cid(self, peer, index_db, test_model):
        """Test that apply_operation can set _head_cid from operation."""
        index_db.ensure_schema(test_model)

        # Create operation with previous_head_cid
        op = OperationRecord(
            op_id='op-with-cid',
            op_type='insert',
            cohort_id='test-cohort',
            record_type='TestDocument',
            record_id='rec-cid',
            sequence_number=1,
            payload={'name': 'CID Test', 'value': 1, 'description': 'CID'},
            previous_head_cid='bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi',
            timestamp=datetime.utcnow().isoformat() + 'Z',
            schema_version='1.0.0',
            signature=b'test_sig',
            signing_algorithm='ed25519'
        )

        index_db.apply_operation(test_model, op)

        # Verify _head_cid was set
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT _head_cid FROM TestDocument WHERE _record_id = ?",
            ('rec-cid',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 'bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi'


@pytest.mark.issue_20
class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_apply_operation_with_null_values_in_payload(self, peer, index_db, test_model):
        """Test applying operation with None/null values in payload."""
        index_db.ensure_schema(test_model)

        op = create_test_operation(
            op_type='insert',
            record_id='rec-null',
            op_id='op-null',
            payload={'name': 'Test', 'value': None, 'description': None}
        )

        index_db.apply_operation(test_model, op)

        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value, description FROM TestDocument WHERE _record_id = ?",
            ('rec-null',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] is None
        assert result[1] is None

    def test_apply_operation_with_empty_string_values(self, peer, index_db, test_model):
        """Test applying operation with empty string values."""
        index_db.ensure_schema(test_model)

        op = create_test_operation(
            op_type='insert',
            record_id='rec-empty',
            op_id='op-empty',
            payload={'name': '', 'value': 0, 'description': ''}
        )

        index_db.apply_operation(test_model, op)

        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, value, description FROM TestDocument WHERE _record_id = ?",
            ('rec-empty',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == ''
        assert result[1] == 0
        assert result[2] == ''

    def test_apply_operation_with_special_characters_in_payload(
        self, peer, index_db, test_model
    ):
        """Test applying operation with special characters in string fields."""
        index_db.ensure_schema(test_model)

        special_text = "Test with 'quotes' and \"double quotes\" and \\ backslash"
        op = create_test_operation(
            op_type='insert',
            record_id='rec-special',
            op_id='op-special',
            payload={'name': special_text, 'value': 1, 'description': 'Special'}
        )

        index_db.apply_operation(test_model, op)

        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM TestDocument WHERE _record_id = ?",
            ('rec-special',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == special_text

    def test_apply_operation_with_large_values(self, peer, index_db, test_model):
        """Test applying operation with large integer values."""
        index_db.ensure_schema(test_model)

        large_value = 9223372036854775807  # Max int64

        op = create_test_operation(
            op_type='insert',
            record_id='rec-large',
            op_id='op-large',
            payload={'name': 'Large', 'value': large_value, 'description': 'Large value'}
        )

        index_db.apply_operation(test_model, op)

        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM TestDocument WHERE _record_id = ?",
            ('rec-large',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == large_value

    def test_apply_operation_with_unicode_characters(self, peer, index_db, test_model):
        """Test applying operation with Unicode characters."""
        index_db.ensure_schema(test_model)

        unicode_text = "Unicode: 你好世界 🌍 Ελληνικά"

        op = create_test_operation(
            op_type='insert',
            record_id='rec-unicode',
            op_id='op-unicode',
            payload={'name': unicode_text, 'value': 1, 'description': 'Unicode'}
        )

        index_db.apply_operation(test_model, op)

        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM TestDocument WHERE _record_id = ?",
            ('rec-unicode',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == unicode_text

    def test_apply_operation_multiple_records_in_sequence(self, peer, index_db, test_model):
        """Test applying operations to multiple different records in sequence."""
        index_db.ensure_schema(test_model)

        # Create and apply operations for multiple records
        record_ids = ['rec-multi-1', 'rec-multi-2', 'rec-multi-3']

        for i, rec_id in enumerate(record_ids, 1):
            op = create_test_operation(
                op_type='insert',
                record_id=rec_id,
                op_id=f'op-multi-{i}',
                payload={'name': f'Record {i}', 'value': i * 100, 'description': f'Record {i}'}
            )
            index_db.apply_operation(test_model, op)

        # Verify all three records exist
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM TestDocument WHERE _tombstoned = 0")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 3
