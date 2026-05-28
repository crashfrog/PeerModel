#!/usr/bin/env python

"""Tests for IndexDB.ensure_schema() implementation (Issue #19)."""

import pytest
import sqlite3
import tempfile
from pathlib import Path

import peermodel
from peermodel.peermodel import DocumentObj
from peermodel.index import IndexDB, SchemaMismatchError


@pytest.fixture
def peer():
    """Create test App instance."""
    return peermodel.App("test_ensure_schema")


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


class TestTableCreation:
    """Test CREATE TABLE IF NOT EXISTS functionality."""

    def test_ensure_schema_creates_table_when_not_exists(self, peer, index_db):
        """Test ensure_schema creates table when it doesn't exist."""
        @peer.model
        class NewModel:
            name: str
            age: int

        peer.indexed('NewModel', 'name')

        # Should not raise any exception
        model_class = DocumentObj.Meta._reg['NewModel']
        index_db.ensure_schema(model_class)

        # Verify table exists
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='NewModel'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 'NewModel'

    def test_ensure_schema_creates_system_columns(self, peer, index_db):
        """Test that system columns are created in the table."""
        @peer.model
        class SystemColModel:
            field1: str

        model_class = DocumentObj.Meta._reg['SystemColModel']
        index_db.ensure_schema(model_class)

        # Verify system columns exist
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(SystemColModel)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        # Check all system columns are present
        assert '_record_id' in columns
        assert '_op_id' in columns
        assert '_sequence' in columns
        assert '_timestamp' in columns
        assert '_head_cid' in columns
        assert '_tombstoned' in columns
        assert '_schema_version' in columns

    def test_ensure_schema_creates_model_fields(self, peer, index_db):
        """Test that model fields are created with correct types."""
        @peer.model
        class FieldModel:
            text_field: str
            int_field: int
            float_field: float
            bool_field: bool

        model_class = DocumentObj.Meta._reg['FieldModel']
        index_db.ensure_schema(model_class)

        # Verify fields exist with correct types
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(FieldModel)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert columns['text_field'] == 'TEXT'
        assert columns['int_field'] == 'INTEGER'
        assert columns['float_field'] == 'REAL'
        assert columns['bool_field'] == 'INTEGER'

    def test_ensure_schema_sets_primary_key(self, peer, index_db):
        """Test that _record_id is set as PRIMARY KEY."""
        @peer.model
        class PKModel:
            field1: str

        model_class = DocumentObj.Meta._reg['PKModel']
        index_db.ensure_schema(model_class)

        # Check primary key constraint
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(PKModel)")
        columns = cursor.fetchall()
        conn.close()

        # Find _record_id column and check if it's primary key (pk column = 1)
        record_id_col = [col for col in columns if col[1] == '_record_id'][0]
        assert record_id_col[5] == 1  # pk flag is at index 5


class TestIdempotency:
    """Test that ensure_schema is idempotent (can be called multiple times)."""

    def test_ensure_schema_idempotent_no_error(self, peer, index_db):
        """Test calling ensure_schema twice doesn't raise an error."""
        @peer.model
        class IdempotentModel:
            field: str

        model_class = DocumentObj.Meta._reg['IdempotentModel']

        # First call
        index_db.ensure_schema(model_class)

        # Second call should not raise any exception
        index_db.ensure_schema(model_class)

    def test_ensure_schema_idempotent_preserves_data(self, peer, index_db):
        """Test that calling ensure_schema twice doesn't drop existing data."""
        @peer.model
        class DataModel:
            value: str

        model_class = DocumentObj.Meta._reg['DataModel']
        index_db.ensure_schema(model_class)

        # Insert test data
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO DataModel (_record_id, _op_id, _sequence, _timestamp, "
            "_head_cid, _tombstoned, _schema_version, value) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ('test-id', 'op-1', 1, 123456, 'cid-1', 0, 1, 'test-value')
        )
        conn.commit()
        conn.close()

        # Call ensure_schema again
        index_db.ensure_schema(model_class)

        # Verify data still exists
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM DataModel WHERE _record_id = ?", ('test-id',))
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == 'test-value'

    def test_ensure_schema_idempotent_multiple_calls(self, peer, index_db):
        """Test calling ensure_schema many times works correctly."""
        @peer.model
        class MultiCallModel:
            field: int

        model_class = DocumentObj.Meta._reg['MultiCallModel']

        # Call ensure_schema 5 times
        for _ in range(5):
            index_db.ensure_schema(model_class)

        # Verify table still works
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO MultiCallModel (_record_id, _op_id, _sequence, "
            "_timestamp, _head_cid, _tombstoned, _schema_version, field) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ('id-1', 'op-1', 1, 123456, 'cid-1', 0, 1, 42)
        )
        conn.commit()
        cursor.execute("SELECT field FROM MultiCallModel")
        result = cursor.fetchone()
        conn.close()

        assert result[0] == 42


class TestSchemaVerification:
    """Test that ensure_schema verifies existing schema matches expected."""

    def test_ensure_schema_accepts_matching_schema(self, peer, index_db):
        """Test that ensure_schema passes when existing schema matches."""
        @peer.model
        class MatchingModel:
            name: str
            count: int

        model_class = DocumentObj.Meta._reg['MatchingModel']

        # Create schema
        index_db.ensure_schema(model_class)

        # Call again - should verify schema matches and not raise
        index_db.ensure_schema(model_class)

    def test_ensure_schema_raises_on_incompatible_type(self, peer, index_db, temp_db):
        """Test SchemaMismatchError raised when column type differs."""
        # Manually create a table with wrong type
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IncompatibleModel (
                _record_id TEXT PRIMARY KEY,
                _op_id TEXT,
                _sequence INTEGER,
                _timestamp INTEGER,
                _head_cid TEXT,
                _tombstoned INTEGER,
                _schema_version INTEGER,
                name INTEGER  -- Should be TEXT
            )
        """)
        conn.commit()
        conn.close()

        @peer.model
        class IncompatibleModel:
            name: str  # Expect TEXT, but table has INTEGER

        model_class = DocumentObj.Meta._reg['IncompatibleModel']

        # Should raise SchemaMismatchError
        with pytest.raises(SchemaMismatchError) as exc_info:
            index_db.ensure_schema(model_class)

        assert 'name' in str(exc_info.value).lower()

    def test_ensure_schema_raises_on_missing_column(self, peer, index_db, temp_db):
        """Test SchemaMismatchError raised when expected column is missing."""
        # Manually create a table missing a column
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE MissingColumnModel (
                _record_id TEXT PRIMARY KEY,
                _op_id TEXT,
                _sequence INTEGER,
                _timestamp INTEGER,
                _head_cid TEXT,
                _tombstoned INTEGER,
                _schema_version INTEGER
                -- Missing 'required_field'
            )
        """)
        conn.commit()
        conn.close()

        @peer.model
        class MissingColumnModel:
            required_field: str

        model_class = DocumentObj.Meta._reg['MissingColumnModel']

        # Should raise SchemaMismatchError
        with pytest.raises(SchemaMismatchError) as exc_info:
            index_db.ensure_schema(model_class)

        assert 'required_field' in str(exc_info.value).lower()

    def test_ensure_schema_raises_on_missing_system_column(self, peer, index_db, temp_db):
        """Test SchemaMismatchError raised when system column is missing."""
        # Manually create a table missing a system column
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE MissingSystemCol (
                _record_id TEXT PRIMARY KEY,
                _op_id TEXT,
                _sequence INTEGER,
                _timestamp INTEGER,
                _head_cid TEXT,
                -- Missing _tombstoned
                _schema_version INTEGER,
                field1 TEXT
            )
        """)
        conn.commit()
        conn.close()

        @peer.model
        class MissingSystemCol:
            field1: str

        model_class = DocumentObj.Meta._reg['MissingSystemCol']

        # Should raise SchemaMismatchError
        with pytest.raises(SchemaMismatchError) as exc_info:
            index_db.ensure_schema(model_class)

        assert '_tombstoned' in str(exc_info.value).lower()


class TestIndexCreation:
    """Test that indexes are created correctly on @indexed fields."""

    def test_ensure_schema_creates_index_on_indexed_field(self, peer, index_db):
        """Test that CREATE INDEX is executed for @indexed fields."""
        @peer.model
        class IndexedFieldModel:
            searchable: str
            not_indexed: str

        peer.indexed('IndexedFieldModel', 'searchable')

        model_class = DocumentObj.Meta._reg['IndexedFieldModel']
        index_db.ensure_schema(model_class)

        # Check that index exists for searchable field
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='IndexedFieldModel'"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()

        # Should have an index on searchable field
        searchable_indexes = [idx for idx in indexes if 'searchable' in idx]
        assert len(searchable_indexes) > 0

    def test_ensure_schema_creates_multiple_indexes(self, peer, index_db):
        """Test that multiple @indexed fields get separate indexes."""
        @peer.model
        class MultiIndexModel:
            field1: str
            field2: int
            field3: str

        peer.indexed('MultiIndexModel', 'field1')
        peer.indexed('MultiIndexModel', 'field2')

        model_class = DocumentObj.Meta._reg['MultiIndexModel']
        index_db.ensure_schema(model_class)

        # Check that both indexes exist
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='MultiIndexModel'"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()

        field1_indexes = [idx for idx in indexes if 'field1' in idx]
        field2_indexes = [idx for idx in indexes if 'field2' in idx]
        field3_indexes = [idx for idx in indexes if 'field3' in idx]

        assert len(field1_indexes) > 0
        assert len(field2_indexes) > 0
        assert len(field3_indexes) == 0  # field3 not indexed

    def test_ensure_schema_indexes_are_idempotent(self, peer, index_db):
        """Test that calling ensure_schema twice doesn't duplicate indexes."""
        @peer.model
        class IdempotentIndexModel:
            indexed_field: str

        peer.indexed('IdempotentIndexModel', 'indexed_field')

        model_class = DocumentObj.Meta._reg['IdempotentIndexModel']

        # Create schema twice
        index_db.ensure_schema(model_class)
        index_db.ensure_schema(model_class)

        # Check index count (should not have duplicates)
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='index' "
            "AND tbl_name='IdempotentIndexModel' AND name LIKE '%indexed_field%'"
        )
        count = cursor.fetchone()[0]
        conn.close()

        # Should have exactly one index (CREATE INDEX IF NOT EXISTS)
        assert count == 1

    def test_ensure_schema_creates_tombstoned_index(self, peer, index_db):
        """Test that an index is created on _tombstoned for filtering."""
        @peer.model
        class TombstoneIndexModel:
            field: str

        model_class = DocumentObj.Meta._reg['TombstoneIndexModel']
        index_db.ensure_schema(model_class)

        # Check for _tombstoned index
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='TombstoneIndexModel'"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()

        # Should have an index on _tombstoned
        tombstoned_indexes = [idx for idx in indexes if 'tombstoned' in idx.lower()]
        assert len(tombstoned_indexes) > 0


class TestNodeStateTable:
    """Test that _node_state table is created."""

    def test_ensure_schema_creates_node_state_table(self, peer, index_db):
        """Test that _node_state table is created if not exists."""
        @peer.model
        class AnyModel:
            field: str

        model_class = DocumentObj.Meta._reg['AnyModel']
        index_db.ensure_schema(model_class)

        # Check that _node_state table exists
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_node_state'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == '_node_state'

    def test_node_state_table_has_correct_columns(self, peer, index_db):
        """Test that _node_state table has required columns."""
        @peer.model
        class StateTestModel:
            field: str

        model_class = DocumentObj.Meta._reg['StateTestModel']
        index_db.ensure_schema(model_class)

        # Check _node_state columns
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(_node_state)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        # Expected columns from NodeState dataclass
        expected_columns = {
            'cohort_id',
            'record_type',
            'last_synced_head_cid',
            'last_synced_sequence',
            'snapshot_cid',
            'snapshot_sequence',
            'index_status',
            'last_sync_at'
        }

        assert expected_columns.issubset(columns)


class TestComplexScenarios:
    """Test complex scenarios with multiple models and schema changes."""

    def test_ensure_schema_multiple_models_separate_tables(self, peer, index_db):
        """Test that multiple models create separate tables in same database."""
        @peer.model
        class ModelA:
            field_a: str

        @peer.model
        class ModelB:
            field_b: int

        model_a = DocumentObj.Meta._reg['ModelA']
        model_b = DocumentObj.Meta._reg['ModelB']

        index_db.ensure_schema(model_a)
        index_db.ensure_schema(model_b)

        # Check both tables exist
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('ModelA', 'ModelB')"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert 'ModelA' in tables
        assert 'ModelB' in tables

    def test_ensure_schema_with_all_supported_types(self, peer, index_db):
        """Test model with all supported Python types."""
        @peer.model
        class AllTypesModel:
            str_field: str
            int_field: int
            float_field: float
            bool_field: bool
            dict_field: dict
            list_field: list
            bytes_field: bytes

        model_class = DocumentObj.Meta._reg['AllTypesModel']
        index_db.ensure_schema(model_class)

        # Verify all columns exist with correct types
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(AllTypesModel)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert columns['str_field'] == 'TEXT'
        assert columns['int_field'] == 'INTEGER'
        assert columns['float_field'] == 'REAL'
        assert columns['bool_field'] == 'INTEGER'
        assert columns['dict_field'] == 'BLOB'
        assert columns['list_field'] == 'BLOB'
        assert columns['bytes_field'] == 'BLOB'

    def test_ensure_schema_empty_model(self, peer, index_db):
        """Test model with no user fields (only system columns)."""
        @peer.model
        class EmptyModel:
            pass

        model_class = DocumentObj.Meta._reg['EmptyModel']
        index_db.ensure_schema(model_class)

        # Should create table with just system columns
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(EmptyModel)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        # Should have all system columns
        assert '_record_id' in columns
        assert '_op_id' in columns
        assert '_sequence' in columns


class TestErrorConditions:
    """Test error conditions and edge cases."""

    def test_ensure_schema_with_nonexistent_indexed_field(self, peer, index_db):
        """Test that indexed field must exist in model."""
        @peer.model
        class ErrorModel:
            real_field: str

        # This should have raised an error at decoration time
        with pytest.raises((ValueError, KeyError, AttributeError)):
            peer.indexed('ErrorModel', 'nonexistent_field')

    def test_ensure_schema_database_path_must_exist(self, peer):
        """Test that IndexDB raises error if database directory doesn't exist."""
        nonexistent_path = Path("/nonexistent/directory/db.sqlite")

        with pytest.raises((FileNotFoundError, OSError)):
            index_db = IndexDB(nonexistent_path)

            @peer.model
            class PathModel:
                field: str

            model_class = DocumentObj.Meta._reg['PathModel']
            index_db.ensure_schema(model_class)

    def test_ensure_schema_with_type_annotation_variations(self, peer, index_db):
        """Test that typing hints like List[str] work correctly."""
        from typing import List, Dict

        @peer.model
        class TypingModel:
            string_list: List[str]
            metadata_dict: Dict[str, int]

        model_class = DocumentObj.Meta._reg['TypingModel']
        index_db.ensure_schema(model_class)

        # Should map to BLOB for complex types
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(TypingModel)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert columns['string_list'] == 'BLOB'
        assert columns['metadata_dict'] == 'BLOB'


class TestIndexDBIntegration:
    """Integration tests with actual IndexDB class."""

    def test_index_db_initialization(self, temp_db):
        """Test that IndexDB can be initialized with a path."""
        index_db = IndexDB(temp_db)
        assert index_db.db_path == temp_db

    def test_index_db_connection_works(self, index_db):
        """Test that IndexDB can establish SQLite connections."""
        # Should be able to connect
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        conn.close()

        assert result[0] == 1

    def test_schema_persists_across_indexdb_instances(self, peer, temp_db):
        """Test that schema persists when creating new IndexDB instances."""
        @peer.model
        class PersistModel:
            field: str

        model_class = DocumentObj.Meta._reg['PersistModel']

        # Create schema with first instance
        index_db1 = IndexDB(temp_db)
        index_db1.ensure_schema(model_class)

        # Create second instance and verify schema exists
        index_db2 = IndexDB(temp_db)
        index_db2.ensure_schema(model_class)  # Should not raise

        # Verify table exists
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='PersistModel'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
