#!/usr/bin/env python

"""Acceptance tests for SyncManager.incremental_sync() implementation (Issue #26).

Tests cover:
- Fetch only new operations since last_synced_head_cid
- Apply operations in chronological order
- Update NodeState with new head, sequence, and last_sync_at
- Edge cases: no new operations, first sync with old state
"""

import pytest
import asyncio
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

import peermodel.primitives
from peermodel.operations import OperationRecord
from peermodel.delegation import SimpleCohort
from peermodel.state import NodeState, set_node_state, get_node_state
from peermodel.index import IndexDB


# ============================================================================
# FIXTURES
# ============================================================================


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
def test_cohort(alice_identity):
    """Create a cohort for operation testing."""
    return SimpleCohort(
        cohort_id="test_cohort", founder_identity=alice_identity
    )


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
def test_db_connection(temp_db):
    """Create and return a test database connection."""
    conn = sqlite3.connect(temp_db)
    yield conn
    conn.close()


@pytest.fixture
def index_db(temp_db):
    """Create an IndexDB instance with a temporary database."""
    return IndexDB(temp_db)


@pytest.fixture
def sample_operations_chain(test_cohort, alice_identity):
    """Create a chain of operations simulating history and new additions."""
    operations = []
    previous_cid = None

    # Create 5 initial operations (simulating past synced state)
    for i in range(5):
        op = test_cohort.create_operation(
            op_type="insert" if i == 0 else "update",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": f"value{i}", "index": i},
            previous_head_cid=previous_cid,
            initiator=alice_identity,
        )
        op.ipfs_cid = f"Qm{i:064x}"
        operations.append(op)
        previous_cid = op.ipfs_cid

    return operations


@pytest.fixture
def mock_ipfs_client(sample_operations_chain):
    """Mock IPFS client that returns operations by CID."""
    client = MagicMock()

    # Create lookup dict: CID -> operation
    op_lookup = {op.ipfs_cid: op for op in sample_operations_chain}

    async def mock_fetch(cid):
        """Simulate fetching operation from IPFS."""
        await asyncio.sleep(0.01)  # Simulate network delay
        if cid in op_lookup:
            return op_lookup[cid]
        raise ValueError(f"CID not found: {cid}")

    client.fetch = mock_fetch
    return client


# ============================================================================
# HAPPY PATH TESTS
# ============================================================================


@pytest.mark.issue_26
class TestIncrementalSyncHappyPath:
    """Happy path: successfully sync incremental operations."""

    @pytest.mark.asyncio
    async def test_incremental_sync_function_exists(self):
        """incremental_sync() method must be defined."""
        # This will fail until implementation exists
        try:
            from peermodel.sync import SyncManager
            assert hasattr(SyncManager, 'incremental_sync')
        except (ImportError, AttributeError):
            pytest.fail(
                "SyncManager.incremental_sync() not yet implemented"
            )

    @pytest.mark.asyncio
    async def test_incremental_sync_fetches_new_ops_only(
        self, test_cohort, test_db_connection, sample_operations_chain
    ):
        """incremental_sync() fetches only operations after last_synced_head_cid."""
        from peermodel.sync import SyncManager

        # Simulate already synced first 3 operations
        op_lookup = {op.ipfs_cid: op for op in sample_operations_chain}
        last_synced_cid = sample_operations_chain[2].ipfs_cid
        last_synced_seq = 3

        # Create state reflecting previous sync
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid=last_synced_cid,
            last_synced_sequence=last_synced_seq,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="current",
            last_sync_at="2026-05-19T10:00:00Z",
        )
        set_node_state(test_db_connection, state)

        # Mock IPFS client
        client = MagicMock()
        async def mock_fetch(cid):
            if cid in op_lookup:
                return op_lookup[cid]
            raise ValueError(f"CID not found: {cid}")
        client.fetch = mock_fetch

        # Create SyncManager and call incremental_sync
        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=None,  # Not used in this test
            snapshot_manager=None,
            ipfs_client=client
        )

        # Mock traverse to verify it's called with correct stop_at_cid
        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = [
                sample_operations_chain[3],
                sample_operations_chain[4],
            ]

            # incremental_sync should call traverse with stop_at_cid
            result = await mgr.incremental_sync(
                record_type="TestRecord",
                current_head_cid=sample_operations_chain[-1].ipfs_cid
            )

            # Verify traverse was called with stop_at_cid set to last_synced_cid
            mock_traverse.assert_called_once()
            call_args = mock_traverse.call_args
            assert call_args[1]['stop_at_cid'] == last_synced_cid

    @pytest.mark.asyncio
    async def test_incremental_sync_applies_ops_in_order(
        self, test_cohort, test_db_connection
    ):
        """incremental_sync() applies fetched ops in chronological order."""
        from peermodel.sync import SyncManager

        # Create new operations to apply
        new_ops = []
        for i in range(3):
            op = test_cohort.create_operation(
                op_type="update",
                record_type="TestRecord",
                record_id="rec-1",
                payload={"data": f"new{i}"},
                previous_head_cid=None,
                initiator=test_cohort.founder_identity,
            )
            op.ipfs_cid = f"QmNew{i}"
            op.sequence_number = 100 + i + 1  # 101, 102, 103
            new_ops.append(op)

        # Create initial state
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="QmOld",
            last_synced_sequence=100,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="current",
            last_sync_at="2026-05-19T10:00:00Z",
        )
        set_node_state(test_db_connection, state)

        # Mock IndexDB and traverse
        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        # Create SyncManager
        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=None,
            ipfs_client=MagicMock()
        )

        # Mock traverse to return the new operations
        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = new_ops

            result = await mgr.incremental_sync(
                record_type="TestRecord",
                current_head_cid="QmNew2"
            )

            # Verify apply_operation was called for each op in order
            assert mock_index_db.apply_operation.call_count == 3
            calls = mock_index_db.apply_operation.call_args_list
            for i, call in enumerate(calls):
                assert call[0][0].sequence_number == 101 + i

    @pytest.mark.asyncio
    async def test_incremental_sync_updates_node_state(
        self, test_cohort, test_db_connection
    ):
        """incremental_sync() updates NodeState with new head and sequence."""
        from peermodel.sync import SyncManager

        # Create new operations
        new_ops = []
        for i in range(2):
            op = test_cohort.create_operation(
                op_type="update",
                record_type="TestRecord",
                record_id="rec-1",
                payload={"data": f"new{i}"},
                previous_head_cid=None,
                initiator=test_cohort.founder_identity,
            )
            op.ipfs_cid = f"QmNew{i}"
            op.sequence_number = 101 + i
            new_ops.append(op)

        # Create initial state
        initial_state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="QmOld",
            last_synced_sequence=100,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="current",
            last_sync_at="2026-05-19T10:00:00Z",
        )
        set_node_state(test_db_connection, initial_state)

        # Create IndexDB instance
        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        # Create SyncManager
        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=None,
            ipfs_client=MagicMock()
        )

        # Mock traverse
        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = new_ops

            result = await mgr.incremental_sync(
                record_type="TestRecord",
                current_head_cid="QmNew1"
            )

            # Verify set_node_state was called
            mock_index_db.set_node_state.assert_called_once()
            updated_state = mock_index_db.set_node_state.call_args[0][0]

            # Verify updated NodeState has new values
            assert updated_state.last_synced_head_cid == "QmNew1"
            assert updated_state.last_synced_sequence == 102
            assert updated_state.last_sync_at is not None


# ============================================================================
# INCREMENTAL SYNC WITH NO NEW OPS
# ============================================================================


@pytest.mark.issue_26
class TestIncrementalSyncNoNewOps:
    """Test incremental_sync when head hasn't changed."""

    @pytest.mark.asyncio
    async def test_incremental_sync_with_matching_head_returns_early(
        self, test_cohort, test_db_connection
    ):
        """incremental_sync() returns early if current_head matches last_synced_head."""
        from peermodel.sync import SyncManager

        # Create state where head matches
        matching_cid = "QmMatching123"
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid=matching_cid,
            last_synced_sequence=50,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="current",
            last_sync_at="2026-05-19T10:00:00Z",
        )
        set_node_state(test_db_connection, state)

        mock_index_db = MagicMock()
        mock_index_db.get_node_state = MagicMock(return_value=state)

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=None,
            ipfs_client=MagicMock()
        )

        result = await mgr.incremental_sync(
            record_type="TestRecord",
            current_head_cid=matching_cid
        )

        # Should return with 0 ops applied
        assert result.ops_applied == 0


@pytest.mark.issue_26
class TestIncrementalSyncEdgeCases:
    """Test edge cases for incremental_sync."""

    @pytest.mark.asyncio
    async def test_incremental_sync_first_sync_from_genesis(
        self, test_cohort, test_db_connection
    ):
        """incremental_sync() handles first sync when last_synced_head_cid is None."""
        from peermodel.sync import SyncManager

        # Create state for first sync
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

        mock_index_db = MagicMock()
        mock_index_db.get_node_state = MagicMock(return_value=state)

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=None,
            ipfs_client=MagicMock()
        )

        # Mock traverse to return operations
        ops = []
        for i in range(3):
            op = test_cohort.create_operation(
                op_type="insert" if i == 0 else "update",
                record_type="TestRecord",
                record_id="rec-1",
                payload={"data": f"val{i}"},
                previous_head_cid=None,
                initiator=test_cohort.founder_identity,
            )
            op.sequence_number = i + 1
            ops.append(op)

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = ops

            result = await mgr.incremental_sync(
                record_type="TestRecord",
                current_head_cid="QmHead"
            )

            # traverse should be called with stop_at_cid=None for first sync
            mock_traverse.assert_called_once()
            assert mock_traverse.call_args[1]['stop_at_cid'] is None

    @pytest.mark.asyncio
    async def test_incremental_sync_single_new_op(
        self, test_cohort, test_db_connection
    ):
        """incremental_sync() applies exactly one operation correctly."""
        from peermodel.sync import SyncManager

        # Create single new operation
        new_op = test_cohort.create_operation(
            op_type="update",
            record_type="TestRecord",
            record_id="rec-1",
            payload={"data": "single"},
            previous_head_cid=None,
            initiator=test_cohort.founder_identity,
        )
        new_op.ipfs_cid = "QmNew"
        new_op.sequence_number = 101

        # Previous state
        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="QmOld",
            last_synced_sequence=100,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="current",
            last_sync_at="2026-05-19T10:00:00Z",
        )
        set_node_state(test_db_connection, state)

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=None,
            ipfs_client=MagicMock()
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = [new_op]

            result = await mgr.incremental_sync(
                record_type="TestRecord",
                current_head_cid="QmNew"
            )

            # Verify one operation was applied
            mock_index_db.apply_operation.assert_called_once_with(new_op)

    @pytest.mark.asyncio
    async def test_incremental_sync_large_batch(
        self, test_cohort, test_db_connection
    ):
        """incremental_sync() handles large batch of new operations."""
        from peermodel.sync import SyncManager

        # Create many new operations
        new_ops = []
        for i in range(50):
            op = test_cohort.create_operation(
                op_type="update",
                record_type="TestRecord",
                record_id="rec-1",
                payload={"data": f"val{i}"},
                previous_head_cid=None,
                initiator=test_cohort.founder_identity,
            )
            op.ipfs_cid = f"QmNew{i}"
            op.sequence_number = 100 + i + 1
            new_ops.append(op)

        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="QmOld",
            last_synced_sequence=100,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="current",
            last_sync_at="2026-05-19T10:00:00Z",
        )
        set_node_state(test_db_connection, state)

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=None,
            ipfs_client=MagicMock()
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = new_ops

            result = await mgr.incremental_sync(
                record_type="TestRecord",
                current_head_cid="QmNew49"
            )

            # All operations should be applied
            assert mock_index_db.apply_operation.call_count == 50

    @pytest.mark.asyncio
    async def test_incremental_sync_timestamp_is_current(
        self, test_cohort, test_db_connection
    ):
        """incremental_sync() sets last_sync_at to current time."""
        from peermodel.sync import SyncManager

        new_op = test_cohort.create_operation(
            op_type="update",
            record_type="TestRecord",
            record_id="rec-1",
            payload={"data": "test"},
            previous_head_cid=None,
            initiator=test_cohort.founder_identity,
        )
        new_op.sequence_number = 101

        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="QmOld",
            last_synced_sequence=100,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="current",
            last_sync_at="2026-05-19T10:00:00Z",
        )
        set_node_state(test_db_connection, state)

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=None,
            ipfs_client=MagicMock()
        )

        before_sync = datetime.utcnow().isoformat()

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = [new_op]

            result = await mgr.incremental_sync(
                record_type="TestRecord",
                current_head_cid="QmNew"
            )

        after_sync = datetime.utcnow().isoformat()

        # Extract the updated state
        updated_state = mock_index_db.set_node_state.call_args[0][0]

        # Verify timestamp is reasonable
        assert updated_state.last_sync_at is not None
        assert before_sync <= updated_state.last_sync_at <= after_sync


# ============================================================================
# RETURN VALUE TESTS
# ============================================================================


@pytest.mark.issue_26
class TestIncrementalSyncReturnValue:
    """Test SyncResult return value structure."""

    @pytest.mark.asyncio
    async def test_incremental_sync_returns_sync_result(
        self, test_cohort, test_db_connection
    ):
        """incremental_sync() returns SyncResult with correct structure."""
        from peermodel.sync import SyncManager, SyncResult

        new_ops = []
        for i in range(2):
            op = test_cohort.create_operation(
                op_type="update",
                record_type="TestRecord",
                record_id="rec-1",
                payload={"data": f"val{i}"},
                previous_head_cid=None,
                initiator=test_cohort.founder_identity,
            )
            op.sequence_number = 100 + i + 1
            new_ops.append(op)

        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="QmOld",
            last_synced_sequence=100,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="current",
            last_sync_at="2026-05-19T10:00:00Z",
        )
        set_node_state(test_db_connection, state)

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=None,
            ipfs_client=MagicMock()
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = new_ops

            result = await mgr.incremental_sync(
                record_type="TestRecord",
                current_head_cid="QmNew1"
            )

            # Verify result is a SyncResult
            assert isinstance(result, SyncResult)

    @pytest.mark.asyncio
    async def test_sync_result_has_ops_applied_field(
        self, test_cohort, test_db_connection
    ):
        """SyncResult should have ops_applied field with count."""
        from peermodel.sync import SyncManager

        new_ops = []
        for i in range(3):
            op = test_cohort.create_operation(
                op_type="update",
                record_type="TestRecord",
                record_id="rec-1",
                payload={"data": f"val{i}"},
                previous_head_cid=None,
                initiator=test_cohort.founder_identity,
            )
            op.sequence_number = 100 + i + 1
            new_ops.append(op)

        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="QmOld",
            last_synced_sequence=100,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="current",
            last_sync_at="2026-05-19T10:00:00Z",
        )
        set_node_state(test_db_connection, state)

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=None,
            ipfs_client=MagicMock()
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = new_ops

            result = await mgr.incremental_sync(
                record_type="TestRecord",
                current_head_cid="QmNew2"
            )

            # Verify ops_applied count is correct
            assert hasattr(result, 'ops_applied')
            assert result.ops_applied == 3

    @pytest.mark.asyncio
    async def test_sync_result_has_new_head_cid_field(
        self, test_cohort, test_db_connection
    ):
        """SyncResult should have new_head_cid field."""
        from peermodel.sync import SyncManager

        new_op = test_cohort.create_operation(
            op_type="update",
            record_type="TestRecord",
            record_id="rec-1",
            payload={"data": "test"},
            previous_head_cid=None,
            initiator=test_cohort.founder_identity,
        )
        new_op.sequence_number = 101

        state = NodeState(
            cohort_id="test_cohort",
            record_type="TestRecord",
            last_synced_head_cid="QmOld",
            last_synced_sequence=100,
            snapshot_cid=None,
            snapshot_sequence=0,
            index_status="current",
            last_sync_at="2026-05-19T10:00:00Z",
        )
        set_node_state(test_db_connection, state)

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=None,
            ipfs_client=MagicMock()
        )

        new_head = "QmNewHead123"

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = [new_op]

            result = await mgr.incremental_sync(
                record_type="TestRecord",
                current_head_cid=new_head
            )

            # Verify new_head_cid is set
            assert hasattr(result, 'new_head_cid')
            assert result.new_head_cid == new_head


@pytest.mark.issue_26
class TestIncrementalSyncIntegration:
    """Integration tests combining multiple aspects."""

    @pytest.mark.asyncio
    async def test_incremental_sync_multiple_record_types_isolated(
        self, test_cohort, test_db_connection
    ):
        """incremental_sync() for one record_type doesn't affect others."""
        from peermodel.sync import SyncManager

        # Create operations for TestRecord
        op1 = test_cohort.create_operation(
            op_type="update",
            record_type="TestRecord",
            record_id="rec-1",
            payload={"data": "test1"},
            previous_head_cid=None,
            initiator=test_cohort.founder_identity,
        )
        op1.sequence_number = 101

        # Create operations for OtherRecord
        op2 = test_cohort.create_operation(
            op_type="update",
            record_type="OtherRecord",
            record_id="rec-2",
            payload={"data": "other1"},
            previous_head_cid=None,
            initiator=test_cohort.founder_identity,
        )
        op2.sequence_number = 201

        # Setup state for both record types
        for record_type in ["TestRecord", "OtherRecord"]:
            state = NodeState(
                cohort_id="test_cohort",
                record_type=record_type,
                last_synced_head_cid="QmOld",
                last_synced_sequence=100 if record_type == "TestRecord" else 200,
                snapshot_cid=None,
                snapshot_sequence=0,
                index_status="current",
                last_sync_at="2026-05-19T10:00:00Z",
            )
            set_node_state(test_db_connection, state)

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=None,
            ipfs_client=MagicMock()
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = [op1]

            result = await mgr.incremental_sync(
                record_type="TestRecord",
                current_head_cid="QmNew1"
            )

            # Verify only TestRecord ops were applied
            assert result.record_type == "TestRecord"
            assert result.ops_applied == 1
