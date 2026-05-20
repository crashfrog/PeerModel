#!/usr/bin/env python

"""Tests for SQLite schema generation from @indexed decorators (Issue #18)."""

import pytest
from typing import List, Dict

import peermodel
from peermodel.peermodel import DocumentObj


@pytest.fixture
def peer():
    """Create test App instance."""
    return peermodel.App("test_indexed")


class TestIndexedMetadataParsing:
    """Test parsing @indexed decorator metadata from model classes."""

    def test_indexed_field_metadata_stored_on_class(self, peer):
        """Test @indexed decorator stores field metadata on model class."""
        @peer.model
        class Sample:
            sample_id: str
            collection_date: str
            pathogen: str

        # Simulate the indexed decorator storing metadata
        # The decorator should set _peermodel_indexed_fields attribute
        peer.indexed('Sample', 'collection_date')
        peer.indexed('Sample', 'pathogen')

        # Retrieve the model class from type registry
        model_class = DocumentObj.Meta._reg['Sample']

        # Assert that metadata is stored
        assert hasattr(model_class, '_peermodel_indexed_fields')
        assert 'collection_date' in model_class._peermodel_indexed_fields
        assert 'pathogen' in model_class._peermodel_indexed_fields

    def test_indexed_metadata_empty_when_no_decorator(self, peer):
        """Test that models without @indexed have empty or absent metadata."""
        @peer.model
        class UnindexedModel:
            field1: str
            field2: int

        model_class = DocumentObj.Meta._reg['UnindexedModel']

        # Should either not have the attribute or have an empty collection
        if hasattr(model_class, '_peermodel_indexed_fields'):
            assert len(model_class._peermodel_indexed_fields) == 0

    def test_indexed_metadata_multiple_fields(self, peer):
        """Test multiple fields can be marked as indexed."""
        @peer.model
        class MultiIndexed:
            id: str
            name: str
            age: int
            created_at: str

        peer.indexed('MultiIndexed', 'id')
        peer.indexed('MultiIndexed', 'name')
        peer.indexed('MultiIndexed', 'age')

        model_class = DocumentObj.Meta._reg['MultiIndexed']
        assert hasattr(model_class, '_peermodel_indexed_fields')
        assert len(model_class._peermodel_indexed_fields) >= 3


class TestPythonToSQLiteTypeMapping:
    """Test Python type to SQLite type mapping."""

    def test_str_maps_to_text(self, peer):
        """Test that str type maps to TEXT in SQLite."""
        @peer.model
        class StrModel:
            text_field: str

        peer.indexed('StrModel', 'text_field')

        # There should be a function to get SQLite type from Python type
        # This is the contract the implementation must fulfill
        # This module doesn't exist yet
        from peermodel.index import get_sqlite_type

        assert get_sqlite_type(str) == 'TEXT'

    def test_int_maps_to_integer(self, peer):
        """Test that int type maps to INTEGER in SQLite."""
        @peer.model
        class IntModel:
            count: int

        peer.indexed('IntModel', 'count')

        from peermodel.index import get_sqlite_type

        assert get_sqlite_type(int) == 'INTEGER'

    def test_float_maps_to_real(self, peer):
        """Test that float type maps to REAL in SQLite."""
        @peer.model
        class FloatModel:
            score: float

        peer.indexed('FloatModel', 'score')

        from peermodel.index import get_sqlite_type

        assert get_sqlite_type(float) == 'REAL'

    def test_bool_maps_to_integer(self, peer):
        """Test that bool type maps to INTEGER in SQLite (0/1)."""
        @peer.model
        class BoolModel:
            is_active: bool

        peer.indexed('BoolModel', 'is_active')

        from peermodel.index import get_sqlite_type

        assert get_sqlite_type(bool) == 'INTEGER'

    def test_dict_maps_to_blob(self, peer):
        """Test that dict type maps to BLOB in SQLite (CBOR-encoded)."""
        @peer.model
        class DictModel:
            metadata: dict

        peer.indexed('DictModel', 'metadata')

        from peermodel.index import get_sqlite_type

        assert get_sqlite_type(dict) == 'BLOB'

    def test_list_maps_to_blob(self, peer):
        """Test that list type maps to BLOB in SQLite (CBOR-encoded)."""
        @peer.model
        class ListModel:
            tags: list

        peer.indexed('ListModel', 'tags')

        from peermodel.index import get_sqlite_type

        assert get_sqlite_type(list) == 'BLOB'

    def test_bytes_maps_to_blob(self, peer):
        """Test that bytes type maps to BLOB in SQLite."""
        @peer.model
        class BytesModel:
            binary_data: bytes

        peer.indexed('BytesModel', 'binary_data')

        from peermodel.index import get_sqlite_type

        assert get_sqlite_type(bytes) == 'BLOB'

    def test_type_mapping_with_typing_hints(self, peer):
        """Test type mapping works with typing hints List[str], etc."""
        @peer.model
        class TypingModel:
            string_list: List[str]
            metadata_dict: Dict[str, int]

        peer.indexed('TypingModel', 'string_list')
        peer.indexed('TypingModel', 'metadata_dict')

        from peermodel.index import get_sqlite_type

        # List[str] should still map to BLOB (CBOR)
        assert get_sqlite_type(List[str]) == 'BLOB'
        # Dict[str, int] should map to BLOB (CBOR)
        assert get_sqlite_type(Dict[str, int]) == 'BLOB'


class TestSystemColumns:
    """Test that system columns are defined correctly."""

    def test_system_columns_defined(self):
        """Test that all required system columns are defined."""
        # This constant doesn't exist yet
        from peermodel.index import SYSTEM_COLUMNS

        expected_columns = [
            '_record_id',
            '_op_id',
            '_sequence',
            '_timestamp',
            '_head_cid',
            '_tombstoned',
            '_schema_version'
        ]

        for col in expected_columns:
            assert col in SYSTEM_COLUMNS

    def test_system_column_types(self):
        """Test that system columns have correct SQLite types."""
        from peermodel.index import SYSTEM_COLUMNS

        # Define expected types for system columns
        expected_types = {
            '_record_id': 'TEXT',      # UUID as text
            '_op_id': 'TEXT',          # Operation ID
            '_sequence': 'INTEGER',    # Sequence number
            '_timestamp': 'INTEGER',   # Unix timestamp
            '_head_cid': 'TEXT',       # IPFS CID
            '_tombstoned': 'INTEGER',  # Boolean 0/1
            '_schema_version': 'INTEGER'  # Schema version number
        }

        for col_name, expected_type in expected_types.items():
            assert SYSTEM_COLUMNS[col_name] == expected_type

    def test_record_id_is_primary_key(self):
        """Test that _record_id is marked as primary key."""
        from peermodel.index import SYSTEM_COLUMNS

        # System columns should indicate which is primary key
        # This could be a separate attribute or part of the column definition
        assert '_record_id' in SYSTEM_COLUMNS


class TestDDLGeneration:
    """Test DDL (CREATE TABLE) generation from model classes."""

    def test_generate_create_table_simple(self, peer):
        """Test generating CREATE TABLE DDL for a simple model."""
        @peer.model
        class SimpleModel:
            name: str
            age: int

        peer.indexed('SimpleModel', 'name')

        from peermodel.index import generate_ddl

        ddl = generate_ddl(DocumentObj.Meta._reg['SimpleModel'])

        # Should contain CREATE TABLE statement
        assert 'CREATE TABLE' in ddl.upper()
        assert 'SimpleModel' in ddl

        # Should contain system columns
        assert '_record_id' in ddl
        assert '_op_id' in ddl
        assert '_sequence' in ddl
        assert '_timestamp' in ddl
        assert '_head_cid' in ddl
        assert '_tombstoned' in ddl
        assert '_schema_version' in ddl

        # Should contain model fields
        assert 'name' in ddl
        assert 'age' in ddl

    def test_generate_create_table_with_types(self, peer):
        """Test that generated DDL includes correct SQLite types."""
        @peer.model
        class TypedModel:
            text_field: str
            int_field: int
            float_field: float
            bool_field: bool

        peer.indexed('TypedModel', 'text_field')

        from peermodel.index import generate_ddl

        ddl = generate_ddl(DocumentObj.Meta._reg['TypedModel'])

        # Should map types correctly
        assert 'text_field TEXT' in ddl
        assert 'int_field INTEGER' in ddl
        assert 'float_field REAL' in ddl
        assert 'bool_field INTEGER' in ddl

    def test_generate_create_table_with_primary_key(self, peer):
        """Test that _record_id is marked as PRIMARY KEY."""
        @peer.model
        class PKModel:
            field1: str

        from peermodel.index import generate_ddl

        ddl = generate_ddl(DocumentObj.Meta._reg['PKModel'])

        # _record_id should be primary key
        assert 'PRIMARY KEY' in ddl.upper()
        # PRIMARY KEY should be on _record_id
        assert '_record_id' in ddl and 'PRIMARY KEY' in ddl.upper()

    def test_generate_create_table_if_not_exists(self, peer):
        """Test that DDL includes IF NOT EXISTS clause."""
        @peer.model
        class SafeModel:
            field1: str

        from peermodel.index import generate_ddl

        ddl = generate_ddl(DocumentObj.Meta._reg['SafeModel'])

        # Should be idempotent with IF NOT EXISTS
        assert 'IF NOT EXISTS' in ddl.upper()

    def test_generate_create_index_for_indexed_fields(self, peer):
        """Test that CREATE INDEX is generated for @indexed fields."""
        @peer.model
        class IndexedModel:
            searchable: str
            sortable: int
            regular: str

        peer.indexed('IndexedModel', 'searchable')
        peer.indexed('IndexedModel', 'sortable')

        from peermodel.index import generate_ddl

        ddl = generate_ddl(DocumentObj.Meta._reg['IndexedModel'])

        # Should include CREATE INDEX for indexed fields
        assert 'CREATE INDEX' in ddl.upper()
        assert 'searchable' in ddl
        assert 'sortable' in ddl

    def test_generate_index_only_for_marked_fields(self, peer):
        """Test CREATE INDEX is NOT generated for non-indexed fields."""
        @peer.model
        class PartialIndexModel:
            indexed_field: str
            regular_field: str

        peer.indexed('PartialIndexModel', 'indexed_field')

        from peermodel.index import generate_ddl

        ddl = generate_ddl(DocumentObj.Meta._reg['PartialIndexModel'])

        # Should have index for indexed_field
        assert 'indexed_field' in ddl

        # regular_field should be in table but not have CREATE INDEX
        # (it should appear in column definition but not in CREATE INDEX)
        index_statements = [
            line for line in ddl.split('\n')
            if 'CREATE INDEX' in line.upper()
        ]
        indexed_field_count = sum(
            'indexed_field' in stmt for stmt in index_statements
        )
        regular_field_count = sum(
            'regular_field' in stmt for stmt in index_statements
        )

        assert indexed_field_count > 0
        assert regular_field_count == 0


class TestComplexScenarios:
    """Test complex scenarios with multiple models and fields."""

    def test_multiple_models_generate_separate_tables(self, peer):
        """Test multiple models generate separate CREATE TABLE statements."""
        @peer.model
        class ModelA:
            field_a: str

        @peer.model
        class ModelB:
            field_b: int

        peer.indexed('ModelA', 'field_a')
        peer.indexed('ModelB', 'field_b')

        from peermodel.index import generate_ddl

        ddl_a = generate_ddl(DocumentObj.Meta._reg['ModelA'])
        ddl_b = generate_ddl(DocumentObj.Meta._reg['ModelB'])

        # Each should have its own table
        assert 'ModelA' in ddl_a
        assert 'ModelB' in ddl_b

        # Should not have cross-contamination
        assert 'ModelB' not in ddl_a
        assert 'ModelA' not in ddl_b

    def test_model_with_all_supported_types(self, peer):
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

        peer.indexed('AllTypesModel', 'str_field')
        peer.indexed('AllTypesModel', 'int_field')

        from peermodel.index import generate_ddl

        ddl = generate_ddl(DocumentObj.Meta._reg['AllTypesModel'])

        # All fields should be present
        assert 'str_field' in ddl
        assert 'int_field' in ddl
        assert 'float_field' in ddl
        assert 'bool_field' in ddl
        assert 'dict_field' in ddl
        assert 'list_field' in ddl
        assert 'bytes_field' in ddl

        # Types should be correct
        assert 'TEXT' in ddl  # str_field
        assert 'INTEGER' in ddl  # int_field, bool_field, system columns
        assert 'REAL' in ddl  # float_field
        assert 'BLOB' in ddl  # dict_field, list_field, bytes_field

    def test_indexed_decorator_api_format(self, peer):
        """Test the expected API format for @indexed decorator."""
        @peer.model
        class APITestModel:
            field1: str
            field2: int

        # Based on spec, API: peer.indexed(model_name, field_name)
        # Test that this API works
        try:
            peer.indexed('APITestModel', 'field1')
            peer.indexed('APITestModel', 'field2')
            api_works = True
        except Exception:
            api_works = False

        msg = "The peer.indexed(model_name, field_name) API should work"
        assert api_works, msg

    def test_ddl_generation_is_idempotent(self, peer):
        """Test that generating DDL multiple times produces same result."""
        @peer.model
        class IdempotentModel:
            field: str

        peer.indexed('IdempotentModel', 'field')

        from peermodel.index import generate_ddl

        model_class = DocumentObj.Meta._reg['IdempotentModel']
        ddl1 = generate_ddl(model_class)
        ddl2 = generate_ddl(model_class)

        assert ddl1 == ddl2


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_indexed_nonexistent_field_raises_error(self, peer):
        """Test marking a non-existent field as indexed raises error."""
        @peer.model
        class EdgeModel:
            real_field: str

        # Trying to index a field that doesn't exist should raise an error
        with pytest.raises((KeyError, AttributeError, ValueError)):
            peer.indexed('EdgeModel', 'nonexistent_field')

    def test_model_with_no_fields_generates_valid_ddl(self, peer):
        """Test model with no user fields generates DDL with system cols."""
        @peer.model
        class EmptyModel:
            pass

        from peermodel.index import generate_ddl

        # Should still generate a table with system columns
        ddl = generate_ddl(DocumentObj.Meta._reg['EmptyModel'])

        assert 'CREATE TABLE' in ddl.upper()
        assert '_record_id' in ddl
        assert '_sequence' in ddl

    def test_indexed_on_complex_types_blob_storage(self, peer):
        """Test indexing complex types (dict, list) works with BLOB."""
        @peer.model
        class ComplexModel:
            metadata: dict
            tags: list

        peer.indexed('ComplexModel', 'metadata')
        peer.indexed('ComplexModel', 'tags')

        from peermodel.index import generate_ddl

        ddl = generate_ddl(DocumentObj.Meta._reg['ComplexModel'])

        # Should have BLOB columns for complex types
        assert 'metadata BLOB' in ddl
        assert 'tags BLOB' in ddl

        # Should still generate indexes on BLOB columns
        assert 'CREATE INDEX' in ddl.upper()
