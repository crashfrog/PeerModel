#!/usr/bin/env python

"""Acceptance tests for CohortRepository main interface (Issue #28).

Tests cover all acceptance criteria:
- save: encrypt, create op, publish to IPFS, apply to index
- get: fetch from IPFS, decrypt, deserialize
- query: SQLite index lookup + IPFS fetch+decrypt
- query_index: raw SQLite rows (fast path, no IPFS)
- delete: tombstone operation published + applied to index
- sync: delegate to SyncManager
- Full save/get/query/delete round-trip

All tests are marked @pytest.mark.issue_28 and are RED until
peermodel/repository.py::CohortRepository is implemented.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import peermodel
import peermodel.peermodel as _pm
from peermodel.primitives import generate_keypair
from peermodel.delegation import create_cohort, SimpleCohort
from peermodel.index import IndexDB
from peermodel.operations import OperationRecord
from peermodel.sync import SyncResult


# ============================================================================
# FAKE IPFS CLIENT
# ============================================================================


class FakeIPFSClient:
    """In-memory fake IPFS client that stores OperationRecords by fake CID."""

    def __init__(self):
        self._store = {}
        self._counter = 0
        self.published = []
        self.fetch_count = 0

    async def publish(self, op):
        cid = f"QmFake{self._counter:08x}"
        self._store[cid] = op
        self._counter += 1
        self.published.append(op)
        return cid

    async def fetch(self, cid):
        self.fetch_count += 1
        if cid not in self._store:
            raise KeyError(f"CID not found: {cid}")
        return self._store[cid]


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def alice_identity():
    """Generate Alice's identity keypair."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
    return {
        'member_id': 'alice',
        'x25519_private': x25519_priv,
        'x25519_public': x25519_pub,
        'ed25519_private': ed25519_priv,
        'ed25519_public': ed25519_pub,
    }


@pytest.fixture
def cohort_setup(alice_identity):
    """Create cohort; return (SimpleCohort, CohortIdentity, cohort_private_key_bytes)."""
    cohort_identity, keybundle, cohort_private_key_bytes = create_cohort(
        cohort_id='test_cohort_28',
        founder_identity=alice_identity,
    )
    cohort = SimpleCohort(
        cohort_id='test_cohort_28',
        founder_identity=alice_identity,
    )
    return cohort, cohort_identity, cohort_private_key_bytes


@pytest.fixture
def temp_db():
    """Temporary SQLite database file."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def index_db(temp_db):
    """IndexDB instance backed by temp file."""
    return IndexDB(temp_db)


@pytest.fixture
def fake_ipfs():
    """In-memory fake IPFS client."""
    return FakeIPFSClient()


@pytest.fixture
def peer():
    """App instance for defining models."""
    return peermodel.App("test_cohort_repo_28")


@pytest.fixture
def item_model(peer):
    """Simple model with indexed fields for repository tests."""
    @peer.model
    class Item:
        name: str
        value: int

    peer.indexed('Item', 'name')
    peer.indexed('Item', 'value')
    return _pm.DocumentObj.Meta._reg['Item']


@pytest.fixture
def repo(cohort_setup, alice_identity, index_db, fake_ipfs, item_model):
    """CohortRepository configured with test cohort, IndexDB, and fake IPFS."""
    from peermodel.repository import CohortRepository

    cohort, cohort_identity, cohort_private_key_bytes = cohort_setup
    index_db.ensure_schema(item_model)

    return CohortRepository(
        cohort=cohort,
        member_identity=alice_identity,
        cohort_private_key_bytes=cohort_private_key_bytes,
        index_db=index_db,
        ipfs_client=fake_ipfs,
    )


@pytest.fixture
def sample_item(item_model):
    """A single Item document for use in tests."""
    return item_model(name='Widget', value=42)


@pytest.fixture
def mock_sync_manager():
    """Mock SyncManager for delegation tests."""
    return MagicMock()


@pytest.fixture
def repo_with_sync(cohort_setup, alice_identity, index_db, fake_ipfs, item_model, mock_sync_manager):
    """CohortRepository with a mock SyncManager attached."""
    from peermodel.repository import CohortRepository

    cohort, cohort_identity, cohort_private_key_bytes = cohort_setup
    index_db.ensure_schema(item_model)

    return CohortRepository(
        cohort=cohort,
        member_identity=alice_identity,
        cohort_private_key_bytes=cohort_private_key_bytes,
        index_db=index_db,
        ipfs_client=fake_ipfs,
        sync_manager=mock_sync_manager,
    )


# ============================================================================
# TESTS: save()
# ============================================================================


@pytest.mark.issue_28
class TestSave:
    """save(doc) must encrypt, create an insert op, publish to IPFS, apply to index."""

    @pytest.mark.asyncio
    async def test_save_returns_string_cid(self, repo, sample_item):
        """save() returns a non-empty string CID identifying the published operation."""
        cid = await repo.save(sample_item)

        assert isinstance(cid, str), (
            f"save() must return str CID, got {type(cid)}"
        )
        assert len(cid) > 0, "save() must return a non-empty CID"

    @pytest.mark.asyncio
    async def test_save_publishes_exactly_one_operation(self, repo, sample_item, fake_ipfs):
        """save() publishes exactly one OperationRecord to IPFS."""
        await repo.save(sample_item)

        assert len(fake_ipfs.published) == 1, (
            f"save() must publish exactly one operation to IPFS, "
            f"got {len(fake_ipfs.published)}"
        )

    @pytest.mark.asyncio
    async def test_save_published_object_is_operation_record(self, repo, sample_item, fake_ipfs):
        """The object published to IPFS is an OperationRecord."""
        await repo.save(sample_item)

        published_op = fake_ipfs.published[0]
        assert isinstance(published_op, OperationRecord), (
            f"Published object must be OperationRecord, got {type(published_op)}"
        )

    @pytest.mark.asyncio
    async def test_save_creates_insert_operation(self, repo, sample_item, fake_ipfs):
        """First save() of a record creates an 'insert' operation."""
        await repo.save(sample_item)

        op = fake_ipfs.published[0]
        assert op.op_type == 'insert', (
            f"First save must use op_type 'insert', got '{op.op_type}'"
        )

    @pytest.mark.asyncio
    async def test_save_operation_has_correct_record_type(self, repo, item_model, fake_ipfs):
        """Saved operation's record_type matches the model class name."""
        item = item_model(name='Gadget', value=99)
        await repo.save(item)

        op = fake_ipfs.published[0]
        assert op.record_type == 'Item', (
            f"Operation record_type must be 'Item', got '{op.record_type}'"
        )

    @pytest.mark.asyncio
    async def test_save_operation_record_id_matches_document_id(self, repo, sample_item, fake_ipfs):
        """Saved operation's record_id matches the document's _id."""
        await repo.save(sample_item)

        op = fake_ipfs.published[0]
        assert op.record_id == sample_item._id, (
            f"Operation record_id must be '{sample_item._id}', got '{op.record_id}'"
        )

    @pytest.mark.asyncio
    async def test_save_payload_is_encrypted_not_plaintext(self, repo, item_model, fake_ipfs):
        """The payload stored in IPFS does not contain plaintext field values.

        This verifies the security property: data in IPFS must be encrypted.
        """
        item = item_model(name='SecretWidgetXYZ', value=99999)
        await repo.save(item)

        op = fake_ipfs.published[0]
        payload_str = str(op.payload)

        assert 'SecretWidgetXYZ' not in payload_str, (
            "Payload stored in IPFS must not contain plaintext field values — "
            "data should be encrypted before publish"
        )
        assert '99999' not in payload_str, (
            "Payload stored in IPFS must not contain plaintext integer values — "
            "data should be encrypted before publish"
        )

    @pytest.mark.asyncio
    async def test_save_applies_record_to_index(self, repo, item_model, sample_item):
        """After save(), the record appears in query_index() results."""
        await repo.save(sample_item)

        rows = repo.query_index(item_model)
        assert len(rows) == 1, (
            f"After save, query_index must return 1 row, got {len(rows)}"
        )
        assert rows[0]['_record_id'] == sample_item._id, (
            f"Index row _record_id must be '{sample_item._id}', "
            f"got '{rows[0]['_record_id']}'"
        )

    @pytest.mark.asyncio
    async def test_save_index_row_stores_head_cid(self, repo, item_model, sample_item):
        """The index row for a saved record stores the returned CID in _head_cid."""
        cid = await repo.save(sample_item)

        rows = repo.query_index(item_model)
        assert len(rows) == 1
        assert rows[0]['_head_cid'] == cid, (
            f"Index _head_cid must equal the published CID '{cid}', "
            f"got '{rows[0]['_head_cid']}'"
        )


# ============================================================================
# TESTS: get()
# ============================================================================


@pytest.mark.issue_28
class TestGet:
    """get(record_type, record_id) must fetch from IPFS, decrypt, deserialize."""

    @pytest.mark.asyncio
    async def test_get_returns_document_obj_instance(self, repo, item_model, sample_item):
        """get() returns a DocumentObj instance."""
        await repo.save(sample_item)

        result = await repo.get(item_model, sample_item._id)

        assert isinstance(result, _pm.DocumentObj), (
            f"get() must return DocumentObj, got {type(result)}"
        )

    @pytest.mark.asyncio
    async def test_get_returns_document_with_correct_id(self, repo, item_model, sample_item):
        """get() returns document whose _id matches what was saved."""
        await repo.save(sample_item)

        result = await repo.get(item_model, sample_item._id)

        assert result._id == sample_item._id, (
            f"get() _id must be '{sample_item._id}', got '{result._id}'"
        )

    @pytest.mark.asyncio
    async def test_get_returns_correct_field_values_after_decryption(self, repo, item_model):
        """get() decrypts and returns the correct field values."""
        item = item_model(name='DecryptedWidget', value=777)
        await repo.save(item)

        result = await repo.get(item_model, item._id)

        assert result.name == 'DecryptedWidget', (
            f"get() name must be 'DecryptedWidget', got '{result.name}'"
        )
        assert result.value == 777, (
            f"get() value must be 777, got {result.value}"
        )

    @pytest.mark.asyncio
    async def test_get_nonexistent_id_raises_error_with_id_in_message(self, repo, item_model):
        """get() with unknown record_id raises an error naming the missing ID."""
        missing_id = 'no-such-record-00000000'
        with pytest.raises(Exception) as exc_info:
            await repo.get(item_model, missing_id)

        assert missing_id in str(exc_info.value), (
            f"Error message must reference the missing record ID '{missing_id}', "
            f"got: {exc_info.value}"
        )


# ============================================================================
# TESTS: query()
# ============================================================================


@pytest.mark.issue_28
class TestQuery:
    """query(record_type, filters) must use SQLite index then fetch each from IPFS."""

    @pytest.mark.asyncio
    async def test_query_empty_repository_returns_empty_list(self, repo, item_model):
        """query() on a repository with no records returns []."""
        results = await repo.query(item_model)

        assert results == [], (
            f"query() on empty repo must return [], got {results}"
        )

    @pytest.mark.asyncio
    async def test_query_returns_all_saved_records(self, repo, item_model):
        """query() without filters returns all saved records."""
        items = [item_model(name=f'Batch{i}', value=i) for i in range(3)]
        for item in items:
            await repo.save(item)

        results = await repo.query(item_model)

        assert len(results) == 3, (
            f"query() must return 3 results after 3 saves, got {len(results)}"
        )

    @pytest.mark.asyncio
    async def test_query_returns_document_obj_instances_not_dicts(self, repo, item_model, sample_item):
        """query() returns DocumentObj instances, not raw dicts."""
        await repo.save(sample_item)

        results = await repo.query(item_model)

        assert len(results) == 1
        assert isinstance(results[0], _pm.DocumentObj), (
            f"query() must return DocumentObj instances, got {type(results[0])}"
        )

    @pytest.mark.asyncio
    async def test_query_with_exact_filter_returns_only_matching_records(self, repo, item_model):
        """query() with filters returns only records matching the filter."""
        await repo.save(item_model(name='Alpha', value=10))
        await repo.save(item_model(name='Beta', value=20))
        await repo.save(item_model(name='Alpha', value=30))

        results = await repo.query(item_model, filters={'name': 'Alpha'})

        assert len(results) == 2, (
            f"query(name='Alpha') must return 2 records, got {len(results)}"
        )
        for result in results:
            assert result.name == 'Alpha', (
                f"All results must have name='Alpha', got '{result.name}'"
            )

    @pytest.mark.asyncio
    async def test_query_field_values_survive_encrypt_decrypt_roundtrip(self, repo, item_model):
        """query() returns records with all field values correctly decrypted."""
        item = item_model(name='RoundTripQuery', value=512)
        await repo.save(item)

        results = await repo.query(item_model)

        assert len(results) == 1
        assert results[0].name == 'RoundTripQuery', (
            f"Query result name must be 'RoundTripQuery', got '{results[0].name}'"
        )
        assert results[0].value == 512, (
            f"Query result value must be 512, got {results[0].value}"
        )


# ============================================================================
# TESTS: query_index()
# ============================================================================


@pytest.mark.issue_28
class TestQueryIndex:
    """query_index() must return raw SQLite rows without touching IPFS."""

    @pytest.mark.asyncio
    async def test_query_index_empty_before_any_save(self, repo, item_model):
        """query_index() returns [] when no records have been saved."""
        result = repo.query_index(item_model)

        assert result == [], (
            f"query_index() on empty repo must return [], got {result}"
        )

    @pytest.mark.asyncio
    async def test_query_index_returns_list_of_dicts(self, repo, item_model, sample_item):
        """query_index() returns a list of dicts (raw rows)."""
        await repo.save(sample_item)

        result = repo.query_index(item_model)

        assert isinstance(result, list), (
            f"query_index() must return list, got {type(result)}"
        )
        assert len(result) == 1
        assert isinstance(result[0], dict), (
            f"query_index() must return dicts, got {type(result[0])}"
        )

    @pytest.mark.asyncio
    async def test_query_index_row_contains_record_id(self, repo, item_model, sample_item):
        """query_index() rows contain '_record_id' matching the document _id."""
        await repo.save(sample_item)

        result = repo.query_index(item_model)

        assert '_record_id' in result[0], (
            f"query_index() rows must contain '_record_id', "
            f"got keys: {list(result[0].keys())}"
        )
        assert result[0]['_record_id'] == sample_item._id, (
            f"_record_id must be '{sample_item._id}', got '{result[0]['_record_id']}'"
        )

    @pytest.mark.asyncio
    async def test_query_index_does_not_call_ipfs_fetch(self, repo, item_model, sample_item, fake_ipfs):
        """query_index() never calls ipfs_client.fetch — it is a SQLite-only fast path."""
        await repo.save(sample_item)
        fetch_count_after_save = fake_ipfs.fetch_count

        repo.query_index(item_model)

        assert fake_ipfs.fetch_count == fetch_count_after_save, (
            f"query_index() must not call ipfs fetch, but fetch was called "
            f"{fake_ipfs.fetch_count - fetch_count_after_save} additional time(s)"
        )

    @pytest.mark.asyncio
    async def test_query_index_row_contains_tombstoned_column(self, repo, item_model, sample_item):
        """query_index() rows contain '_tombstoned' system column."""
        await repo.save(sample_item)

        result = repo.query_index(item_model)

        assert '_tombstoned' in result[0], (
            f"query_index() rows must contain '_tombstoned', "
            f"got keys: {list(result[0].keys())}"
        )
        assert result[0]['_tombstoned'] == 0, (
            f"Live record _tombstoned must be 0, got {result[0]['_tombstoned']}"
        )

    @pytest.mark.asyncio
    async def test_query_index_excludes_tombstoned_by_default(self, repo, item_model):
        """query_index() excludes tombstoned records by default."""
        item = item_model(name='ToTombstone', value=0)
        await repo.save(item)
        await repo.delete(item_model, item._id)

        result = repo.query_index(item_model)

        assert result == [], (
            f"query_index() must exclude tombstoned records by default, "
            f"got {len(result)} rows"
        )

    @pytest.mark.asyncio
    async def test_query_index_include_tombstoned_returns_them(self, repo, item_model):
        """query_index(include_tombstoned=True) includes tombstoned records."""
        item = item_model(name='TombstonedItem', value=0)
        await repo.save(item)
        await repo.delete(item_model, item._id)

        result = repo.query_index(item_model, include_tombstoned=True)

        assert len(result) == 1, (
            f"query_index(include_tombstoned=True) must return the tombstoned record, "
            f"got {len(result)} rows"
        )
        assert result[0]['_tombstoned'] == 1, (
            f"Tombstoned record must have _tombstoned=1, got {result[0]['_tombstoned']}"
        )


# ============================================================================
# TESTS: delete()
# ============================================================================


@pytest.mark.issue_28
class TestDelete:
    """delete(record_type, record_id) must publish a tombstone op and apply to index."""

    @pytest.mark.asyncio
    async def test_delete_returns_string_cid(self, repo, item_model, sample_item):
        """delete() returns a non-empty string CID for the tombstone operation."""
        await repo.save(sample_item)

        tombstone_cid = await repo.delete(item_model, sample_item._id)

        assert isinstance(tombstone_cid, str), (
            f"delete() must return str CID, got {type(tombstone_cid)}"
        )
        assert len(tombstone_cid) > 0, "delete() must return a non-empty CID"

    @pytest.mark.asyncio
    async def test_delete_publishes_tombstone_operation_record(self, repo, item_model, sample_item, fake_ipfs):
        """delete() publishes a tombstone OperationRecord to IPFS."""
        await repo.save(sample_item)
        count_before = len(fake_ipfs.published)

        await repo.delete(item_model, sample_item._id)

        assert len(fake_ipfs.published) == count_before + 1, (
            "delete() must publish exactly one tombstone operation to IPFS"
        )
        tombstone_op = fake_ipfs.published[-1]
        assert isinstance(tombstone_op, OperationRecord), (
            f"Tombstone must be OperationRecord, got {type(tombstone_op)}"
        )

    @pytest.mark.asyncio
    async def test_delete_operation_type_is_tombstone(self, repo, item_model, sample_item, fake_ipfs):
        """The operation published by delete() has op_type='tombstone'."""
        await repo.save(sample_item)
        await repo.delete(item_model, sample_item._id)

        tombstone_op = fake_ipfs.published[-1]
        assert tombstone_op.op_type == 'tombstone', (
            f"Tombstone operation must have op_type='tombstone', "
            f"got '{tombstone_op.op_type}'"
        )

    @pytest.mark.asyncio
    async def test_delete_tombstone_has_correct_record_id(self, repo, item_model, sample_item, fake_ipfs):
        """Tombstone operation references the correct record_id."""
        await repo.save(sample_item)
        await repo.delete(item_model, sample_item._id)

        tombstone_op = fake_ipfs.published[-1]
        assert tombstone_op.record_id == sample_item._id, (
            f"Tombstone record_id must be '{sample_item._id}', "
            f"got '{tombstone_op.record_id}'"
        )

    @pytest.mark.asyncio
    async def test_delete_excludes_record_from_query(self, repo, item_model):
        """After delete(), query() no longer returns the deleted record."""
        item = item_model(name='ToDelete', value=0)
        await repo.save(item)

        results_before = await repo.query(item_model)
        assert len(results_before) == 1

        await repo.delete(item_model, item._id)

        results_after = await repo.query(item_model)
        assert len(results_after) == 0, (
            f"After delete, query() must return [], got {len(results_after)} results"
        )

    @pytest.mark.asyncio
    async def test_delete_marks_record_tombstoned_in_index(self, repo, item_model, sample_item):
        """After delete(), query_index(include_tombstoned=True) shows _tombstoned=1."""
        await repo.save(sample_item)
        await repo.delete(item_model, sample_item._id)

        rows = repo.query_index(item_model, include_tombstoned=True)
        assert len(rows) == 1
        assert rows[0]['_tombstoned'] == 1, (
            f"After delete, _tombstoned must be 1, got {rows[0]['_tombstoned']}"
        )

    @pytest.mark.asyncio
    async def test_delete_does_not_affect_other_records(self, repo, item_model):
        """delete() only removes the targeted record; other records remain queryable."""
        item_a = item_model(name='KeepMe', value=1)
        item_b = item_model(name='DeleteMe', value=2)
        await repo.save(item_a)
        await repo.save(item_b)

        await repo.delete(item_model, item_b._id)

        results = await repo.query(item_model)
        assert len(results) == 1, (
            f"After deleting one of two records, query() must return 1, "
            f"got {len(results)}"
        )
        assert results[0]._id == item_a._id, (
            f"Remaining record must be item_a (id={item_a._id}), "
            f"got id={results[0]._id}"
        )

    @pytest.mark.asyncio
    async def test_delete_nonexistent_record_raises_error_with_id_in_message(
        self, repo, item_model
    ):
        """delete() with an unknown record_id raises an error naming that ID."""
        missing_id = 'no-such-record-deadbeef'
        with pytest.raises(Exception) as exc_info:
            await repo.delete(item_model, missing_id)

        assert missing_id in str(exc_info.value), (
            f"Error must reference missing record ID '{missing_id}', "
            f"got: {exc_info.value}"
        )


# ============================================================================
# TESTS: sync()
# ============================================================================


@pytest.mark.issue_28
class TestSync:
    """sync() must delegate to SyncManager.incremental_sync()."""

    @pytest.mark.asyncio
    async def test_sync_delegates_to_sync_manager_incremental_sync(
        self, repo_with_sync, mock_sync_manager
    ):
        """sync() calls sync_manager.incremental_sync() with record_type and head CID."""
        expected_result = SyncResult(
            ops_applied=0, new_head_cid='QmHead123', record_type='Item'
        )
        mock_sync_manager.incremental_sync = AsyncMock(return_value=expected_result)

        await repo_with_sync.sync(record_type='Item', current_head_cid='QmHead123')

        mock_sync_manager.incremental_sync.assert_called_once(), (
            "sync() must call sync_manager.incremental_sync() exactly once"
        )

    @pytest.mark.asyncio
    async def test_sync_passes_record_type_to_sync_manager(
        self, repo_with_sync, mock_sync_manager
    ):
        """sync() passes record_type to sync_manager.incremental_sync()."""
        mock_sync_manager.incremental_sync = AsyncMock(
            return_value=SyncResult(ops_applied=0, new_head_cid='Qm', record_type='Item')
        )

        await repo_with_sync.sync(record_type='Item', current_head_cid='QmHead')

        call_kwargs = mock_sync_manager.incremental_sync.call_args
        passed_record_type = (
            call_kwargs.kwargs.get('record_type')
            or (call_kwargs.args[0] if call_kwargs.args else None)
        )
        assert passed_record_type == 'Item', (
            f"sync() must pass record_type='Item' to incremental_sync, "
            f"got: {call_kwargs}"
        )

    @pytest.mark.asyncio
    async def test_sync_returns_sync_manager_result(
        self, repo_with_sync, mock_sync_manager
    ):
        """sync() returns exactly what sync_manager.incremental_sync() returns."""
        expected = SyncResult(ops_applied=5, new_head_cid='QmNew5', record_type='Item')
        mock_sync_manager.incremental_sync = AsyncMock(return_value=expected)

        result = await repo_with_sync.sync(record_type='Item', current_head_cid='QmNew5')

        assert result is expected, (
            f"sync() must return the SyncResult from SyncManager, "
            f"got {type(result)}"
        )

    @pytest.mark.asyncio
    async def test_sync_without_sync_manager_raises_descriptive_error(self, repo):
        """sync() without a configured sync_manager raises an informative error."""
        with pytest.raises(Exception) as exc_info:
            await repo.sync(record_type='Item', current_head_cid='QmHead')

        error_msg = str(exc_info.value).lower()
        assert 'sync' in error_msg or 'manager' in error_msg, (
            f"Error message should indicate the missing sync_manager, "
            f"got: {exc_info.value}"
        )


# ============================================================================
# TESTS: Full round-trip
# ============================================================================


@pytest.mark.issue_28
class TestFullRoundTrip:
    """End-to-end tests covering the full save/get/query/delete cycle."""

    @pytest.mark.asyncio
    async def test_save_then_get_recovers_identical_document(self, repo, item_model):
        """save() followed by get() returns a document with identical field values."""
        original = item_model(name='RoundTrip', value=42)
        await repo.save(original)

        retrieved = await repo.get(item_model, original._id)

        assert retrieved._id == original._id, (
            f"Round-trip _id must match: expected '{original._id}', "
            f"got '{retrieved._id}'"
        )
        assert retrieved.name == original.name, (
            f"Round-trip name must match: expected '{original.name}', "
            f"got '{retrieved.name}'"
        )
        assert retrieved.value == original.value, (
            f"Round-trip value must match: expected {original.value}, "
            f"got {retrieved.value}"
        )

    @pytest.mark.asyncio
    async def test_save_multiple_then_query_returns_all(self, repo, item_model):
        """Saving N records then calling query() returns all N."""
        items = [item_model(name=f'Multi{i}', value=i * 10) for i in range(4)]
        saved_ids = set()
        for item in items:
            await repo.save(item)
            saved_ids.add(item._id)

        results = await repo.query(item_model)

        assert len(results) == 4, (
            f"query() must return 4 results after 4 saves, got {len(results)}"
        )
        result_ids = {r._id for r in results}
        assert result_ids == saved_ids, (
            f"query() result IDs must match saved IDs.\n"
            f"  expected: {saved_ids}\n"
            f"  got:      {result_ids}"
        )

    @pytest.mark.asyncio
    async def test_query_index_and_query_return_same_count(self, repo, item_model):
        """query_index() and query() return the same number of live records."""
        for i in range(3):
            await repo.save(item_model(name=f'CountMe{i}', value=i))

        index_rows = repo.query_index(item_model)
        full_results = await repo.query(item_model)

        assert len(index_rows) == len(full_results), (
            f"query_index() ({len(index_rows)}) and query() ({len(full_results)}) "
            f"must return the same count for live records"
        )
        assert len(index_rows) == 3, (
            f"Both must return 3 live records, got {len(index_rows)}"
        )

    @pytest.mark.asyncio
    async def test_full_save_get_query_delete_lifecycle(self, repo, item_model):
        """Complete lifecycle: save → get → query → delete → query returns empty."""
        # Step 1: Save
        item = item_model(name='Lifecycle', value=100)
        cid = await repo.save(item)
        assert isinstance(cid, str) and len(cid) > 0, "save() must return a CID"

        # Step 2: Get
        retrieved = await repo.get(item_model, item._id)
        assert retrieved.name == 'Lifecycle', (
            f"get() name must be 'Lifecycle', got '{retrieved.name}'"
        )
        assert retrieved.value == 100, (
            f"get() value must be 100, got {retrieved.value}"
        )

        # Step 3: Query
        results = await repo.query(item_model)
        assert len(results) == 1, (
            f"query() must return 1 record before delete, got {len(results)}"
        )
        assert results[0]._id == item._id, (
            f"query() must return the saved item, got id={results[0]._id}"
        )

        # Step 4: Delete
        tombstone_cid = await repo.delete(item_model, item._id)
        assert isinstance(tombstone_cid, str) and len(tombstone_cid) > 0, (
            "delete() must return a CID for the tombstone"
        )

        # Step 5: Query after delete returns empty
        results_after = await repo.query(item_model)
        assert len(results_after) == 0, (
            f"After delete, query() must return [], got {len(results_after)} results"
        )

    @pytest.mark.asyncio
    async def test_get_all_individually_after_bulk_save(self, repo, item_model):
        """Save N records and retrieve each individually by ID with correct values."""
        items = [item_model(name=f'BulkItem{i}', value=i * 7) for i in range(5)]
        for item in items:
            await repo.save(item)

        for original in items:
            retrieved = await repo.get(item_model, original._id)
            assert retrieved.name == original.name, (
                f"get({original._id}) name must be '{original.name}', "
                f"got '{retrieved.name}'"
            )
            assert retrieved.value == original.value, (
                f"get({original._id}) value must be {original.value}, "
                f"got {retrieved.value}"
            )
