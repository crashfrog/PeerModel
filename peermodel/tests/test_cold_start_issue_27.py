#!/usr/bin/env python

"""Acceptance tests for SyncManager.cold_start() implementation (Issue #27).

Tests cover:
- ColdStartResult dataclass exists with correct fields
- cold_start() method exists on SyncManager
- Snapshot loaded and applied to index when provided
- Delta ops traversed from current head to snapshot head
- Full rebuild from genesis when no snapshot exists
- NodeState updated to "current" after cold start
- End-to-end: populate → snapshot → wipe index → cold_start recovers records
"""

import pytest
import asyncio
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import peermodel
import peermodel.primitives
from peermodel.operations import OperationRecord
from peermodel.delegation import SimpleCohort
from peermodel.state import NodeState, set_node_state, get_node_state
from peermodel.index import IndexDB
from peermodel.snapshots import Snapshot, SnapshotManager


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
    """Create a cohort for cold start testing."""
    return SimpleCohort(
        cohort_id="test_cohort_27", founder_identity=alice_identity
    )


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    yield db_path
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
def peer():
    """Create test App instance for cold start tests."""
    return peermodel.App("test_cold_start_27")


@pytest.fixture
def cold_record_model(peer):
    """Create a ColdRecord model for cold start tests."""
    @peer.model
    class ColdRecord:
        name: str
        value: int

    from peermodel.peermodel import DocumentObj
    return DocumentObj.Meta._reg['ColdRecord']


@pytest.fixture
def ed25519_signing_key():
    """Generate an Ed25519 private key for signing snapshots."""
    _, _, ed25519_priv, _ = peermodel.primitives.generate_keypair()
    return ed25519_priv


@pytest.fixture
def snapshot_with_two_records(index_db, cold_record_model, ed25519_signing_key):
    """Create a snapshot containing 2 live ColdRecord rows.

    Inserts two records into the IndexDB, creates a snapshot, then returns
    the snapshot.  The snapshot's log_head_cid is 'cid-snap-head' and its
    sequence_number is 2.
    """
    index_db.ensure_schema(cold_record_model)
    conn = sqlite3.connect(index_db.db_path)
    cursor = conn.cursor()
    for i, (name, val) in enumerate([('Alpha', 10), ('Beta', 20)], 1):
        cursor.execute(
            """
            INSERT INTO ColdRecord
                (_record_id, _op_id, _sequence, _timestamp, _head_cid,
                 _tombstoned, _schema_version, name, value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (f'rec-{i}', f'op-{i}', i, 1_000_000_000, f'cid-snap-{i}',
             0, 1, name, val),
        )
    conn.commit()
    conn.close()

    sm = SnapshotManager()
    return sm.create_snapshot(
        db=index_db,
        model_class=cold_record_model,
        cohort_id='test_cohort_27',
        record_type='ColdRecord',
        log_head_cid='cid-snap-head',
        sequence_number=2,
        signing_private_key=ed25519_signing_key,
        signing_algorithm='ed25519',
    )


def make_delta_op(test_cohort, seq, record_id='rec-delta', name='Delta', val=99):
    """Create a single OperationRecord representing a post-snapshot change."""
    op = test_cohort.create_operation(
        op_type='insert',
        record_type='ColdRecord',
        record_id=record_id,
        payload={'name': name, 'value': val},
        previous_head_cid='cid-snap-head',
        initiator=test_cohort.founder_identity,
    )
    op.ipfs_cid = f'Qm{seq:064x}'
    op.sequence_number = seq
    return op


# ============================================================================
# RETURN TYPE TESTS
# ============================================================================


@pytest.mark.issue_27
class TestColdStartResultDataclass:
    """ColdStartResult dataclass must exist with the correct fields."""

    def test_cold_start_result_is_importable(self):
        """ColdStartResult must be importable from peermodel.sync."""
        from peermodel.sync import ColdStartResult
        assert ColdStartResult is not None

    def test_cold_start_result_has_ops_applied(self):
        """ColdStartResult must have an ops_applied field."""
        from peermodel.sync import ColdStartResult
        from dataclasses import fields
        field_names = {f.name for f in fields(ColdStartResult)}
        assert 'ops_applied' in field_names, (
            "ColdStartResult missing 'ops_applied' field"
        )

    def test_cold_start_result_has_new_head_cid(self):
        """ColdStartResult must have a new_head_cid field."""
        from peermodel.sync import ColdStartResult
        from dataclasses import fields
        field_names = {f.name for f in fields(ColdStartResult)}
        assert 'new_head_cid' in field_names, (
            "ColdStartResult missing 'new_head_cid' field"
        )

    def test_cold_start_result_has_record_type(self):
        """ColdStartResult must have a record_type field."""
        from peermodel.sync import ColdStartResult
        from dataclasses import fields
        field_names = {f.name for f in fields(ColdStartResult)}
        assert 'record_type' in field_names, (
            "ColdStartResult missing 'record_type' field"
        )

    def test_cold_start_result_has_snapshot_applied(self):
        """ColdStartResult must have a snapshot_applied boolean field."""
        from peermodel.sync import ColdStartResult
        from dataclasses import fields
        field_names = {f.name for f in fields(ColdStartResult)}
        assert 'snapshot_applied' in field_names, (
            "ColdStartResult missing 'snapshot_applied' field"
        )


# ============================================================================
# METHOD EXISTENCE
# ============================================================================


@pytest.mark.issue_27
class TestColdStartMethodExists:
    """SyncManager must expose a cold_start() coroutine method."""

    def test_cold_start_method_exists(self):
        """SyncManager must have a cold_start attribute."""
        from peermodel.sync import SyncManager
        assert hasattr(SyncManager, 'cold_start'), (
            "SyncManager missing cold_start() method"
        )

    def test_cold_start_is_coroutine(self):
        """cold_start must be an async method (coroutine function)."""
        import inspect
        from peermodel.sync import SyncManager
        assert inspect.iscoroutinefunction(SyncManager.cold_start), (
            "SyncManager.cold_start must be declared async"
        )


# ============================================================================
# HAPPY PATH: cold start WITH snapshot
# ============================================================================


@pytest.mark.issue_27
class TestColdStartWithSnapshot:
    """cold_start() with a pre-existing snapshot."""

    @pytest.mark.asyncio
    async def test_cold_start_applies_snapshot_to_index(
        self, test_cohort, snapshot_with_two_records
    ):
        """cold_start() must call index_db.apply_snapshot() with the snapshot."""
        from peermodel.sync import SyncManager

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()
        mock_index_db.apply_snapshot = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []

            await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='cid-snap-head',
                snapshot=snapshot_with_two_records,
            )

        mock_index_db.apply_snapshot.assert_called_once_with(
            snapshot_with_two_records
        )

    @pytest.mark.asyncio
    async def test_cold_start_traverses_delta_after_snapshot(
        self, test_cohort, snapshot_with_two_records
    ):
        """cold_start() must traverse only ops newer than the snapshot head."""
        from peermodel.sync import SyncManager

        delta_op = make_delta_op(test_cohort, seq=3)

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()
        mock_index_db.apply_snapshot = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = [delta_op]

            await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm' + '0' * 62 + '03',
                snapshot=snapshot_with_two_records,
            )

        mock_traverse.assert_called_once()
        call_kwargs = mock_traverse.call_args[1]
        assert call_kwargs['stop_at_cid'] == 'cid-snap-head', (
            "traverse stop_at_cid must be the snapshot's log_head_cid"
        )

    @pytest.mark.asyncio
    async def test_cold_start_applies_delta_ops_after_snapshot(
        self, test_cohort, snapshot_with_two_records
    ):
        """cold_start() must apply each delta op to the index after snapshot."""
        from peermodel.sync import SyncManager

        delta_ops = [make_delta_op(test_cohort, seq=3 + i) for i in range(2)]

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()
        mock_index_db.apply_snapshot = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = delta_ops

            await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm' + '0' * 62 + '04',
                snapshot=snapshot_with_two_records,
            )

        assert mock_index_db.apply_operation.call_count == 2, (
            "apply_operation must be called once per delta op"
        )

    @pytest.mark.asyncio
    async def test_cold_start_returns_snapshot_applied_true(
        self, test_cohort, snapshot_with_two_records
    ):
        """ColdStartResult.snapshot_applied must be True when snapshot used."""
        from peermodel.sync import SyncManager

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()
        mock_index_db.apply_snapshot = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []

            result = await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='cid-snap-head',
                snapshot=snapshot_with_two_records,
            )

        assert result.snapshot_applied is True, (
            "ColdStartResult.snapshot_applied must be True when snapshot was used"
        )

    @pytest.mark.asyncio
    async def test_cold_start_result_ops_applied_counts_delta_only(
        self, test_cohort, snapshot_with_two_records
    ):
        """ColdStartResult.ops_applied counts only delta ops, not snapshot records."""
        from peermodel.sync import SyncManager

        delta_ops = [make_delta_op(test_cohort, seq=3 + i) for i in range(3)]

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()
        mock_index_db.apply_snapshot = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = delta_ops

            result = await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm' + '0' * 62 + '05',
                snapshot=snapshot_with_two_records,
            )

        assert result.ops_applied == 3, (
            f"ops_applied should be 3 (delta ops only), got {result.ops_applied}"
        )


# ============================================================================
# HAPPY PATH: cold start WITHOUT snapshot (full rebuild)
# ============================================================================


@pytest.mark.issue_27
class TestColdStartWithoutSnapshot:
    """cold_start() with no snapshot performs full traversal from genesis."""

    @pytest.mark.asyncio
    async def test_cold_start_traverses_from_genesis_without_snapshot(
        self, test_cohort
    ):
        """Without a snapshot, traverse from genesis (stop_at_cid=None)."""
        from peermodel.sync import SyncManager

        ops = [make_delta_op(test_cohort, seq=i + 1) for i in range(4)]

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = ops

            await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm' + '0' * 62 + '04',
                snapshot=None,
            )

        mock_traverse.assert_called_once()
        call_kwargs = mock_traverse.call_args[1]
        assert call_kwargs['stop_at_cid'] is None, (
            "traverse stop_at_cid must be None for full rebuild from genesis"
        )

    @pytest.mark.asyncio
    async def test_cold_start_does_not_call_apply_snapshot_without_snapshot(
        self, test_cohort
    ):
        """Without a snapshot, apply_snapshot must NOT be called."""
        from peermodel.sync import SyncManager

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()
        mock_index_db.apply_snapshot = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []

            await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm000',
                snapshot=None,
            )

        mock_index_db.apply_snapshot.assert_not_called()

    @pytest.mark.asyncio
    async def test_cold_start_applies_all_ops_without_snapshot(
        self, test_cohort
    ):
        """Without a snapshot, every op from genesis is applied to the index."""
        from peermodel.sync import SyncManager

        ops = [make_delta_op(test_cohort, seq=i + 1) for i in range(5)]

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = ops

            result = await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm' + '0' * 62 + '05',
                snapshot=None,
            )

        assert mock_index_db.apply_operation.call_count == 5, (
            "apply_operation must be called for every op in the full log"
        )
        assert result.ops_applied == 5, (
            f"ops_applied should be 5, got {result.ops_applied}"
        )

    @pytest.mark.asyncio
    async def test_cold_start_returns_snapshot_applied_false_without_snapshot(
        self, test_cohort
    ):
        """ColdStartResult.snapshot_applied must be False with no snapshot."""
        from peermodel.sync import SyncManager

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []

            result = await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm000',
                snapshot=None,
            )

        assert result.snapshot_applied is False, (
            "ColdStartResult.snapshot_applied must be False when no snapshot used"
        )


# ============================================================================
# NODE STATE UPDATE
# ============================================================================


@pytest.mark.issue_27
class TestColdStartUpdatesNodeState:
    """cold_start() must update NodeState to reflect the completed rebuild."""

    @pytest.mark.asyncio
    async def test_cold_start_sets_index_status_to_current(
        self, test_cohort
    ):
        """NodeState.index_status must be 'current' after cold_start."""
        from peermodel.sync import SyncManager

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []

            await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm000',
                snapshot=None,
            )

        mock_index_db.set_node_state.assert_called_once()
        saved_state = mock_index_db.set_node_state.call_args[0][0]
        assert saved_state.index_status == 'current', (
            f"index_status must be 'current' after cold start, "
            f"got '{saved_state.index_status}'"
        )

    @pytest.mark.asyncio
    async def test_cold_start_updates_last_synced_head_cid(
        self, test_cohort
    ):
        """NodeState.last_synced_head_cid must equal current_head_cid after cold_start."""
        from peermodel.sync import SyncManager

        current_head = 'QmFinalHead123456789'
        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []

            await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid=current_head,
                snapshot=None,
            )

        saved_state = mock_index_db.set_node_state.call_args[0][0]
        assert saved_state.last_synced_head_cid == current_head, (
            f"last_synced_head_cid must be '{current_head}', "
            f"got '{saved_state.last_synced_head_cid}'"
        )

    @pytest.mark.asyncio
    async def test_cold_start_updates_last_synced_sequence(
        self, test_cohort
    ):
        """NodeState.last_synced_sequence must equal the final op's sequence_number."""
        from peermodel.sync import SyncManager

        ops = [make_delta_op(test_cohort, seq=i + 1) for i in range(3)]

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = ops

            await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm' + '0' * 62 + '03',
                snapshot=None,
            )

        saved_state = mock_index_db.set_node_state.call_args[0][0]
        assert saved_state.last_synced_sequence == 3, (
            f"last_synced_sequence must be 3 (last op's seq), "
            f"got {saved_state.last_synced_sequence}"
        )

    @pytest.mark.asyncio
    async def test_cold_start_stores_snapshot_cid_in_node_state(
        self, test_cohort, snapshot_with_two_records
    ):
        """NodeState.snapshot_cid must be set to snapshot.snapshot_id after cold_start with snapshot."""
        from peermodel.sync import SyncManager

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()
        mock_index_db.apply_snapshot = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []

            await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='cid-snap-head',
                snapshot=snapshot_with_two_records,
            )

        saved_state = mock_index_db.set_node_state.call_args[0][0]
        assert saved_state.snapshot_cid == snapshot_with_two_records.snapshot_id, (
            "NodeState.snapshot_cid must be set to the applied snapshot's ID"
        )

    @pytest.mark.asyncio
    async def test_cold_start_sets_record_type_in_node_state(
        self, test_cohort
    ):
        """NodeState.record_type must match the record_type argument."""
        from peermodel.sync import SyncManager

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []

            await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm000',
                snapshot=None,
            )

        saved_state = mock_index_db.set_node_state.call_args[0][0]
        assert saved_state.record_type == 'ColdRecord', (
            f"NodeState.record_type must be 'ColdRecord', got '{saved_state.record_type}'"
        )

    @pytest.mark.asyncio
    async def test_cold_start_sets_cohort_id_in_node_state(
        self, test_cohort
    ):
        """NodeState.cohort_id must match the SyncManager's cohort identity."""
        from peermodel.sync import SyncManager

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []

            await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm000',
                snapshot=None,
            )

        saved_state = mock_index_db.set_node_state.call_args[0][0]
        assert saved_state.cohort_id == 'test_cohort_27', (
            f"NodeState.cohort_id must be 'test_cohort_27', got '{saved_state.cohort_id}'"
        )


# ============================================================================
# RETURN VALUE
# ============================================================================


@pytest.mark.issue_27
class TestColdStartReturnValue:
    """cold_start() must return a ColdStartResult with correct values."""

    @pytest.mark.asyncio
    async def test_cold_start_returns_cold_start_result_instance(
        self, test_cohort
    ):
        """cold_start() must return a ColdStartResult, not a SyncResult."""
        from peermodel.sync import SyncManager, ColdStartResult

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []

            result = await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm000',
                snapshot=None,
            )

        assert isinstance(result, ColdStartResult), (
            f"cold_start() must return ColdStartResult, got {type(result).__name__}"
        )

    @pytest.mark.asyncio
    async def test_cold_start_result_new_head_cid_matches_argument(
        self, test_cohort
    ):
        """ColdStartResult.new_head_cid must equal the current_head_cid passed in."""
        from peermodel.sync import SyncManager

        target_head = 'QmTargetHead999'
        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []

            result = await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid=target_head,
                snapshot=None,
            )

        assert result.new_head_cid == target_head, (
            f"ColdStartResult.new_head_cid must be '{target_head}', "
            f"got '{result.new_head_cid}'"
        )

    @pytest.mark.asyncio
    async def test_cold_start_result_record_type_matches_argument(
        self, test_cohort
    ):
        """ColdStartResult.record_type must match the record_type argument."""
        from peermodel.sync import SyncManager

        mock_index_db = MagicMock()
        mock_index_db.set_node_state = MagicMock()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=mock_index_db,
            snapshot_manager=MagicMock(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []

            result = await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm000',
                snapshot=None,
            )

        assert result.record_type == 'ColdRecord', (
            f"ColdStartResult.record_type must be 'ColdRecord', "
            f"got '{result.record_type}'"
        )


# ============================================================================
# END-TO-END INTEGRATION: populate → snapshot → wipe → cold_start recovers
# ============================================================================


@pytest.mark.issue_27
class TestColdStartEndToEnd:
    """Full scenario: wipe the index and verify cold_start restores it."""

    @pytest.mark.asyncio
    async def test_cold_start_recovers_records_from_snapshot(
        self,
        test_cohort,
        index_db,
        cold_record_model,
        snapshot_with_two_records,
        temp_db,
    ):
        """After a wipe, cold_start restores all records captured in the snapshot.

        Scenario (from issue acceptance criteria):
          1. Populate: 2 records exist in the index.
          2. Snapshot: snapshot_with_two_records captures those 2 records.
          3. Wipe: truncate the ColdRecord table (simulates cold/empty index).
          4. cold_start(): rebuild from snapshot (no delta ops).
          5. Verify: index contains exactly the 2 original records.
        """
        from peermodel.sync import SyncManager

        # Step 3 – wipe the index
        conn = sqlite3.connect(temp_db)
        conn.execute("DELETE FROM ColdRecord")
        conn.commit()
        conn.close()

        # Verify the index is empty before cold start
        rows_before = index_db.query(cold_record_model)
        assert len(rows_before) == 0, (
            "Pre-condition: index must be empty before cold_start"
        )

        # Step 4 – cold start with no delta (snapshot head == current head)
        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=index_db,
            snapshot_manager=SnapshotManager(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = []  # no delta ops

            result = await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='cid-snap-head',
                snapshot=snapshot_with_two_records,
            )

        # Step 5 – verify recovery
        rows_after = index_db.query(cold_record_model)
        assert len(rows_after) == 2, (
            f"cold_start must restore 2 records from snapshot, "
            f"found {len(rows_after)}"
        )
        names = {r['name'] for r in rows_after}
        assert names == {'Alpha', 'Beta'}, (
            f"Restored records must have names {{'Alpha', 'Beta'}}, got {names}"
        )
        assert result.snapshot_applied is True
        assert result.ops_applied == 0

    @pytest.mark.asyncio
    async def test_cold_start_recovers_snapshot_plus_delta(
        self,
        test_cohort,
        index_db,
        cold_record_model,
        snapshot_with_two_records,
        temp_db,
    ):
        """cold_start restores snapshot records AND applies subsequent delta ops.

        Scenario:
          1. Snapshot captures 2 records (Alpha, Beta) at head 'cid-snap-head'.
          2. Wipe the index.
          3. A new op (insert Gamma) exists between snapshot head and current head.
          4. cold_start() should restore Alpha + Beta from snapshot, then apply
             the Gamma insert, leaving 3 records total.
        """
        from peermodel.sync import SyncManager

        # Build a delta op that inserts a new record after the snapshot
        gamma_op = make_delta_op(
            test_cohort, seq=3, record_id='rec-gamma', name='Gamma', val=30
        )

        # Wipe the index
        conn = sqlite3.connect(temp_db)
        conn.execute("DELETE FROM ColdRecord")
        conn.commit()
        conn.close()

        mgr = SyncManager(
            cohort_identity=test_cohort,
            index_db=index_db,
            snapshot_manager=SnapshotManager(),
            ipfs_client=MagicMock(),
        )

        with patch('peermodel.sync.traverse') as mock_traverse:
            mock_traverse.return_value = [gamma_op]

            result = await mgr.cold_start(
                record_type='ColdRecord',
                current_head_cid='Qm' + '0' * 62 + '03',
                snapshot=snapshot_with_two_records,
            )

        # Verify traverse was called with correct stop_at_cid
        call_kwargs = mock_traverse.call_args[1]
        assert call_kwargs['stop_at_cid'] == 'cid-snap-head', (
            "Delta traversal must start from snapshot head"
        )

        assert result.ops_applied == 1, (
            f"1 delta op should have been applied, got {result.ops_applied}"
        )
        assert result.snapshot_applied is True
