#!/usr/bin/env python

"""Tests for NodeState dataclass and database operations (issue #24)."""

import pytest
import sqlite3
import tempfile
from pathlib import Path

# These imports will fail until the feature is implemented (RED tests)
try:
    from peermodel.state import NodeState, get_node_state, set_node_state
except ImportError:
    pytest.skip("NodeState not yet implemented", allow_module_level=True)


@pytest.fixture
def temp_db_path():
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def test_db_connection(temp_db_path):
    """Create and return a test database connection."""
    conn = sqlite3.connect(temp_db_path)
    yield conn
    conn.close()


class TestNodeStateDataclass:
    """Test NodeState dataclass definition and structure."""

    def test_nodestate_exists(self):
        """NodeState dataclass should be defined."""
        assert NodeState is not None

    def test_nodestate_has_cohort_id(self):
        """NodeState should have cohort_id field."""
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid=None,
            last_synced_sequence=0,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=None,
        )
        assert hasattr(state, "cohort_id")
        assert state.cohort_id == "test_cohort"

    def test_nodestate_has_record_type(self):
        """NodeState should have record_type field."""
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid=None,
            last_synced_sequence=0,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=None,
        )
        assert hasattr(state, "record_type")
        assert state.record_type == "TestRecord"

    def test_nodestate_has_last_synced_head_cid(self):
        """NodeState should have last_synced_head_cid field."""
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="Qm1234567890abcdef",
            last_synced_sequence=42,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="current",
            last_sync_at=None,
        )
        assert hasattr(state, "last_synced_head_cid")
        assert state.last_synced_head_cid == "Qm1234567890abcdef"

    def test_nodestate_has_last_synced_sequence(self):
        """NodeState should have last_synced_sequence field."""
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="Qm1234567890abcdef",
            last_synced_sequence=42,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="current",
            last_sync_at=None,
        )
        assert hasattr(state, "last_synced_sequence")
        assert state.last_synced_sequence == 42

    def test_nodestate_has_snapshot_cid(self):
        """NodeState should have snapshot_cid field."""
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid=None,
            last_synced_sequence=0,
            snapshot_cid="QmSnapshot123",
            snapshot_sequence=10,
            index_status="cold",
            last_sync_at=None,
        )
        assert hasattr(state, "snapshot_cid")
        assert state.snapshot_cid == "QmSnapshot123"

    def test_nodestate_has_snapshot_sequence(self):
        """NodeState should have snapshot_sequence field."""
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid=None,
            last_synced_sequence=0,
            snapshot_cid="QmSnapshot123",
            snapshot_sequence=10,
            index_status="cold",
            last_sync_at=None,
        )
        assert hasattr(state, "snapshot_sequence")
        assert state.snapshot_sequence == 10

    def test_nodestate_has_index_status(self):
        """NodeState should have index_status field."""
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid=None,
            last_synced_sequence=0,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="building",
            last_sync_at=None,
        )
        assert hasattr(state, "index_status")
        assert state.index_status == "building"

    def test_nodestate_has_last_sync_at(self):
        """NodeState should have last_sync_at field."""
        timestamp = "2026-05-19T12:00:00Z"
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid=None,
            last_synced_sequence=0,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=timestamp,
        )
        assert hasattr(state, "last_sync_at")
        assert state.last_sync_at == timestamp

    def test_nodestate_allows_none_values(self):
        """NodeState should allow None for optional CID and timestamp fields."""
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid=None,
            last_synced_sequence=0,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=None,
        )
        assert state.last_synced_head_cid is None
        assert state.snapshot_cid is None
        assert state.last_sync_at is None

    def test_nodestate_index_status_values(self):
        """NodeState index_status should support all specified states."""
        valid_statuses = ["cold", "building", "current", "stale"]
        for status in valid_statuses:
            state = NodeState(
                cohort_id="test_cohort",
                record_type="TestRecord",
                last_synced_head_cid=None,
                last_synced_sequence=0,
                snapshot_cid=None,
                snapshot_sequence=0,
                index_status=status,
                last_sync_at=None,
            )
            assert state.index_status == status


class TestGetNodeState:
    """Test get_node_state() database retrieval."""

    def test_get_node_state_exists(self):
        """get_node_state function should be defined."""
        assert callable(get_node_state)

    def test_get_node_state_returns_none_when_not_exists(self, test_db_connection):
        """get_node_state should return None when state doesn't exist."""
        result = get_node_state(
            test_db_connection,
            cohort_id="nonexistent_cohort",
            record_type="NonexistentRecord",
        )
        assert result is None

    def test_get_node_state_retrieves_saved_state(self, test_db_connection):
        """get_node_state should retrieve a previously saved state."""
        # First, save a state
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="Qm1234567890abcdef",
            last_synced_sequence=42,
            snapshot_cid="QmSnapshot123",
            snapshot_sequence=10,
            index_status="current",
            last_sync_at="2026-05-19T12:00:00Z",
        )
        set_node_state(test_db_connection, state)

        # Now retrieve it
        retrieved = get_node_state(
            test_db_connection, cohort_id="test_cohort", record_type="TestRecord"
        )

        assert retrieved is not None
        assert isinstance(retrieved, NodeState)
        assert retrieved.cohort_id == "test_cohort"
        assert retrieved.record_type == "TestRecord"
        assert retrieved.last_synced_head_cid == "Qm1234567890abcdef"
        assert retrieved.last_synced_sequence == 42
        assert retrieved.snapshot_cid == "QmSnapshot123"
        assert retrieved.snapshot_sequence == 10
        assert retrieved.index_status == "current"
        assert retrieved.last_sync_at == "2026-05-19T12:00:00Z"

    def test_get_node_state_with_none_values(self, test_db_connection):
        """get_node_state should correctly retrieve states with None values."""
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid=None,
            last_synced_sequence=0,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=None,
        )
        set_node_state(test_db_connection, state)

        retrieved = get_node_state(
            test_db_connection, cohort_id="test_cohort", record_type="TestRecord"
        )

        assert retrieved is not None
        assert retrieved.last_synced_head_cid is None
        assert retrieved.snapshot_cid is None
        assert retrieved.last_sync_at is None

    def test_get_node_state_isolates_by_cohort_id(self, test_db_connection):
        """get_node_state should only retrieve states for the specified cohort."""
        state1 = NodeState(
            cohort_id="cohort_1",
            record_type="TestRecord",
            last_synced_head_cid="Qm111",
            last_synced_sequence=1,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=None,
        )
        state2 = NodeState(
            cohort_id="cohort_2",
            record_type="TestRecord",
            last_synced_head_cid="Qm222",
            last_synced_sequence=2,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=None,
        )
        set_node_state(test_db_connection, state1)
        set_node_state(test_db_connection, state2)

        retrieved1 = get_node_state(test_db_connection, "cohort_1", "TestRecord")
        retrieved2 = get_node_state(test_db_connection, "cohort_2", "TestRecord")

        assert retrieved1.cohort_id == "cohort_1"
        assert retrieved1.last_synced_head_cid == "Qm111"
        assert retrieved2.cohort_id == "cohort_2"
        assert retrieved2.last_synced_head_cid == "Qm222"

    def test_get_node_state_isolates_by_record_type(self, test_db_connection):
        """get_node_state should only retrieve states for the specified record type."""
        state1 = NodeState(
            cohort_id="test_cohort",
            record_type="RecordType1",
            last_synced_head_cid="Qm111",
            last_synced_sequence=1,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=None,
        )
        state2 = NodeState(
            cohort_id="test_cohort",
            record_type="RecordType2",
            last_synced_head_cid="Qm222",
            last_synced_sequence=2,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=None,
        )
        set_node_state(test_db_connection, state1)
        set_node_state(test_db_connection, state2)

        retrieved1 = get_node_state(test_db_connection, "test_cohort", "RecordType1")
        retrieved2 = get_node_state(test_db_connection, "test_cohort", "RecordType2")

        assert retrieved1.record_type == "RecordType1"
        assert retrieved1.last_synced_head_cid == "Qm111"
        assert retrieved2.record_type == "RecordType2"
        assert retrieved2.last_synced_head_cid == "Qm222"


class TestSetNodeState:
    """Test set_node_state() database persistence."""

    def test_set_node_state_exists(self):
        """set_node_state function should be defined."""
        assert callable(set_node_state)

    def test_set_node_state_creates_new_record(self, test_db_connection):
        """set_node_state should create a new record if it doesn't exist."""
        state = NodeState(
            cohort_id="new_cohort",
            record_type="NewRecord",
            last_synced_head_cid="QmNew123",
            last_synced_sequence=1,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="building",
            last_sync_at="2026-05-19T12:00:00Z",
        )

        set_node_state(test_db_connection, state)

        retrieved = get_node_state(test_db_connection, "new_cohort", "NewRecord")
        assert retrieved is not None
        assert retrieved.cohort_id == "new_cohort"
        assert retrieved.last_synced_head_cid == "QmNew123"

    def test_set_node_state_updates_existing_record(self, test_db_connection):
        """set_node_state should update an existing record (upsert)."""
        # Create initial state
        initial_state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="QmOld123",
            last_synced_sequence=1,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at="2026-05-19T10:00:00Z",
        )
        set_node_state(test_db_connection, initial_state)

        # Update with new values
        updated_state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="QmNew456",
            last_synced_sequence=5,
            snapshot_cid="QmSnapshot999",
            snapshot_sequence=3,
            index_status="current",
            last_sync_at="2026-05-19T12:00:00Z",
        )
        set_node_state(test_db_connection, updated_state)

        # Verify update
        retrieved = get_node_state(test_db_connection, "test_cohort", "TestRecord")
        assert retrieved.last_synced_head_cid == "QmNew456"
        assert retrieved.last_synced_sequence == 5
        assert retrieved.snapshot_cid == "QmSnapshot999"
        assert retrieved.snapshot_sequence == 3
        assert retrieved.index_status == "current"
        assert retrieved.last_sync_at == "2026-05-19T12:00:00Z"

    def test_set_node_state_preserves_none_values(self, test_db_connection):
        """set_node_state should correctly persist None values."""
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid=None,
            last_synced_sequence=0,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=None,
        )

        set_node_state(test_db_connection, state)

        retrieved = get_node_state(test_db_connection, "test_cohort", "TestRecord")
        assert retrieved.last_synced_head_cid is None
        assert retrieved.snapshot_cid is None
        assert retrieved.last_sync_at is None

    def test_set_node_state_handles_concurrent_cohorts(self, test_db_connection):
        """set_node_state should handle multiple cohorts independently."""
        states = [
            NodeState(
                cohort_id=f"cohort_{i}",
                record_type="TestRecord",
                last_synced_head_cid=f"Qm{i}",
                last_synced_sequence=i,
                snapshot_cid=None,
                snapshot_sequence=0,
                index_status="cold",
                last_sync_at=None,
            )
            for i in range(5)
        ]

        for state in states:
            set_node_state(test_db_connection, state)

        for i, state in enumerate(states):
            retrieved = get_node_state(test_db_connection, f"cohort_{i}", "TestRecord")
            assert retrieved.cohort_id == f"cohort_{i}"
            assert retrieved.last_synced_head_cid == f"Qm{i}"
            assert retrieved.last_synced_sequence == i


class TestGetSetRoundTrip:
    """Test get/set round-trip correctness."""

    def test_round_trip_preserves_all_fields(self, test_db_connection):
        """Round-trip get/set should preserve all field values."""
        original = NodeState(
            cohort_id="round_trip_cohort",
            record_type="RoundTripRecord",
            last_synced_head_cid="QmRoundTrip123",
            last_synced_sequence=99,
            snapshot_cid="QmSnapshot456",
            snapshot_sequence=50,
            index_status="current",
            last_sync_at="2026-05-19T15:30:45Z",
        )

        set_node_state(test_db_connection, original)
        retrieved = get_node_state(
            test_db_connection, "round_trip_cohort", "RoundTripRecord"
        )

        assert retrieved.cohort_id == original.cohort_id
        assert retrieved.record_type == original.record_type
        assert retrieved.last_synced_head_cid == original.last_synced_head_cid
        assert retrieved.last_synced_sequence == original.last_synced_sequence
        assert retrieved.snapshot_cid == original.snapshot_cid
        assert retrieved.snapshot_sequence == original.snapshot_sequence
        assert retrieved.index_status == original.index_status
        assert retrieved.last_sync_at == original.last_sync_at

    def test_round_trip_with_minimal_state(self, test_db_connection):
        """Round-trip should work with minimal (never synced) state."""
        original = NodeState(
            cohort_id="minimal_cohort",
            record_type="MinimalRecord",
            last_synced_head_cid=None,
            last_synced_sequence=0,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=None,
        )

        set_node_state(test_db_connection, original)
        retrieved = get_node_state(
            test_db_connection, "minimal_cohort", "MinimalRecord"
        )

        assert retrieved.cohort_id == original.cohort_id
        assert retrieved.record_type == original.record_type
        assert retrieved.last_synced_head_cid is None
        assert retrieved.last_synced_sequence == 0
        assert retrieved.snapshot_cid is None
        assert retrieved.snapshot_sequence == 0
        assert retrieved.index_status == "cold"
        assert retrieved.last_sync_at is None

    def test_round_trip_multiple_updates(self, test_db_connection):
        """Multiple updates should correctly overwrite previous values."""
        cohort_id = "multi_update_cohort"
        record_type = "MultiUpdateRecord"

        # Initial state
        state1 = NodeState(
            cohort_id=cohort_id,
            record_type=record_type,
            last_synced_head_cid="Qm1",
            last_synced_sequence=1,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="building",
            last_sync_at="2026-05-19T10:00:00Z",
        )
        set_node_state(test_db_connection, state1)

        # Second state
        state2 = NodeState(
            cohort_id=cohort_id,
            record_type=record_type,
            last_synced_head_cid="Qm2",
            last_synced_sequence=2,
            snapshot_cid="QmSnap1",
            snapshot_sequence=1,
            index_status="current",
            last_sync_at="2026-05-19T11:00:00Z",
        )
        set_node_state(test_db_connection, state2)

        # Third state
        state3 = NodeState(
            cohort_id=cohort_id,
            record_type=record_type,
            last_synced_head_cid="Qm3",
            last_synced_sequence=3,
            snapshot_cid="QmSnap2",
            snapshot_sequence=2,
            index_status="stale",
            last_sync_at="2026-05-19T12:00:00Z",
        )
        set_node_state(test_db_connection, state3)

        # Verify final state matches state3
        retrieved = get_node_state(test_db_connection, cohort_id, record_type)
        assert retrieved.last_synced_head_cid == "Qm3"
        assert retrieved.last_synced_sequence == 3
        assert retrieved.snapshot_cid == "QmSnap2"
        assert retrieved.snapshot_sequence == 2
        assert retrieved.index_status == "stale"
        assert retrieved.last_sync_at == "2026-05-19T12:00:00Z"

    def test_round_trip_with_large_sequence_numbers(self, test_db_connection):
        """Round-trip should handle large sequence numbers correctly."""
        original = NodeState(
            cohort_id="large_seq_cohort",
            record_type="LargeSeqRecord",
            last_synced_head_cid="QmLarge",
            last_synced_sequence=999999999,
            snapshot_cid="QmSnapLarge",
            snapshot_sequence=888888888,
            index_status="current",
            last_sync_at="2026-05-19T12:00:00Z",
        )

        set_node_state(test_db_connection, original)
        retrieved = get_node_state(
            test_db_connection, "large_seq_cohort", "LargeSeqRecord"
        )

        assert retrieved.last_synced_sequence == 999999999
        assert retrieved.snapshot_sequence == 888888888


class TestUpsertBehavior:
    """Test upsert (insert-or-update) behavior explicitly."""

    def test_upsert_inserts_when_missing(self, test_db_connection):
        """Upsert should insert when record doesn't exist."""
        # Verify state doesn't exist initially
        initial = get_node_state(test_db_connection, "upsert_cohort", "UpsertRecord")
        assert initial is None

        # Upsert (should insert)
        state = NodeState(
            cohort_id="upsert_cohort",
            record_type="UpsertRecord",
            last_synced_head_cid="QmInsert",
            last_synced_sequence=1,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=None,
        )
        set_node_state(test_db_connection, state)

        # Verify inserted
        retrieved = get_node_state(test_db_connection, "upsert_cohort", "UpsertRecord")
        assert retrieved is not None
        assert retrieved.last_synced_head_cid == "QmInsert"

    def test_upsert_updates_when_exists(self, test_db_connection):
        """Upsert should update when record exists."""
        # Insert initial record
        initial = NodeState(
            cohort_id="upsert_cohort",
            record_type="UpsertRecord",
            last_synced_head_cid="QmOld",
            last_synced_sequence=1,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="cold",
            last_sync_at=None,
        )
        set_node_state(test_db_connection, initial)

        # Upsert (should update)
        updated = NodeState(
            cohort_id="upsert_cohort",
            record_type="UpsertRecord",
            last_synced_head_cid="QmNew",
            last_synced_sequence=5,
            snapshot_cid="QmSnap",
            snapshot_sequence=3,
            index_status="current",
            last_sync_at="2026-05-19T12:00:00Z",
        )
        set_node_state(test_db_connection, updated)

        # Verify only one record exists with updated values
        retrieved = get_node_state(test_db_connection, "upsert_cohort", "UpsertRecord")
        assert retrieved.last_synced_head_cid == "QmNew"
        assert retrieved.last_synced_sequence == 5

    def test_upsert_does_not_create_duplicates(self, test_db_connection):
        """Upsert should not create duplicate records for same cohort/record_type."""
        # Insert same state multiple times
        for i in range(5):
            modified_state = NodeState(
                cohort_id="dup_test_cohort",
                record_type="DupTestRecord",
                last_synced_head_cid=f"Qm{i}",
                last_synced_sequence=i,
                snapshot_cid=None,
                snapshot_sequence=0,
                index_status="cold",
                last_sync_at=None,
            )
            set_node_state(test_db_connection, modified_state)

        # Verify only one record exists with latest values
        retrieved = get_node_state(
            test_db_connection, "dup_test_cohort", "DupTestRecord"
        )
        assert retrieved is not None
        assert retrieved.last_synced_head_cid == "Qm4"
        assert retrieved.last_synced_sequence == 4

        # Verify no duplicates by querying database directly
        cursor = test_db_connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM _node_state WHERE cohort_id = ? AND record_type = ?",
            ("dup_test_cohort", "DupTestRecord"),
        )
        count = cursor.fetchone()[0]
        assert count == 1
