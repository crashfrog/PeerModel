#!/usr/bin/env python

"""Tests for defensive deserialization (issue #32).

These tests verify that DocumentObj._from_storage() tolerates schema evolution:
- Ignore unknown fields (log at DEBUG level)
- Use field defaults for missing fields (additive changes)
- Never raise on unrecognized fields
"""

import pytest
from dataclasses import field

import peermodel


@pytest.fixture
def peer():
    return peermodel.App("test model")


@pytest.fixture
def memdb():
    with peermodel.InMemoryDocumentDatabase() as db:
        yield db


# Test 1: Deserialize with extra fields (should ignore)
def test_deserialize_with_extra_fields_ignores_them(peer, memdb):
    """When storage has extra fields not in the model, ignore them silently."""
    @peer.model
    class TestDocument:
        name: str = ""
        age: int = 0

    # Simulate storage record with an extra field "email" that doesn't exist in model
    storage_record = {
        'name': 'Alice',
        'age': 30,
        'email': 'alice@example.com'  # Extra field not in model
    }

    doc_id = '12345678-1234-5678-1234-567812345678'

    # This should not raise an exception - extra fields should be ignored
    result = TestDocument._from_storage(memdb, doc_id, storage_record)

    assert result._id == doc_id
    assert result.name == 'Alice'
    assert result.age == 30
    assert not hasattr(result, 'email')  # Extra field should not be set


def test_deserialize_with_multiple_extra_fields(peer, memdb):
    """Multiple extra fields should all be ignored."""
    @peer.model
    class TestDocument:
        name: str = ""

    storage_record = {
        'name': 'Bob',
        'extra1': 'value1',
        'extra2': 'value2',
        'extra3': 42
    }

    doc_id = '12345678-1234-5678-1234-567812345678'

    result = TestDocument._from_storage(memdb, doc_id, storage_record)

    assert result._id == doc_id
    assert result.name == 'Bob'
    assert not hasattr(result, 'extra1')
    assert not hasattr(result, 'extra2')
    assert not hasattr(result, 'extra3')


# Test 2: Deserialize with missing fields (should use defaults)
def test_deserialize_with_missing_field_uses_default(peer, memdb):
    """When storage is missing a field, use the field's default value."""
    @peer.model
    class TestDocument:
        name: str = ""
        age: int = 0
        email: str = "default@example.com"

    # Storage record missing the 'email' field
    storage_record = {
        'name': 'Charlie',
        'age': 25
    }

    doc_id = '12345678-1234-5678-1234-567812345678'

    # Should not raise, should use default for email
    result = TestDocument._from_storage(memdb, doc_id, storage_record)

    assert result._id == doc_id
    assert result.name == 'Charlie'
    assert result.age == 25
    assert result.email == "default@example.com"  # Should use default


def test_deserialize_with_missing_field_uses_factory_default(peer, memdb):
    """When storage is missing a field with default_factory, use the factory."""
    @peer.model
    class TestDocument:
        name: str = ""
        tags: list = field(default_factory=list)

    # Storage record missing the 'tags' field
    storage_record = {
        'name': 'Dave'
    }

    doc_id = '12345678-1234-5678-1234-567812345678'

    result = TestDocument._from_storage(memdb, doc_id, storage_record)

    assert result._id == doc_id
    assert result.name == 'Dave'
    assert result.tags == []  # Should use default_factory result


def test_deserialize_with_multiple_missing_fields(peer, memdb):
    """Multiple missing fields should all use their defaults."""
    @peer.model
    class TestDocument:
        name: str = ""
        age: int = 0
        email: str = "default@example.com"
        active: bool = True
        tags: list = field(default_factory=list)

    # Storage record only has name
    storage_record = {
        'name': 'Eve'
    }

    doc_id = '12345678-1234-5678-1234-567812345678'

    result = TestDocument._from_storage(memdb, doc_id, storage_record)

    assert result._id == doc_id
    assert result.name == 'Eve'
    assert result.age == 0
    assert result.email == "default@example.com"
    assert result.active is True
    assert result.tags == []


# Test 3: No exceptions on schema mismatch (combination of both)
def test_no_exception_on_both_extra_and_missing_fields(peer, memdb):
    """Schema evolution with both extra and missing fields should not raise."""
    @peer.model
    class TestDocument:
        name: str = ""
        age: int = 0
        new_field: str = "default_value"

    # Storage has 'email' (extra) but missing 'new_field'
    storage_record = {
        'name': 'Frank',
        'age': 40,
        'email': 'frank@example.com'  # Extra
        # 'new_field' is missing
    }

    doc_id = '12345678-1234-5678-1234-567812345678'

    # Should handle both gracefully
    result = TestDocument._from_storage(memdb, doc_id, storage_record)

    assert result._id == doc_id
    assert result.name == 'Frank'
    assert result.age == 40
    assert result.new_field == "default_value"  # Missing field uses default
    assert not hasattr(result, 'email')  # Extra field ignored


def test_empty_storage_record_uses_all_defaults(peer, memdb):
    """Empty storage record should create document with all defaults."""
    @peer.model
    class TestDocument:
        name: str = "default_name"
        age: int = 0
        active: bool = True

    storage_record = {}  # Completely empty

    doc_id = '12345678-1234-5678-1234-567812345678'

    result = TestDocument._from_storage(memdb, doc_id, storage_record)

    assert result._id == doc_id
    assert result.name == "default_name"
    assert result.age == 0
    assert result.active is True


def test_deserialize_nested_document_with_schema_changes(peer, memdb):
    """Nested documents should also handle schema evolution defensively."""
    @peer.model
    class InnerDocument:
        value: str = ""
        new_field: str = "default"  # Field added after some records stored

    @peer.model
    class OuterDocument:
        name: str = ""
        inner: InnerDocument = None

    # Storage has nested document missing new_field
    storage_record = {
        'name': 'Grace',
        'inner': ('InnerDocument', 'inner-id', {'value': 'test_value'})
        # 'new_field' missing in inner document
    }

    doc_id = '12345678-1234-5678-1234-567812345678'

    result = OuterDocument._from_storage(memdb, doc_id, storage_record)

    assert result._id == doc_id
    assert result.name == 'Grace'
    assert result.inner.value == 'test_value'
    assert result.inner.new_field == "default"  # Should use default for missing field


def test_deserialize_nested_document_with_extra_fields(peer, memdb):
    """Nested documents should ignore extra fields in storage."""
    @peer.model
    class InnerDocument:
        value: str = ""

    @peer.model
    class OuterDocument:
        name: str = ""
        inner: InnerDocument = None

    # Storage has nested document with extra field
    storage_record = {
        'name': 'Henry',
        'inner': ('InnerDocument', 'inner-id', {
            'value': 'test_value',
            'removed_field': 'old_data'  # Extra field
        })
    }

    doc_id = '12345678-1234-5678-1234-567812345678'

    result = OuterDocument._from_storage(memdb, doc_id, storage_record)

    assert result._id == doc_id
    assert result.name == 'Henry'
    assert result.inner.value == 'test_value'
    assert not hasattr(result.inner, 'removed_field')
