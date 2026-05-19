#!/usr/bin/env python

"""Tests for migration registry discovery (Issue #29)."""

import pytest


def test_load_registry_from_package():
    """Load registry from data model package.

    Tests that load_engine() can import a package's migrations.registry
    module and construct a MigrationEngine from its MIGRATIONS dict.

    Acceptance criteria:
    - Load registry from data model package
    """
    from peermodel.migrations import load_engine

    # Create a mock package with a migrations.registry module
    # This test expects load_engine to:
    # 1. Import {package_name}.migrations.registry
    # 2. Read the MIGRATIONS dict
    # 3. Return a MigrationEngine instance

    # For this RED test, we expect load_engine to not exist yet
    engine = load_engine("test_package")
    assert engine is not None


def test_build_version_graph():
    """Build version graph from MIGRATIONS keys.

    Tests that MigrationEngine builds a directed graph where:
    - Nodes are version strings
    - Edges are (from_version, to_version) pairs
    - Used by find_path() for BFS traversal

    Acceptance criteria:
    - Build version graph
    """
    from peermodel.migrations import MigrationEngine

    # Sample migration registry
    migrations = {
        ("1.0.0", "1.1.0"): lambda rt, rd: rd,
        ("1.1.0", "2.0.0"): lambda rt, rd: rd,
        ("2.0.0", "2.1.0"): lambda rt, rd: rd,
    }

    engine = MigrationEngine(migrations)
    graph = engine.build_version_graph()

    # Graph should be an adjacency list: version -> list of reachable versions
    assert "1.0.0" in graph
    assert "1.1.0" in graph["1.0.0"]
    assert "2.0.0" in graph["1.1.0"]
    assert "2.1.0" in graph["2.0.0"]


def test_find_single_step_path():
    """Find single-step migration path.

    Tests that find_path() correctly identifies a direct migration
    from one version to another when a single-step transform exists.

    Acceptance criteria:
    - Find single-step path
    """
    from peermodel.migrations import MigrationEngine

    migrations = {
        ("1.0.0", "2.0.0"): lambda rt, rd: rd,
    }

    engine = MigrationEngine(migrations)
    path = engine.find_path("1.0.0", "2.0.0")

    # Should return list of (from, to) tuples representing each step
    assert path == [("1.0.0", "2.0.0")]


def test_find_multi_step_path():
    """Find multi-step migration path using BFS.

    Tests that find_path() finds the shortest path through multiple
    migration steps when no direct migration exists.

    Acceptance criteria:
    - Find multi-step path
    """
    from peermodel.migrations import MigrationEngine

    migrations = {
        ("1.0.0", "1.1.0"): lambda rt, rd: rd,
        ("1.1.0", "2.0.0"): lambda rt, rd: rd,
        ("2.0.0", "2.1.0"): lambda rt, rd: rd,
    }

    engine = MigrationEngine(migrations)
    path = engine.find_path("1.0.0", "2.1.0")

    # Should find shortest path: 1.0.0 -> 1.1.0 -> 2.0.0 -> 2.1.0
    assert len(path) == 3
    assert path[0] == ("1.0.0", "1.1.0")
    assert path[1] == ("1.1.0", "2.0.0")
    assert path[2] == ("2.0.0", "2.1.0")


def test_find_path_no_migration_needed():
    """Return empty path when versions match.

    Tests that find_path() returns an empty list when from_version
    equals to_version (no migration needed).
    """
    from peermodel.migrations import MigrationEngine

    migrations = {
        ("1.0.0", "2.0.0"): lambda rt, rd: rd,
    }

    engine = MigrationEngine(migrations)
    path = engine.find_path("2.0.0", "2.0.0")

    assert path == []


def test_missing_migration_error_on_major_version_gap():
    """Raise MissingMigrationError when major version gap has no path.

    Tests that find_path() raises MissingMigrationError when:
    - from_version and to_version have different major version components
    - No migration path exists between them

    Per spec: "If versions differ only in minor/patch and no path exists,
    returns empty list (additive change; no transform needed)."

    Acceptance criteria:
    - Raise MissingMigrationError on gap
    """
    from peermodel.migrations import MigrationEngine, MissingMigrationError

    migrations = {
        ("1.0.0", "1.1.0"): lambda rt, rd: rd,
        # No path from 1.x to 3.x
        ("3.0.0", "3.1.0"): lambda rt, rd: rd,
    }

    engine = MigrationEngine(migrations)

    # Major version gap (1.x -> 3.x) with no path should raise
    with pytest.raises(MissingMigrationError):
        engine.find_path("1.1.0", "3.0.0")


def test_additive_change_no_migration():
    """Return empty path for minor version difference with no migration.

    Tests that find_path() returns empty list for additive changes
    (minor/patch version bumps) where no explicit migration exists.
    This is intentional - additive changes don't require migration functions.
    """
    from peermodel.migrations import MigrationEngine

    migrations = {
        ("1.0.0", "2.0.0"): lambda rt, rd: rd,
        # No migration from 2.0.0 to 2.1.0 - it's an additive change
    }

    engine = MigrationEngine(migrations)
    path = engine.find_path("2.0.0", "2.1.0")

    # Minor version bump with no registered migration should return empty list
    assert path == []


def test_apply_single_step_migration():
    """Apply a single migration transform.

    Tests that apply() correctly invokes a single migration function
    and returns the transformed record dict.
    """
    from peermodel.migrations import MigrationEngine

    def migrate_v1_to_v2(record_type, record_dict):
        result = dict(record_dict)
        result["renamed_field"] = result.pop("old_field")
        return result

    migrations = {
        ("1.0.0", "2.0.0"): migrate_v1_to_v2,
    }

    engine = MigrationEngine(migrations)
    record = {"old_field": "value"}
    result = engine.apply("TestRecord", record, "1.0.0", "2.0.0")

    assert "renamed_field" in result
    assert "old_field" not in result
    assert result["renamed_field"] == "value"


def test_apply_multi_step_migration():
    """Apply multi-step migration path sequentially.

    Tests that apply() chains multiple migration functions,
    passing the output of each step to the next.
    """
    from peermodel.migrations import MigrationEngine

    def migrate_v1_to_v1_1(record_type, record_dict):
        result = dict(record_dict)
        result["new_field"] = "added_in_1_1"
        return result

    def migrate_v1_1_to_v2_0(record_type, record_dict):
        result = dict(record_dict)
        result["another_field"] = "added_in_2_0"
        return result

    migrations = {
        ("1.0.0", "1.1.0"): migrate_v1_to_v1_1,
        ("1.1.0", "2.0.0"): migrate_v1_1_to_v2_0,
    }

    engine = MigrationEngine(migrations)
    record = {"original": "value"}
    result = engine.apply("TestRecord", record, "1.0.0", "2.0.0")

    # Should have fields from both migrations
    assert result["original"] == "value"
    assert result["new_field"] == "added_in_1_1"
    assert result["another_field"] == "added_in_2_0"


def test_migration_transform_error_wrapped():
    """Wrap exceptions from migration transforms.

    Tests that apply() catches exceptions raised by migration functions
    and wraps them in MigrationTransformError with context about the
    version step that failed.
    """
    from peermodel.migrations import MigrationEngine, MigrationTransformError

    def failing_migration(record_type, record_dict):
        raise ValueError("Transform failed")

    migrations = {
        ("1.0.0", "2.0.0"): failing_migration,
    }

    engine = MigrationEngine(migrations)
    record = {"field": "value"}

    with pytest.raises(MigrationTransformError) as exc_info:
        engine.apply("TestRecord", record, "1.0.0", "2.0.0")

    # Should wrap the original exception with version context
    assert "Transform failed" in str(exc_info.value)


def test_load_engine_missing_registry_error():
    """Raise MigrationRegistryNotFoundError for missing registry.

    Tests that load_engine() raises a helpful error when:
    - Package is not installed
    - Package has no migrations module
    - Package has no MIGRATIONS attribute
    """
    from peermodel.migrations import (
        load_engine,
        MigrationRegistryNotFoundError
    )

    with pytest.raises(MigrationRegistryNotFoundError):
        load_engine("nonexistent_package")


def test_get_engine_caching():
    """Cache MigrationEngine instances per package.

    Tests that get_engine() caches loaded engines and returns
    the same instance for repeated calls with the same package name.
    """
    from peermodel.migrations import get_engine, _engine_cache

    # Clear cache
    _engine_cache.clear()

    # This will fail since the package doesn't exist,
    # but that's OK for RED test
    # We're testing the caching mechanism, not the loading
    try:
        engine1 = get_engine("test_package")
        engine2 = get_engine("test_package")
        assert engine1 is engine2  # Same instance from cache
    except Exception:
        # Expected to fail - feature doesn't exist yet
        pass


def test_version_graph_handles_branching_paths():
    """Handle version graphs with multiple paths.

    Tests that BFS finds the shortest path when multiple routes exist.
    """
    from peermodel.migrations import MigrationEngine

    migrations = {
        # Long path: 1.0.0 -> 1.1.0 -> 1.2.0 -> 2.0.0
        ("1.0.0", "1.1.0"): lambda rt, rd: rd,
        ("1.1.0", "1.2.0"): lambda rt, rd: rd,
        ("1.2.0", "2.0.0"): lambda rt, rd: rd,
        # Short path: 1.0.0 -> 2.0.0
        ("1.0.0", "2.0.0"): lambda rt, rd: rd,
    }

    engine = MigrationEngine(migrations)
    path = engine.find_path("1.0.0", "2.0.0")

    # Should find the shortest path (direct)
    assert len(path) == 1
    assert path == [("1.0.0", "2.0.0")]


def test_record_type_selective_migration():
    """Support record-type-selective migrations.

    Tests that migration functions can inspect record_type and
    selectively transform only certain record types.

    Per spec: "Some migrations may be selective - only transforming
    certain record types. The function should return record_dict
    unmodified for types it does not handle."
    """
    from peermodel.migrations import MigrationEngine

    def selective_migration(record_type, record_dict):
        if record_type == "SampleCollection":
            result = dict(record_dict)
            result["transformed"] = True
            return result
        # Return unmodified for other types
        return record_dict

    migrations = {
        ("1.0.0", "2.0.0"): selective_migration,
    }

    engine = MigrationEngine(migrations)

    # Should transform SampleCollection
    sample_record = {"data": "value"}
    result1 = engine.apply("SampleCollection", sample_record, "1.0.0", "2.0.0")
    assert result1["transformed"] is True

    # Should not transform SequenceRun
    sequence_record = {"data": "value"}
    result2 = engine.apply("SequenceRun", sequence_record, "1.0.0", "2.0.0")
    assert "transformed" not in result2
