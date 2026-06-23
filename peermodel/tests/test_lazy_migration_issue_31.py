#!/usr/bin/env python

"""Acceptance tests for lazy migration on read (Issue #31).

Tests cover CohortRepository.get() behavior when reading a record whose
stored schema_version differs from the current package version:
- Returns a fully migrated DocumentObj instance
- Leaves the original OperationRecord in the log unchanged
- Skips migration when versions already match

API under test:
    from peermodel.repository import CohortRepository

    repo = CohortRepository(
        ipfs_client=client,       # object with .fetch(record_id) -> OperationRecord
        package_name='mypackage',  # used by load_engine() to find MIGRATIONS
        current_version='2.0.0'    # target schema version for migrations
    )
    doc = repo.get(record_type=MyModel, record_id='some-uuid')
    # -> DocumentObj subclass instance, fields migrated from stored schema
"""

import pytest
import copy
from datetime import datetime
from unittest.mock import patch

import peermodel
from peermodel.peermodel import DocumentObj, InMemoryDocumentDatabase
from peermodel.operations import OperationRecord
from peermodel.migrations import MigrationEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_op(
    record_id='rec-1',
    schema_version='1.0.0',
    payload=None,
    record_type='V2Model',
    op_id='op-1',
    sequence_number=1,
):
    """Build a minimal OperationRecord for testing."""
    if payload is None:
        payload = {'name': 'Alice', 'old_field': 'legacy_value'}
    return OperationRecord(
        op_id=op_id,
        op_type='insert',
        cohort_id='test-cohort',
        record_type=record_type,
        record_id=record_id,
        sequence_number=sequence_number,
        payload=payload,
        previous_head_cid=None,
        timestamp=datetime.utcnow().isoformat() + 'Z',
        schema_version=schema_version,
        signature=b'test_sig',
        signing_algorithm='ed25519',
    )


class MockIPFSClient:
    """Synchronous in-memory IPFS mock: record_id → OperationRecord."""

    def __init__(self, records: dict):
        self._records = records

    def fetch(self, record_id: str) -> OperationRecord:
        return self._records[record_id]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def peer():
    """Create a test App instance."""
    return peermodel.App("test_lazy_migration_31")


@pytest.fixture
def v2_model(peer):
    """Current (v2) model: 'old_field' renamed to 'new_field'."""
    @peer.model
    class V2Model:
        name: str
        new_field: str

    return DocumentObj.Meta._reg['V2Model']


@pytest.fixture
def migration_engine():
    """MigrationEngine that renames old_field → new_field between 1.0.0 and 2.0.0."""
    def migrate_v1_to_v2(record_type, record_dict):
        result = dict(record_dict)
        if 'old_field' in result:
            result['new_field'] = result.pop('old_field')
        return result

    return MigrationEngine({("1.0.0", "2.0.0"): migrate_v1_to_v2})


@pytest.fixture
def v1_operation(v2_model):
    """OperationRecord written under schema v1.0.0 with old_field in payload."""
    return _make_op(
        record_id='rec-v1',
        schema_version='1.0.0',
        payload={'name': 'Alice', 'old_field': 'legacy_value'},
        record_type='V2Model',
    )


@pytest.fixture
def v2_operation(v2_model):
    """OperationRecord written under schema v2.0.0 with new_field in payload."""
    return _make_op(
        record_id='rec-v2',
        schema_version='2.0.0',
        payload={'name': 'Bob', 'new_field': 'current_value'},
        record_type='V2Model',
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.issue_31
class TestGetReturnType:
    """CohortRepository.get() always returns a DocumentObj subclass."""

    def test_get_returns_record_type_instance(
        self, peer, v2_model, migration_engine, v2_operation
    ):
        """get() returns an instance of the requested record_type.

        Acceptance: Return fully migrated instance.
        """
        from peermodel.repository import CohortRepository

        client = MockIPFSClient({'rec-v2': v2_operation})

        with patch('peermodel.migrations.load_engine', return_value=migration_engine):
            repo = CohortRepository(
                ipfs_client=client,
                package_name='test_package',
                current_version='2.0.0',
            )
            doc = repo.get(v2_model, 'rec-v2')

        assert isinstance(doc, v2_model), (
            f"get() must return a {v2_model.__name__} instance, got {type(doc)}"
        )

    def test_get_returns_document_obj_subclass(
        self, peer, v2_model, migration_engine, v2_operation
    ):
        """get() returns a DocumentObj subclass (not a raw dict).

        Acceptance: Return fully migrated instance.
        """
        from peermodel.repository import CohortRepository

        client = MockIPFSClient({'rec-v2': v2_operation})

        with patch('peermodel.migrations.load_engine', return_value=migration_engine):
            repo = CohortRepository(
                ipfs_client=client,
                package_name='test_package',
                current_version='2.0.0',
            )
            doc = repo.get(v2_model, 'rec-v2')

        assert isinstance(doc, DocumentObj), (
            f"get() must return a DocumentObj subclass, got {type(doc)}"
        )


@pytest.mark.issue_31
class TestVersionMatchSkipsMigration:
    """When stored schema_version == current_version, no migration is applied."""

    def test_get_version_match_returns_doc_with_correct_fields(
        self, peer, v2_model, migration_engine, v2_operation
    ):
        """get() on a current-version record returns doc with payload fields intact.

        Acceptance: Detect version mismatch in get() (inverse: no mismatch → pass through).
        """
        from peermodel.repository import CohortRepository

        client = MockIPFSClient({'rec-v2': v2_operation})

        with patch('peermodel.migrations.load_engine', return_value=migration_engine):
            repo = CohortRepository(
                ipfs_client=client,
                package_name='test_package',
                current_version='2.0.0',
            )
            doc = repo.get(v2_model, 'rec-v2')

        # Payload was {'name': 'Bob', 'new_field': 'current_value'}
        assert doc.name == 'Bob', (
            f"name should be 'Bob', got {doc.name!r}"
        )
        assert doc.new_field == 'current_value', (
            f"new_field should be 'current_value', got {doc.new_field!r}"
        )

    def test_get_version_match_does_not_call_migration(
        self, peer, v2_model, migration_engine, v2_operation
    ):
        """get() on a current-version record never invokes the migration engine.

        Acceptance: Detect version mismatch in get().
        """
        from peermodel.repository import CohortRepository

        migration_called = []

        def tracking_migrate(record_type, record_dict):
            migration_called.append(True)
            return record_dict

        tracking_engine = MigrationEngine({("2.0.0", "2.1.0"): tracking_migrate})

        client = MockIPFSClient({'rec-v2': v2_operation})

        with patch('peermodel.migrations.load_engine', return_value=tracking_engine):
            repo = CohortRepository(
                ipfs_client=client,
                package_name='test_package',
                current_version='2.0.0',
            )
            repo.get(v2_model, 'rec-v2')

        assert migration_called == [], (
            "Migration must NOT be applied when schema_version matches current_version"
        )


@pytest.mark.issue_31
class TestVersionMismatchAppliesMigration:
    """When stored schema_version != current_version, transforms are applied on read."""

    def test_get_v1_record_returns_migrated_new_field(
        self, peer, v2_model, migration_engine, v1_operation
    ):
        """get() on a v1.0.0 record applies the 1.0.0→2.0.0 transform.

        Stored payload has old_field; migrated payload has new_field.

        Acceptance: Apply migration on read; return fully migrated instance.
        """
        from peermodel.repository import CohortRepository

        client = MockIPFSClient({'rec-v1': v1_operation})

        with patch('peermodel.migrations.load_engine', return_value=migration_engine):
            repo = CohortRepository(
                ipfs_client=client,
                package_name='test_package',
                current_version='2.0.0',
            )
            doc = repo.get(v2_model, 'rec-v1')

        assert doc.new_field == 'legacy_value', (
            f"new_field should be 'legacy_value' (migrated from old_field), "
            f"got {doc.new_field!r}"
        )

    def test_get_v1_record_migrated_name_preserved(
        self, peer, v2_model, migration_engine, v1_operation
    ):
        """Migration preserves unchanged fields.

        Acceptance: Return fully migrated instance.
        """
        from peermodel.repository import CohortRepository

        client = MockIPFSClient({'rec-v1': v1_operation})

        with patch('peermodel.migrations.load_engine', return_value=migration_engine):
            repo = CohortRepository(
                ipfs_client=client,
                package_name='test_package',
                current_version='2.0.0',
            )
            doc = repo.get(v2_model, 'rec-v1')

        assert doc.name == 'Alice', (
            f"Unchanged field 'name' should be 'Alice', got {doc.name!r}"
        )

    def test_get_v1_record_migrated_doc_has_correct_record_id(
        self, peer, v2_model, migration_engine, v1_operation
    ):
        """Migrated doc retains the original record_id as _id.

        Acceptance: Return fully migrated instance.
        """
        from peermodel.repository import CohortRepository

        client = MockIPFSClient({'rec-v1': v1_operation})

        with patch('peermodel.migrations.load_engine', return_value=migration_engine):
            repo = CohortRepository(
                ipfs_client=client,
                package_name='test_package',
                current_version='2.0.0',
            )
            doc = repo.get(v2_model, 'rec-v1')

        assert doc._id == 'rec-v1', (
            f"Migrated doc._id should be the original record_id 'rec-v1', "
            f"got {doc._id!r}"
        )


@pytest.mark.issue_31
class TestOriginalRecordUnchanged:
    """The OperationRecord in the log must not be mutated by get()."""

    def test_get_does_not_mutate_operation_schema_version(
        self, peer, v2_model, migration_engine, v1_operation
    ):
        """Original OperationRecord.schema_version is unchanged after get().

        Acceptance: Original record in log unchanged.
        """
        from peermodel.repository import CohortRepository

        original_schema_version = v1_operation.schema_version
        client = MockIPFSClient({'rec-v1': v1_operation})

        with patch('peermodel.migrations.load_engine', return_value=migration_engine):
            repo = CohortRepository(
                ipfs_client=client,
                package_name='test_package',
                current_version='2.0.0',
            )
            repo.get(v2_model, 'rec-v1')

        assert v1_operation.schema_version == original_schema_version, (
            f"OperationRecord.schema_version must not be mutated: "
            f"expected {original_schema_version!r}, "
            f"got {v1_operation.schema_version!r}"
        )

    def test_get_does_not_mutate_operation_payload(
        self, peer, v2_model, migration_engine, v1_operation
    ):
        """Original OperationRecord.payload is unchanged after get().

        Acceptance: Original record in log unchanged.
        """
        from peermodel.repository import CohortRepository

        original_payload = copy.deepcopy(v1_operation.payload)
        client = MockIPFSClient({'rec-v1': v1_operation})

        with patch('peermodel.migrations.load_engine', return_value=migration_engine):
            repo = CohortRepository(
                ipfs_client=client,
                package_name='test_package',
                current_version='2.0.0',
            )
            repo.get(v2_model, 'rec-v1')

        assert v1_operation.payload == original_payload, (
            f"OperationRecord.payload must not be mutated by migration: "
            f"expected {original_payload!r}, got {v1_operation.payload!r}"
        )

    def test_get_v1_operation_still_has_old_field_after_migration(
        self, peer, v2_model, migration_engine, v1_operation
    ):
        """Stored payload keeps old_field key; only the returned doc uses new_field.

        Acceptance: Original record in log unchanged.
        """
        from peermodel.repository import CohortRepository

        client = MockIPFSClient({'rec-v1': v1_operation})

        with patch('peermodel.migrations.load_engine', return_value=migration_engine):
            repo = CohortRepository(
                ipfs_client=client,
                package_name='test_package',
                current_version='2.0.0',
            )
            repo.get(v2_model, 'rec-v1')

        assert 'old_field' in v1_operation.payload, (
            "OperationRecord.payload must still contain 'old_field' after get() — "
            "the log is immutable"
        )
        assert 'new_field' not in v1_operation.payload, (
            "OperationRecord.payload must NOT have 'new_field' added — "
            "the log is immutable"
        )
