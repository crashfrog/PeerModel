#!/usr/bin/env python

"""Tests for eager migration dry-run mode (Issue #34).

This module tests the dry_run parameter for migrate_eager(), which allows
executing the full migration pipeline (fetch, decrypt, transform, re-encrypt)
without writing changes to IPFS or the index.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path

import peermodel
from peermodel.peermodel import DocumentObj
from peermodel.index import IndexDB
from peermodel.migrations import (
    MigrationResult,
    migrate_eager,
    MigrationEngine,
)


@pytest.fixture
def peer():
    """Create test App instance."""
    return peermodel.App("test_eager_migration_dryrun")


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
def test_model_v1(peer):
    """Create a v1 test model."""
    @peer.model
    class SampleRecord:
        name: str
        value: int = 0

    return DocumentObj.Meta._reg['SampleRecord']


@pytest.fixture
def test_model_v2(peer):
    """Create a v2 test model (after schema evolution)."""
    @peer.model
    class SequenceRun:
        run_id: str
        description: str = ""

    return DocumentObj.Meta._reg['SequenceRun']


@pytest.fixture
def populated_index(index_db, test_model_v1):
    """Populate index with records at different schema versions."""
    # Setup schema
    index_db.ensure_schema(test_model_v1)

    # Insert records at version 1.0.0
    conn = sqlite3.connect(str(index_db.db_path))
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO SampleRecord
        (_record_id, _op_id, _sequence, _timestamp, _schema_version, name, value)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("rec-1", "op-1", 1, 1000, "1.0.0", "Alice", 100))

    cursor.execute("""
        INSERT INTO SampleRecord
        (_record_id, _op_id, _sequence, _timestamp, _schema_version, name, value)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("rec-2", "op-2", 2, 2000, "1.0.0", "Bob", 200))

    # Insert records at version 1.1.0 (minor update, no migration needed)
    cursor.execute("""
        INSERT INTO SampleRecord
        (_record_id, _op_id, _sequence, _timestamp, _schema_version, name, value)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("rec-3", "op-3", 3, 3000, "1.1.0", "Carol", 300))

    # Insert record at version 2.0.0 (major version, already migrated)
    cursor.execute("""
        INSERT INTO SampleRecord
        (_record_id, _op_id, _sequence, _timestamp, _schema_version, name, value)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("rec-4", "op-4", 4, 4000, "2.0.0", "David", 400))

    conn.commit()
    conn.close()

    return index_db


@pytest.fixture
def migration_engine():
    """Create a test migration engine with sample migrations."""
    def migrate_v1_0_to_v1_1(record_type, record_dict):
        """Add default description field."""
        result = dict(record_dict)
        if record_type == "SampleRecord":
            result["description"] = ""  # Add new field
        return result

    def migrate_v1_1_to_v2_0(record_type, record_dict):
        """Rename name to run_id, value to status."""
        result = dict(record_dict)
        if record_type == "SampleRecord":
            result["run_id"] = result.pop("name", "")
            result["status"] = result.pop("value", 0)
        return result

    migrations = {
        ("1.0.0", "1.1.0"): migrate_v1_0_to_v1_1,
        ("1.1.0", "2.0.0"): migrate_v1_1_to_v2_0,
    }

    return MigrationEngine(migrations)


@pytest.mark.issue_34
class TestMigrationResult:
    """Tests for MigrationResult dataclass."""

    def test_migration_result_creation(self):
        """Create MigrationResult with counts."""
        result = MigrationResult(migrated=5, skipped=3, errors=1)

        assert result.migrated == 5
        assert result.skipped == 3
        assert result.errors == 1

    def test_migration_result_default_values(self):
        """MigrationResult has sensible defaults."""
        result = MigrationResult()

        assert result.migrated == 0
        assert result.skipped == 0
        assert result.errors == 0
        assert result.error_details == []

    def test_migration_result_total_count(self):
        """MigrationResult.total property sums all counts."""
        result = MigrationResult(migrated=5, skipped=3, errors=2)

        assert result.total == 10

    def test_migration_result_with_error_details(self):
        """MigrationResult can track error details."""
        errors = [
            {"record_id": "rec-1", "error": "Decryption failed"},
            {"record_id": "rec-2", "error": "Invalid version"},
        ]
        result = MigrationResult(errors=2, error_details=errors)

        assert len(result.error_details) == 2
        assert result.error_details[0]["record_id"] == "rec-1"


@pytest.mark.issue_34
class TestEagerMigrationDryRun:
    """Tests for migrate_eager() with dry_run=True."""

    def test_migrate_eager_dry_run_signature(self):
        """migrate_eager accepts dry_run parameter."""
        # Should be callable with dry_run=True
        # This test checks the API exists
        assert callable(migrate_eager)

        # Check it accepts the required parameters
        import inspect
        sig = inspect.signature(migrate_eager)

        # Should have dry_run parameter
        assert "dry_run" in sig.parameters
        # dry_run should default to False
        assert sig.parameters["dry_run"].default is False

    def test_migrate_eager_dry_run_returns_migration_result(
        self, populated_index, migration_engine, monkeypatch
    ):
        """migrate_eager returns MigrationResult even in dry_run mode."""
        import asyncio

        # Mock the migration engine lookup
        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: migration_engine
        )

        # Call with dry_run=True
        result = asyncio.run(migrate_eager(
            index_db=populated_index,
            target_version="2.0.0",
            package_name="test_package",
            dry_run=True
        ))

        # Should return MigrationResult
        assert isinstance(result, MigrationResult)
        # Should have count fields
        assert hasattr(result, 'migrated')
        assert hasattr(result, 'skipped')
        assert hasattr(result, 'errors')

    def test_migrate_eager_dry_run_counts_records_needing_migration(
        self, populated_index, migration_engine, monkeypatch
    ):
        """In dry-run, migrated count reflects records that would migrate."""
        import asyncio

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: migration_engine
        )

        result = asyncio.run(migrate_eager(
            index_db=populated_index,
            target_version="2.0.0",
            package_name="test_package",
            dry_run=True
        ))

        # 2 records at 1.0.0 would be migrated
        # 1 record at 1.1.0 would be migrated
        # 1 record at 2.0.0 is already current
        assert result.migrated == 3
        assert result.skipped == 1
        assert result.errors == 0
        assert result.total == 4

    def test_migrate_eager_dry_run_does_not_update_index(
        self, populated_index, migration_engine, monkeypatch
    ):
        """In dry-run mode, the index is not modified."""
        import asyncio

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: migration_engine
        )

        # Record original schema versions before migration
        conn = sqlite3.connect(str(populated_index.db_path))
        cursor = conn.cursor()

        query = """SELECT _record_id, _schema_version
                   FROM SampleRecord ORDER BY _record_id"""
        cursor.execute(query)
        original_versions = dict(cursor.fetchall())
        conn.close()

        # Run dry-run migration
        asyncio.run(migrate_eager(
            index_db=populated_index,
            target_version="2.0.0",
            package_name="test_package",
            dry_run=True
        ))

        # Verify schema versions unchanged
        conn = sqlite3.connect(str(populated_index.db_path))
        cursor = conn.cursor()

        cursor.execute(query)
        final_versions = dict(cursor.fetchall())
        conn.close()

        # All versions should still be original
        assert final_versions == original_versions

    def test_migrate_eager_dry_run_does_not_modify_record_data(
        self, populated_index, migration_engine, monkeypatch
    ):
        """In dry-run mode, record data fields are not modified."""
        import asyncio

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: migration_engine
        )

        # Record original data before migration
        conn = sqlite3.connect(str(populated_index.db_path))
        cursor = conn.cursor()

        query = "SELECT _record_id, name, value FROM SampleRecord ORDER BY _record_id"
        cursor.execute(query)
        original_data = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        conn.close()

        # Run dry-run migration
        asyncio.run(migrate_eager(
            index_db=populated_index,
            target_version="2.0.0",
            package_name="test_package",
            dry_run=True
        ))

        # Verify data unchanged
        conn = sqlite3.connect(str(populated_index.db_path))
        cursor = conn.cursor()

        cursor.execute(query)
        final_data = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        conn.close()

        # All data should still be original
        assert final_data == original_data

    def test_migrate_eager_non_dry_run_writes_changes(
        self, populated_index, migration_engine, monkeypatch
    ):
        """When dry_run=False, changes are persisted."""
        import asyncio

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: migration_engine
        )

        # Run with dry_run=False
        result = asyncio.run(migrate_eager(
            index_db=populated_index,
            target_version="2.0.0",
            package_name="test_package",
            dry_run=False
        ))

        # Should still return valid result
        assert isinstance(result, MigrationResult)
        assert result.migrated > 0 or result.skipped > 0

        # Verify schema versions were updated
        conn = sqlite3.connect(str(populated_index.db_path))
        cursor = conn.cursor()

        query = """SELECT COUNT(*) FROM SampleRecord
                   WHERE _schema_version = '2.0.0'"""
        cursor.execute(query)
        count_at_target = cursor.fetchone()[0]
        conn.close()

        # At least some records should be at target version after non-dry-run
        assert count_at_target >= 3

    def test_migrate_eager_dry_run_executes_full_pipeline(
        self, populated_index, migration_engine, monkeypatch
    ):
        """In dry-run, the full pipeline is executed (even without writing)."""
        import asyncio

        # Track pipeline steps with a side-effect
        pipeline_steps = []

        def tracking_migration(step_name):
            def wrapper(record_type, record_dict):
                pipeline_steps.append(step_name)
                # Return transformed dict
                result = dict(record_dict)
                if step_name == "transform_1":
                    result["_transformed_step1"] = True
                elif step_name == "transform_2":
                    result["_transformed_step2"] = True
                return result
            return wrapper

        migrations = {
            ("1.0.0", "1.1.0"): tracking_migration("transform_1"),
            ("1.1.0", "2.0.0"): tracking_migration("transform_2"),
        }
        engine = MigrationEngine(migrations)

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: engine
        )

        # Run dry-run
        asyncio.run(migrate_eager(
            index_db=populated_index,
            target_version="2.0.0",
            package_name="test_package",
            dry_run=True
        ))

        # Pipeline steps should have been executed (even in dry-run)
        # Each record needing migration should trigger the pipeline
        assert len(pipeline_steps) > 0

    def test_migrate_eager_handles_errors_gracefully(
        self, populated_index, migration_engine, monkeypatch
    ):
        """migrate_eager tracks errors without stopping the migration."""
        import asyncio

        def failing_migration(record_type, record_dict):
            # Fail on records with value >= 300
            if record_dict.get("value", 0) >= 300:
                msg = "Cannot migrate high-value records"
                raise ValueError(msg)
            result = dict(record_dict)
            result["_migrated"] = True
            return result

        migrations = {
            ("1.0.0", "2.0.0"): failing_migration,
        }
        engine = MigrationEngine(migrations)

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: engine
        )

        # Run dry-run (should not raise, but track errors)
        result = asyncio.run(migrate_eager(
            index_db=populated_index,
            target_version="2.0.0",
            package_name="test_package",
            dry_run=True
        ))

        # Should have some errors
        assert result.errors > 0
        # Should have error details
        assert len(result.error_details) == result.errors

    def test_migrate_eager_dry_run_reports_accurate_counts(
        self, populated_index, migration_engine, monkeypatch
    ):
        """Dry-run reports same counts as non-dry-run would."""
        import asyncio
        import shutil

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: migration_engine
        )

        # Run dry-run
        dry_run_result = asyncio.run(migrate_eager(
            index_db=populated_index,
            target_version="2.0.0",
            package_name="test_package",
            dry_run=True
        ))

        # Create a copy of the index for non-dry-run
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            copy_db_path = Path(f.name)

        try:
            # Copy the populated database
            shutil.copy(str(populated_index.db_path), str(copy_db_path))

            copy_index = IndexDB(copy_db_path)

            # Run non-dry-run
            non_dry_run_result = asyncio.run(migrate_eager(
                index_db=copy_index,
                target_version="2.0.0",
                package_name="test_package",
                dry_run=False
            ))

            # Counts should match
            assert dry_run_result.migrated == non_dry_run_result.migrated
            assert dry_run_result.skipped == non_dry_run_result.skipped
            assert dry_run_result.errors == non_dry_run_result.errors
            assert dry_run_result.total == non_dry_run_result.total
        finally:
            if copy_db_path.exists():
                copy_db_path.unlink()

    def test_migrate_eager_default_dry_run_is_false(
        self, populated_index, migration_engine, monkeypatch
    ):
        """When dry_run is not specified, it defaults to False."""
        import asyncio

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: migration_engine
        )

        # Call without specifying dry_run
        asyncio.run(migrate_eager(
            index_db=populated_index,
            target_version="2.0.0",
            package_name="test_package"
            # dry_run not specified, should default to False
        ))

        # Should write changes (verify by checking index was updated)
        conn = sqlite3.connect(str(populated_index.db_path))
        cursor = conn.cursor()

        query = """SELECT COUNT(*) FROM SampleRecord
                   WHERE _schema_version = '2.0.0'"""
        cursor.execute(query)
        count_at_target = cursor.fetchone()[0]
        conn.close()

        # At least some records should be at target version
        assert count_at_target >= 3

    def test_migrate_eager_respects_migration_path(
        self, populated_index, migration_engine, monkeypatch
    ):
        """migrate_eager uses the migration path from MigrationEngine."""
        import asyncio

        # Track which migrations were called
        called_migrations = []

        def tracked_v1_0_to_v1_1(record_type, record_dict):
            called_migrations.append(("1.0.0", "1.1.0"))
            result = dict(record_dict)
            result["_v1_1"] = True
            return result

        def tracked_v1_1_to_v2_0(record_type, record_dict):
            called_migrations.append(("1.1.0", "2.0.0"))
            result = dict(record_dict)
            result["_v2_0"] = True
            return result

        migrations = {
            ("1.0.0", "1.1.0"): tracked_v1_0_to_v1_1,
            ("1.1.0", "2.0.0"): tracked_v1_1_to_v2_0,
        }
        engine = MigrationEngine(migrations)

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: engine
        )

        # Run dry-run
        asyncio.run(migrate_eager(
            index_db=populated_index,
            target_version="2.0.0",
            package_name="test_package",
            dry_run=True
        ))

        # Both migration steps should have been called for v1.0.0 records
        assert ("1.0.0", "1.1.0") in called_migrations
        assert ("1.1.0", "2.0.0") in called_migrations

    def test_migrate_eager_empty_index(
        self, index_db, test_model_v1, migration_engine, monkeypatch
    ):
        """migrate_eager handles empty index gracefully."""
        import asyncio

        # Setup empty schema (no records)
        index_db.ensure_schema(test_model_v1)

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: migration_engine
        )

        result = asyncio.run(migrate_eager(
            index_db=index_db,
            target_version="2.0.0",
            package_name="test_package",
            dry_run=True
        ))

        # Should return valid result with all zeros
        assert isinstance(result, MigrationResult)
        assert result.migrated == 0
        assert result.skipped == 0
        assert result.errors == 0
        assert result.total == 0

    def test_migrate_eager_missing_migration_path(
        self, populated_index, monkeypatch
    ):
        """migrate_eager raises error when no migration path exists."""
        import asyncio
        from peermodel.migrations import MissingMigrationError

        # Create engine with a gap (no path from 1.x to 3.x)
        migrations = {
            ("3.0.0", "3.1.0"): lambda rt, rd: rd,
        }
        engine = MigrationEngine(migrations)

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: engine
        )

        # Should raise MissingMigrationError when trying to migrate to 3.x
        with pytest.raises(MissingMigrationError):
            asyncio.run(migrate_eager(
                index_db=populated_index,
                target_version="3.0.0",
                package_name="test_package",
                dry_run=True
            ))


@pytest.mark.issue_34
class TestDryRunVsNonDryRun:
    """Tests comparing dry-run vs non-dry-run behavior."""

    def test_dry_run_and_non_dry_run_same_counts(
        self, populated_index, migration_engine, monkeypatch
    ):
        """Both modes report identical counts."""
        import asyncio
        import shutil

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: migration_engine
        )

        # Dry-run
        dry_result = asyncio.run(migrate_eager(
            index_db=populated_index,
            target_version="2.0.0",
            package_name="test_package",
            dry_run=True
        ))

        # Create fresh copy for non-dry-run
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            fresh_db_path = Path(f.name)

        try:
            shutil.copy(str(populated_index.db_path), str(fresh_db_path))
            fresh_index = IndexDB(fresh_db_path)

            # Non-dry-run
            wet_result = asyncio.run(migrate_eager(
                index_db=fresh_index,
                target_version="2.0.0",
                package_name="test_package",
                dry_run=False
            ))

            # All counts should match
            assert dry_result.migrated == wet_result.migrated
            assert dry_result.skipped == wet_result.skipped
            assert dry_result.errors == wet_result.errors
        finally:
            if fresh_db_path.exists():
                fresh_db_path.unlink()

    def test_dry_run_index_unchanged_after_migration(
        self, populated_index, migration_engine, monkeypatch
    ):
        """After dry-run, index is completely unchanged."""
        import asyncio
        import shutil

        monkeypatch.setattr(
            'peermodel.migrations.get_engine',
            lambda pkg: migration_engine
        )

        # Save original state
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            original_copy_path = Path(f.name)

        try:
            shutil.copy(str(populated_index.db_path), str(original_copy_path))

            # Run dry-run
            asyncio.run(migrate_eager(
                index_db=populated_index,
                target_version="2.0.0",
                package_name="test_package",
                dry_run=True
            ))

            # Compare current with original
            conn_current = sqlite3.connect(str(populated_index.db_path))
            conn_original = sqlite3.connect(str(original_copy_path))

            cursor_current = conn_current.cursor()
            cursor_original = conn_original.cursor()

            # Get all data from both
            query = "SELECT * FROM SampleRecord ORDER BY _record_id"
            cursor_current.execute(query)
            current_data = cursor_current.fetchall()

            cursor_original.execute(query)
            original_data = cursor_original.fetchall()

            conn_current.close()
            conn_original.close()

            # Data should be identical
            assert current_data == original_data
        finally:
            if original_copy_path.exists():
                original_copy_path.unlink()
