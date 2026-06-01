#!/usr/bin/env python

"""Acceptance tests for IndexDB.query() implementation (Issue #21)."""

import pytest
import sqlite3
import tempfile
from pathlib import Path

import peermodel
from peermodel.peermodel import DocumentObj
from peermodel.index import IndexDB


@pytest.fixture
def peer():
    """Create test App instance."""
    return peermodel.App("test_query_interface")


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
    """Create a test model for queries."""
    @peer.model
    class Product:
        name: str
        category: str
        price: int
        stock: int
        active: bool

    # Mark some fields as indexed
    peer.indexed('Product', 'name')
    peer.indexed('Product', 'category')
    peer.indexed('Product', 'price')
    peer.indexed('Product', 'active')

    return DocumentObj.Meta._reg['Product']


def insert_test_data(index_db, test_model):
    """Insert test data into the database."""
    index_db.ensure_schema(test_model)

    test_records = [
        ('prod-1', 'op-1', 1, 'Laptop', 'Electronics', 1000, 5, 1),
        ('prod-2', 'op-2', 2, 'Mouse', 'Electronics', 25, 150, 1),
        ('prod-3', 'op-3', 3, 'Keyboard', 'Electronics', 75, 100, 1),
        ('prod-4', 'op-4', 4, 'Monitor', 'Electronics', 300, 10, 0),
        ('prod-5', 'op-5', 5, 'Desk', 'Furniture', 500, 20, 1),
        ('prod-6', 'op-6', 6, 'Chair', 'Furniture', 200, 30, 1),
    ]

    conn = sqlite3.connect(index_db.db_path)
    cursor = conn.cursor()

    for rec_id, op_id, seq, name, category, price, stock, active in test_records:
        cursor.execute(
            f"""
            INSERT INTO Product
            (_record_id, _op_id, _sequence, _timestamp, _head_cid, _tombstoned, _schema_version,
             name, category, price, stock, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (rec_id, op_id, seq, 1000000000, 'cid-1', 0, 1, name, category, price, stock, active)
        )

    conn.commit()
    conn.close()


@pytest.mark.issue_21
class TestQueryByExactValue:
    """Test querying by exact field values."""

    def test_query_by_string_field_exact_match(self, peer, index_db, test_model):
        """Test query with exact string match."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'name': 'Laptop'}
        )

        assert len(results) == 1
        assert results[0]['name'] == 'Laptop'
        assert results[0]['_record_id'] == 'prod-1'

    def test_query_by_category_exact_match(self, peer, index_db, test_model):
        """Test query with exact string match on category field."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'category': 'Electronics'}
        )

        assert len(results) == 4
        for result in results:
            assert result['category'] == 'Electronics'

    def test_query_by_integer_field_exact_match(self, peer, index_db, test_model):
        """Test query with exact integer match."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'price': 1000}
        )

        assert len(results) == 1
        assert results[0]['price'] == 1000
        assert results[0]['name'] == 'Laptop'

    def test_query_by_boolean_field_exact_match(self, peer, index_db, test_model):
        """Test query with exact boolean match."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'active': True}
        )

        assert len(results) == 5
        for result in results:
            assert result['active'] is True

    def test_query_by_boolean_field_false(self, peer, index_db, test_model):
        """Test query with boolean false."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'active': False}
        )

        assert len(results) == 1
        assert results[0]['active'] is False
        assert results[0]['name'] == 'Monitor'

    def test_query_no_matches_returns_empty_list(self, peer, index_db, test_model):
        """Test query with no matching results."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'name': 'NonexistentProduct'}
        )

        assert len(results) == 0
        assert results == []


@pytest.mark.issue_21
class TestQueryWithComparisonOperators:
    """Test querying with comparison operators (>, <, >=, <=)."""

    def test_query_greater_than_operator(self, peer, index_db, test_model):
        """Test query with > operator."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'price': ('>', 100)}
        )

        assert len(results) == 4  # Laptop(1000), Monitor(300), Desk(500), Chair(200)
        for result in results:
            assert result['price'] > 100

    def test_query_less_than_operator(self, peer, index_db, test_model):
        """Test query with < operator."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'price': ('<', 100)}
        )

        assert len(results) == 2  # Mouse(25), Keyboard(75)
        for result in results:
            assert result['price'] < 100

    def test_query_greater_than_or_equal_operator(self, peer, index_db, test_model):
        """Test query with >= operator."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'price': ('>=', 200)}
        )

        assert len(results) == 4  # Laptop(1000), Monitor(300), Desk(500), Chair(200)
        for result in results:
            assert result['price'] >= 200

    def test_query_less_than_or_equal_operator(self, peer, index_db, test_model):
        """Test query with <= operator."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'price': ('<=', 100)}
        )

        assert len(results) == 2  # Mouse(25), Keyboard(75)
        for result in results:
            assert result['price'] <= 100

    def test_query_greater_than_with_integers(self, peer, index_db, test_model):
        """Test > operator returns correct rows."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'stock': ('>', 50)}
        )

        # Products with stock > 50: Mouse(150), Keyboard(100), Chair(30) - wait Chair is 30
        # Actually: Mouse(150), Keyboard(100)
        assert len(results) == 2
        for result in results:
            assert result['stock'] > 50


@pytest.mark.issue_21
class TestOrderBy:
    """Test ordering results by field (ASC/DESC)."""

    def test_query_order_by_ascending(self, peer, index_db, test_model):
        """Test ordering results in ascending order."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            order_by='price'
        )

        prices = [r['price'] for r in results]
        assert prices == sorted(prices)
        assert prices == [25, 75, 200, 300, 500, 1000]

    def test_query_order_by_descending(self, peer, index_db, test_model):
        """Test ordering results in descending order with - prefix."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            order_by='-price'
        )

        prices = [r['price'] for r in results]
        assert prices == sorted(prices, reverse=True)
        assert prices == [1000, 500, 300, 200, 75, 25]

    def test_query_order_by_string_ascending(self, peer, index_db, test_model):
        """Test ordering by string field ascending."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            order_by='name'
        )

        names = [r['name'] for r in results]
        assert names == sorted(names)

    def test_query_order_by_string_descending(self, peer, index_db, test_model):
        """Test ordering by string field descending."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            order_by='-name'
        )

        names = [r['name'] for r in results]
        assert names == sorted(names, reverse=True)

    def test_query_order_by_combined_with_filters(self, peer, index_db, test_model):
        """Test ordering combined with filtering."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'category': 'Electronics'},
            order_by='price'
        )

        prices = [r['price'] for r in results]
        assert len(results) == 4
        assert prices == sorted(prices)
        assert prices == [25, 75, 300, 1000]


@pytest.mark.issue_21
class TestPagination:
    """Test pagination with limit and offset."""

    def test_query_limit_returns_specified_number(self, peer, index_db, test_model):
        """Test limit parameter returns specified number of rows."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            order_by='name',
            limit=3
        )

        assert len(results) == 3

    def test_query_limit_zero_returns_all(self, peer, index_db, test_model):
        """Test limit=0 returns all rows."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            limit=0
        )

        assert len(results) == 6

    def test_query_limit_greater_than_total(self, peer, index_db, test_model):
        """Test limit greater than total returns all."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            limit=100
        )

        assert len(results) == 6

    def test_query_offset_skips_rows(self, peer, index_db, test_model):
        """Test offset parameter skips specified rows."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            order_by='name',
            offset=2
        )

        assert len(results) == 4
        names = [r['name'] for r in results]
        # After skipping 2: Keyboard, Laptop, Monitor, Mouse
        assert 'Chair' not in names
        assert 'Desk' not in names

    def test_query_limit_and_offset_together(self, peer, index_db, test_model):
        """Test limit and offset together for pagination."""
        insert_test_data(index_db, test_model)

        # Get page 1: rows 0-2
        page1 = index_db.query(
            test_model,
            order_by='name',
            limit=2,
            offset=0
        )
        assert len(page1) == 2

        # Get page 2: rows 2-4
        page2 = index_db.query(
            test_model,
            order_by='name',
            limit=2,
            offset=2
        )
        assert len(page2) == 2

        # Get page 3: rows 4-6
        page3 = index_db.query(
            test_model,
            order_by='name',
            limit=2,
            offset=4
        )
        assert len(page3) == 2

        # Verify no duplicates across pages
        all_ids = set()
        for page in [page1, page2, page3]:
            for result in page:
                assert result['_record_id'] not in all_ids
                all_ids.add(result['_record_id'])

    def test_query_offset_without_limit(self, peer, index_db, test_model):
        """Test offset alone returns remaining rows."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            order_by='name',
            offset=3
        )

        assert len(results) == 3

    def test_query_offset_greater_than_total(self, peer, index_db, test_model):
        """Test offset greater than total returns empty."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            offset=100
        )

        assert len(results) == 0


@pytest.mark.issue_21
class TestTombstonedRecordsHandling:
    """Test default exclusion of tombstoned records."""

    def test_query_excludes_tombstoned_by_default(self, peer, index_db, test_model):
        """Test that tombstoned records are excluded by default."""
        insert_test_data(index_db, test_model)

        # Tombstone one record
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Product SET _tombstoned = 1, _op_id = ? WHERE _record_id = ?",
            ('op-tombstone-1', 'prod-1')
        )
        conn.commit()
        conn.close()

        results = index_db.query(test_model)

        assert len(results) == 5
        for result in results:
            assert result['_record_id'] != 'prod-1'

    def test_query_include_tombstoned_true(self, peer, index_db, test_model):
        """Test include_tombstoned=True includes tombstoned records."""
        insert_test_data(index_db, test_model)

        # Tombstone one record
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Product SET _tombstoned = 1, _op_id = ? WHERE _record_id = ?",
            ('op-tombstone-1', 'prod-1')
        )
        conn.commit()
        conn.close()

        results = index_db.query(
            test_model,
            include_tombstoned=True
        )

        assert len(results) == 6
        tombstoned = [r for r in results if r['_record_id'] == 'prod-1']
        assert len(tombstoned) == 1
        assert tombstoned[0]['_tombstoned'] == 1

    def test_query_filters_with_tombstoned_default(self, peer, index_db, test_model):
        """Test filtering respects tombstoned exclusion."""
        insert_test_data(index_db, test_model)

        # Tombstone a Monitor (the only inactive product)
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Product SET _tombstoned = 1, _op_id = ? WHERE _record_id = ?",
            ('op-tombstone-4', 'prod-4')
        )
        conn.commit()
        conn.close()

        # Query for inactive products
        results = index_db.query(
            test_model,
            filters={'active': False}
        )

        # Should return empty since prod-4 is now tombstoned
        assert len(results) == 0

    def test_query_filters_with_include_tombstoned_true(self, peer, index_db, test_model):
        """Test filtering with include_tombstoned=True."""
        insert_test_data(index_db, test_model)

        # Tombstone a Monitor (the only inactive product)
        conn = sqlite3.connect(index_db.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Product SET _tombstoned = 1, _op_id = ? WHERE _record_id = ?",
            ('op-tombstone-4', 'prod-4')
        )
        conn.commit()
        conn.close()

        # Query for inactive products including tombstoned
        results = index_db.query(
            test_model,
            filters={'active': False},
            include_tombstoned=True
        )

        assert len(results) == 1
        assert results[0]['_record_id'] == 'prod-4'
        assert results[0]['_tombstoned'] == 1


@pytest.mark.issue_21
class TestComplexQueries:
    """Test complex combinations of filters, ordering, and pagination."""

    def test_query_filter_order_limit(self, peer, index_db, test_model):
        """Test combined filter, order, and limit."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'category': 'Electronics'},
            order_by='-price',
            limit=2
        )

        assert len(results) == 2
        assert results[0]['price'] == 1000
        assert results[1]['price'] == 300

    def test_query_filter_order_pagination(self, peer, index_db, test_model):
        """Test filtering, ordering, and pagination together."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'active': True},
            order_by='price',
            limit=2,
            offset=1
        )

        assert len(results) == 2
        prices = [r['price'] for r in results]
        assert prices == [75, 200]

    def test_query_comparison_operator_with_order_and_limit(self, peer, index_db, test_model):
        """Test comparison operator with ordering and limit."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'price': ('>=', 200)},
            order_by='price',
            limit=3
        )

        assert len(results) == 3
        prices = [r['price'] for r in results]
        assert prices == [200, 300, 500]

    def test_query_multiple_filters_and_operator(self, peer, index_db, test_model):
        """Test multiple filter conditions."""
        insert_test_data(index_db, test_model)

        # Query for active Electronics products
        results = index_db.query(
            test_model,
            filters={
                'category': 'Electronics',
                'active': True
            },
            order_by='price'
        )

        assert len(results) == 3
        for result in results:
            assert result['category'] == 'Electronics'
            assert result['active'] is True


@pytest.mark.issue_21
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_query_empty_database(self, peer, index_db, test_model):
        """Test query on empty database."""
        index_db.ensure_schema(test_model)

        results = index_db.query(test_model)

        assert len(results) == 0

    def test_query_with_no_filters_no_ordering(self, peer, index_db, test_model):
        """Test query with default parameters."""
        insert_test_data(index_db, test_model)

        results = index_db.query(test_model)

        assert len(results) == 6

    def test_query_returns_all_columns(self, peer, index_db, test_model):
        """Test query returns all columns including system columns."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'name': 'Laptop'},
            limit=1
        )

        assert len(results) == 1
        result = results[0]

        # Check system columns
        assert '_record_id' in result
        assert '_op_id' in result
        assert '_sequence' in result
        assert '_timestamp' in result
        assert '_tombstoned' in result
        assert '_schema_version' in result

        # Check model fields
        assert 'name' in result
        assert 'category' in result
        assert 'price' in result
        assert 'stock' in result
        assert 'active' in result

    def test_query_result_format_is_dict(self, peer, index_db, test_model):
        """Test query results are dictionaries."""
        insert_test_data(index_db, test_model)

        results = index_db.query(test_model, limit=1)

        assert len(results) == 1
        assert isinstance(results[0], dict)

    def test_query_returns_correct_types(self, peer, index_db, test_model):
        """Test query results have correct data types."""
        insert_test_data(index_db, test_model)

        results = index_db.query(test_model, limit=1)
        result = results[0]

        # Check string fields
        assert isinstance(result['name'], str)
        assert isinstance(result['category'], str)

        # Check integer fields
        assert isinstance(result['price'], int)
        assert isinstance(result['stock'], int)

        # Check boolean field
        assert isinstance(result['active'], (bool, int))  # SQLite stores bool as 0/1

    def test_query_offset_at_boundary(self, peer, index_db, test_model):
        """Test offset at the boundary."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            order_by='name',
            offset=5
        )

        assert len(results) == 1

    def test_query_limit_one(self, peer, index_db, test_model):
        """Test limit=1 returns exactly one result."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            limit=1
        )

        assert len(results) == 1

    def test_query_with_zero_offset(self, peer, index_db, test_model):
        """Test offset=0 starts from beginning."""
        insert_test_data(index_db, test_model)

        results_with_offset = index_db.query(
            test_model,
            order_by='name',
            offset=0,
            limit=3
        )

        results_without_offset = index_db.query(
            test_model,
            order_by='name',
            limit=3
        )

        assert len(results_with_offset) == len(results_without_offset)
        assert results_with_offset == results_without_offset


@pytest.mark.issue_21
class TestFilterSyntax:
    """Test different filter syntax variations."""

    def test_filter_exact_value_syntax(self, peer, index_db, test_model):
        """Test exact value filter syntax."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'price': 1000}
        )

        assert len(results) == 1
        assert results[0]['price'] == 1000

    def test_filter_tuple_operator_syntax(self, peer, index_db, test_model):
        """Test tuple operator filter syntax."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            filters={'price': ('>', 500)}
        )

        assert len(results) == 1  # Laptop(1000)
        assert all(r['price'] > 500 for r in results)

    def test_filter_comparison_operators_all_types(self, peer, index_db, test_model):
        """Test all comparison operators."""
        insert_test_data(index_db, test_model)

        # Greater than
        gt = index_db.query(test_model, filters={'price': ('>', 200)})
        # Less than
        lt = index_db.query(test_model, filters={'price': ('<', 200)})
        # Greater or equal
        gte = index_db.query(test_model, filters={'price': ('>=', 200)})
        # Less or equal
        lte = index_db.query(test_model, filters={'price': ('<=', 200)})

        assert len(gt) == 3   # 1000, 300, 500
        assert len(lt) == 2   # 25, 75
        assert len(gte) == 4  # 1000, 300, 500, 200
        assert len(lte) == 3  # 25, 75, 200


@pytest.mark.issue_21
class TestOrderingSyntax:
    """Test ordering syntax variations."""

    def test_order_ascending_explicit(self, peer, index_db, test_model):
        """Test ascending order without prefix."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            order_by='price'
        )

        prices = [r['price'] for r in results]
        assert prices == sorted(prices)

    def test_order_descending_with_dash_prefix(self, peer, index_db, test_model):
        """Test descending order with - prefix."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            order_by='-price'
        )

        prices = [r['price'] for r in results]
        assert prices == sorted(prices, reverse=True)

    def test_order_none_returns_any_order(self, peer, index_db, test_model):
        """Test order_by=None returns results in any order."""
        insert_test_data(index_db, test_model)

        results = index_db.query(
            test_model,
            order_by=None
        )

        assert len(results) == 6

    def test_order_by_different_fields(self, peer, index_db, test_model):
        """Test ordering by different field types."""
        insert_test_data(index_db, test_model)

        # Order by string field
        by_name = index_db.query(test_model, order_by='name')
        names = [r['name'] for r in by_name]
        assert names == sorted(names)

        # Order by integer field
        by_price = index_db.query(test_model, order_by='price')
        prices = [r['price'] for r in by_price]
        assert prices == sorted(prices)
