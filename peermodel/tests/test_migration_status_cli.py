#!/usr/bin/env python

"""Tests for migration status CLI command (Issue #35).

This module tests the `prmdl migrate status` command which provides
visibility into the version distribution of records in the database
and the available migration paths.
"""

import pytest
import sqlite3
from click.testing import CliRunner


@pytest.fixture
def test_db(tmp_path):
    """Create a test SQLite database with version tracking."""
    db_path = tmp_path / "test_index.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create a sample indexed table with _schema_version column
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS SampleRecord (
            _record_id TEXT PRIMARY KEY,
            _op_id TEXT,
            _sequence INTEGER,
            _timestamp INTEGER,
            _head_cid TEXT,
            _tombstoned INTEGER,
            _schema_version TEXT,
            sample_field TEXT
        )
    """)

    # Create another sample table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS SequenceRun (
            _record_id TEXT PRIMARY KEY,
            _op_id TEXT,
            _sequence INTEGER,
            _timestamp INTEGER,
            _head_cid TEXT,
            _tombstoned INTEGER,
            _schema_version TEXT,
            run_name TEXT
        )
    """)

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def populated_db(test_db):
    """Populate test database with records at different versions."""
    conn = sqlite3.connect(str(test_db))
    cursor = conn.cursor()

    # Insert SampleRecord at different versions
    cursor.execute("""
        INSERT INTO SampleRecord
        (_record_id, _schema_version, sample_field, _tombstoned)
        VALUES (?, ?, ?, ?)
    """, ("rec1", "1.0.0", "data1", 0))

    cursor.execute("""
        INSERT INTO SampleRecord
        (_record_id, _schema_version, sample_field, _tombstoned)
        VALUES (?, ?, ?, ?)
    """, ("rec2", "1.0.0", "data2", 0))

    cursor.execute("""
        INSERT INTO SampleRecord
        (_record_id, _schema_version, sample_field, _tombstoned)
        VALUES (?, ?, ?, ?)
    """, ("rec3", "2.0.0", "data3", 0))

    cursor.execute("""
        INSERT INTO SampleRecord
        (_record_id, _schema_version, sample_field, _tombstoned)
        VALUES (?, ?, ?, ?)
    """, ("rec4", "2.1.0", "data4", 0))

    # Insert SequenceRun at different versions
    cursor.execute("""
        INSERT INTO SequenceRun
        (_record_id, _schema_version, run_name, _tombstoned)
        VALUES (?, ?, ?, ?)
    """, ("run1", "1.0.0", "run_a", 0))

    cursor.execute("""
        INSERT INTO SequenceRun
        (_record_id, _schema_version, run_name, _tombstoned)
        VALUES (?, ?, ?, ?)
    """, ("run2", "1.1.0", "run_b", 0))

    cursor.execute("""
        INSERT INTO SequenceRun
        (_record_id, _schema_version, run_name, _tombstoned)
        VALUES (?, ?, ?, ?)
    """, ("run3", "2.0.0", "run_c", 0))

    conn.commit()
    conn.close()

    return test_db


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.mark.issue_35
def test_query_version_distribution_from_sqlite(populated_db):
    """Query version distribution per record type from SQLite index.

    Tests that the system can query the _schema_version column
    to determine how many records of each type exist at each version.

    Acceptance criteria:
    - Query version distribution from SQLite
    """
    from peermodel.migrations import query_version_distribution

    # Query should return dict mapping record_type -> version -> count
    distribution = query_version_distribution(str(populated_db))

    # Should have both record types
    assert "SampleRecord" in distribution
    assert "SequenceRun" in distribution

    # Should have correct counts per version
    assert distribution["SampleRecord"]["1.0.0"] == 2
    assert distribution["SampleRecord"]["2.0.0"] == 1
    assert distribution["SampleRecord"]["2.1.0"] == 1

    assert distribution["SequenceRun"]["1.0.0"] == 1
    assert distribution["SequenceRun"]["1.1.0"] == 1
    assert distribution["SequenceRun"]["2.0.0"] == 1


@pytest.mark.issue_35
def test_query_version_distribution_excludes_tombstoned(test_db):
    """Version distribution should exclude tombstoned records.

    Tests that records marked as tombstoned (deleted) are not
    counted in the version distribution.
    """
    from peermodel.migrations import query_version_distribution

    conn = sqlite3.connect(str(test_db))
    cursor = conn.cursor()

    # Insert mix of active and tombstoned records
    cursor.execute("""
        INSERT INTO SampleRecord
        (_record_id, _schema_version, sample_field, _tombstoned)
        VALUES (?, ?, ?, ?)
    """, ("rec1", "1.0.0", "data1", 0))

    cursor.execute("""
        INSERT INTO SampleRecord
        (_record_id, _schema_version, sample_field, _tombstoned)
        VALUES (?, ?, ?, ?)
    """, ("rec2", "1.0.0", "data2", 1))  # tombstoned

    conn.commit()
    conn.close()

    distribution = query_version_distribution(str(test_db))

    # Should only count non-tombstoned record
    assert distribution["SampleRecord"]["1.0.0"] == 1


@pytest.mark.issue_35
def test_display_version_counts_and_percentages(cli_runner, populated_db):
    """Display version counts with percentages for each record type.

    Tests that the CLI output shows both absolute counts and
    percentages for each version of each record type.

    Acceptance criteria:
    - Display version counts + percentages
    """
    from peermodel.cli import cli

    result = cli_runner.invoke(cli, ['migrate', 'status', '--db', str(populated_db)])

    # Command should succeed
    assert result.exit_code == 0

    # Output should contain record type headers
    assert "SampleRecord" in result.output
    assert "SequenceRun" in result.output

    # Output should show version counts
    assert "1.0.0" in result.output
    assert "2.0.0" in result.output

    # Output should show counts (2 records at version 1.0.0 for SampleRecord)
    assert "2" in result.output or "50%" in result.output

    # Output should show percentages
    # SampleRecord: 2/4 = 50% at 1.0.0, 1/4 = 25% at 2.0.0, 1/4 = 25% at 2.1.0
    assert "%" in result.output


@pytest.mark.issue_35
def test_show_available_migration_paths(cli_runner, populated_db):
    """Show available migration paths for each version.

    Tests that the CLI output indicates which migration paths
    exist for upgrading records from each version.

    Acceptance criteria:
    - Show available migration paths
    """
    from peermodel.cli import cli

    # Assume there's a migration registry with some paths
    # (This test expects the command to fail since the migration
    # registry doesn't exist yet - RED phase)
    result = cli_runner.invoke(cli, ['migrate', 'status', '--db', str(populated_db)])

    # Should show migration path information
    # e.g., "1.0.0 -> 2.0.0 (available)" or "1.0.0 -> 1.1.0 -> 2.0.0"
    assert result.exit_code == 0

    # Output should indicate migration availability
    # (exact format TBD by implementation)
    output_lower = result.output.lower()
    assert any(keyword in output_lower for keyword in
               ['path', 'migration', 'available', 'upgrade', 'migrate to'])


@pytest.mark.issue_35
def test_report_estimated_records_to_migrate(cli_runner, populated_db):
    """Report estimated number of records needing migration.

    Tests that the CLI output summarizes how many records
    would need to be migrated to reach the latest version.

    Acceptance criteria:
    - Report estimated records to migrate
    """
    from peermodel.cli import cli

    result = cli_runner.invoke(cli, ['migrate', 'status', '--db', str(populated_db)])

    assert result.exit_code == 0

    # Output should include summary of records needing migration
    # e.g., "3 records need migration" or "3/7 records (43%) outdated"
    output_lower = result.output.lower()
    assert any(keyword in output_lower for keyword in
               ['need', 'outdated', 'to migrate', 'upgrade'])

    # Should show numeric counts
    # SampleRecord: 3 records at old versions (1.0.0, 2.0.0) if 2.1.0 is latest
    # SequenceRun: 2 records at old versions (1.0.0, 1.1.0) if 2.0.0 is latest
    assert any(str(num) in result.output for num in [2, 3, 5])


@pytest.mark.issue_35
def test_cli_output_format_table(cli_runner, populated_db):
    """Output should be formatted as a readable table.

    Tests that the CLI output is well-formatted and easy to read,
    typically as a table with aligned columns.

    Acceptance criteria:
    - Tests: CLI output format
    """
    from peermodel.cli import cli

    result = cli_runner.invoke(cli, ['migrate', 'status', '--db', str(populated_db)])

    assert result.exit_code == 0

    # Output should have some structure (headers, separators, alignment)
    lines = result.output.split('\n')

    # Should have multiple lines (not just one big blob)
    assert len(lines) > 3

    # Should have some kind of header or separator
    # (dashes, equals, or similar formatting)
    has_formatting = any(
        set(line.strip()) <= {'-', '=', '_', '|', ' ', '+'}
        for line in lines
        if line.strip()
    )
    assert has_formatting or "Record Type" in result.output


@pytest.mark.issue_35
def test_cli_output_format_json_option(cli_runner, populated_db):
    """Support JSON output format for programmatic use.

    Tests that the CLI supports a --json flag for machine-readable output.
    """
    from peermodel.cli import cli
    import json

    result = cli_runner.invoke(cli, ['migrate', 'status', '--db', str(populated_db), '--json'])

    assert result.exit_code == 0

    # Should be valid JSON
    data = json.loads(result.output)

    # Should have structured data
    assert isinstance(data, dict)
    assert "SampleRecord" in data or "record_types" in data


@pytest.mark.issue_35
def test_status_with_no_records(cli_runner, test_db):
    """Handle empty database gracefully.

    Tests that the status command works when database has no records.
    """
    from peermodel.cli import cli

    result = cli_runner.invoke(cli, ['migrate', 'status', '--db', str(test_db)])

    assert result.exit_code == 0

    # Should indicate no records
    output_lower = result.output.lower()
    assert any(keyword in output_lower for keyword in
               ['no records', 'empty', '0 records'])


@pytest.mark.issue_35
def test_status_with_single_version(cli_runner, test_db):
    """Handle database where all records are at same version.

    Tests output when all records are already at the latest version.
    """
    from peermodel.cli import cli

    conn = sqlite3.connect(str(test_db))
    cursor = conn.cursor()

    # Insert all records at same version
    cursor.execute("""
        INSERT INTO SampleRecord
        (_record_id, _schema_version, sample_field, _tombstoned)
        VALUES (?, ?, ?, ?)
    """, ("rec1", "2.0.0", "data1", 0))

    cursor.execute("""
        INSERT INTO SampleRecord
        (_record_id, _schema_version, sample_field, _tombstoned)
        VALUES (?, ?, ?, ?)
    """, ("rec2", "2.0.0", "data2", 0))

    conn.commit()
    conn.close()

    result = cli_runner.invoke(cli, ['migrate', 'status', '--db', str(test_db)])

    assert result.exit_code == 0

    # Should indicate all records are current
    output_lower = result.output.lower()
    assert "100%" in result.output or any(
        keyword in output_lower for keyword in
        ['up to date', 'current', 'no migration needed']
    )


@pytest.mark.issue_35
def test_status_migration_path_with_engine(cli_runner, populated_db, monkeypatch):
    """Show migration paths using actual MigrationEngine.

    Tests that the status command integrates with MigrationEngine
    to show actual migration paths from the registry.
    """
    from peermodel.cli import cli
    from peermodel.migrations import MigrationEngine

    # Mock a migration engine with some paths
    def mock_get_engine(package_name):
        migrations = {
            ("1.0.0", "1.1.0"): lambda rt, rd: rd,
            ("1.1.0", "2.0.0"): lambda rt, rd: rd,
            ("2.0.0", "2.1.0"): lambda rt, rd: rd,
        }
        return MigrationEngine(migrations)

    # Monkeypatch get_engine to return our mock
    monkeypatch.setattr('peermodel.migrations.get_engine', mock_get_engine)

    result = cli_runner.invoke(cli, ['migrate', 'status', '--db', str(populated_db)])

    assert result.exit_code == 0

    # Should show specific migration paths
    # e.g., "1.0.0 -> 1.1.0 -> 2.0.0"
    assert "->" in result.output or "→" in result.output


@pytest.mark.issue_35
def test_status_with_missing_migration_path(cli_runner, populated_db, monkeypatch):
    """Indicate when no migration path exists.

    Tests that the status command warns when records exist at a version
    that has no migration path to the latest version.
    """
    from peermodel.cli import cli
    from peermodel.migrations import MigrationEngine

    # Mock engine with a gap (no path from 1.0.0 to 2.x)
    def mock_get_engine(package_name):
        migrations = {
            ("2.0.0", "2.1.0"): lambda rt, rd: rd,
            # Missing path from 1.x to 2.x
        }
        return MigrationEngine(migrations)

    monkeypatch.setattr('peermodel.migrations.get_engine', mock_get_engine)

    result = cli_runner.invoke(cli, ['migrate', 'status', '--db', str(populated_db)])

    assert result.exit_code == 0

    # Should warn about missing paths
    output_lower = result.output.lower()
    assert any(keyword in output_lower for keyword in
               ['no path', 'missing', 'unavailable', 'warning', 'error'])


@pytest.mark.issue_35
def test_status_filters_by_record_type(cli_runner, populated_db):
    """Support filtering status by record type.

    Tests that the --type flag filters output to a specific record type.
    """
    from peermodel.cli import cli

    result = cli_runner.invoke(cli, [
        'migrate', 'status',
        '--db', str(populated_db),
        '--type', 'SampleRecord'
    ])

    assert result.exit_code == 0

    # Should only show SampleRecord
    assert "SampleRecord" in result.output
    assert "SequenceRun" not in result.output


@pytest.mark.issue_35
def test_status_shows_latest_version_per_type(cli_runner, populated_db):
    """Indicate the latest version for each record type.

    Tests that the status output identifies which version is
    considered "latest" for each record type.
    """
    from peermodel.cli import cli

    result = cli_runner.invoke(cli, ['migrate', 'status', '--db', str(populated_db)])

    assert result.exit_code == 0

    # Should indicate latest version
    output_lower = result.output.lower()
    assert any(keyword in output_lower for keyword in
               ['latest', 'current', 'target'])

    # Should show version numbers associated with "latest"
    # SampleRecord latest: 2.1.0
    # SequenceRun latest: 2.0.0
    assert "2.1.0" in result.output or "2.0.0" in result.output


@pytest.mark.issue_35
def test_query_version_distribution_implementation():
    """Implementation detail test for query_version_distribution function.

    Tests the actual SQL query logic that aggregates version counts.
    This is a lower-level test to ensure the query is correct.
    """
    from peermodel.migrations import query_version_distribution
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        conn = sqlite3.connect(tmp.name)
        cursor = conn.cursor()

        # Create table
        cursor.execute("""
            CREATE TABLE TestModel (
                _record_id TEXT PRIMARY KEY,
                _schema_version TEXT,
                _tombstoned INTEGER
            )
        """)

        # Insert test data
        cursor.execute("""
            INSERT INTO TestModel (_record_id, _schema_version, _tombstoned)
            VALUES ('r1', '1.0.0', 0), ('r2', '1.0.0', 0), ('r3', '2.0.0', 0)
        """)

        conn.commit()
        conn.close()

        # Query distribution
        result = query_version_distribution(tmp.name)

        # Should return correct structure
        assert result["TestModel"]["1.0.0"] == 2
        assert result["TestModel"]["2.0.0"] == 1


@pytest.mark.issue_35
def test_status_command_requires_db_path(cli_runner):
    """Command should fail gracefully without database path.

    Tests error handling when --db flag is missing.
    """
    from peermodel.cli import cli

    result = cli_runner.invoke(cli, ['migrate', 'status'])

    # Should fail with helpful error
    assert result.exit_code != 0

    output_lower = result.output.lower()
    assert any(keyword in output_lower for keyword in
               ['required', 'missing', 'database', '--db'])


@pytest.mark.issue_35
def test_status_handles_nonexistent_db(cli_runner, tmp_path):
    """Command should fail gracefully for nonexistent database.

    Tests error handling when database file doesn't exist.
    """
    from peermodel.cli import cli

    fake_db = tmp_path / "nonexistent.db"
    result = cli_runner.invoke(cli, ['migrate', 'status', '--db', str(fake_db)])

    # Should fail with helpful error — "No such command 'migrate'" does NOT count;
    # the error must name the missing file, not the missing command.
    assert result.exit_code != 0
    assert "No such command" not in result.output

    output_lower = result.output.lower()
    assert any(keyword in output_lower for keyword in
               ['not found', 'does not exist'])
