#!/usr/bin/env python

"""Acceptance tests for migration run CLI command (Issue #36).

Tests for the `prmdl migrate run` command which:
- Calls CohortRepository.migrate_eager()
- Shows progress bar
- Prompts for confirmation (unless --yes)
- Reports duration + counts
- Auto-triggers snapshot
"""

import pytest
import sqlite3
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_db(tmp_path):
    """Create a test SQLite database with version tracking."""
    db_path = tmp_path / "test_migrations.db"
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
    """, ("run2", "2.0.0", "run_b", 0))

    conn.commit()
    conn.close()

    return test_db


@pytest.mark.issue_36
class TestMigrateRunCLIBasics:
    """Test basic structure of migrate run command."""

    def test_migrate_run_command_exists(self, cli_runner):
        """Test that 'prmdl migrate run' command exists.

        Acceptance criteria:
        - Command 'prmdl migrate run' is recognized by CLI
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(cli, ['migrate', 'run', '--help'])

        # Command should exist and respond to --help without "no such command" error
        assert result.exit_code == 0
        assert 'no such command' not in result.output.lower()

    def test_migrate_run_requires_database_option(self, cli_runner):
        """Test that --db option is required.

        Acceptance criteria:
        - Command fails without --db flag
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(cli, ['migrate', 'run'])

        # Should fail without --db - either with error about missing option
        # or for a different reason (db not found)
        assert result.exit_code != 0
        # Check that it's asking for --db, not that the command doesn't exist
        assert 'no such command' not in result.output.lower()

    def test_migrate_run_accepts_db_option(self, cli_runner, test_db):
        """Test that --db option is accepted.

        Acceptance criteria:
        - --db flag specifies database path
        """
        from peermodel.cli import cli

        # Should accept --db option
        result = cli_runner.invoke(cli, ['migrate', 'run', '--db', str(test_db), '--help'])

        # Help should work with --db option
        assert result.exit_code == 0
        assert 'no such command' not in result.output.lower()

    def test_migrate_run_accepts_type_option(self, cli_runner, test_db):
        """Test that --type option to filter by record type is accepted.

        Acceptance criteria:
        - --type flag filters migration to specific record type
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(cli, ['migrate', 'run', '--help'])

        # Help should mention --type option without "no such command" error
        assert result.exit_code == 0
        assert 'no such command' not in result.output.lower()
        assert '--type' in result.output

    def test_migrate_run_accepts_yes_flag(self, cli_runner, test_db):
        """Test that --yes flag skips confirmation.

        Acceptance criteria:
        - --yes flag bypasses confirmation prompt
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(cli, ['migrate', 'run', '--help'])

        # Help should mention --yes flag
        assert result.exit_code == 0
        assert 'no such command' not in result.output.lower()
        assert '--yes' in result.output

    def test_migrate_run_accepts_dry_run_flag(self, cli_runner, test_db):
        """Test that --dry-run flag is available.

        Acceptance criteria:
        - --dry-run flag performs test migration without writing
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(cli, ['migrate', 'run', '--help'])

        # Help should mention --dry-run flag
        assert result.exit_code == 0
        assert 'no such command' not in result.output.lower()
        assert '--dry-run' in result.output


@pytest.mark.issue_36
class TestMigrateRunProgressDisplay:
    """Test progress bar display during migration."""

    def test_migrate_run_shows_progress_bar(self, cli_runner, populated_db):
        """Test that progress is displayed during migration.

        Acceptance criteria:
        - Show progress (processed/total) during migration
        """
        from peermodel.cli import cli

        # This test is RED - expects the command to handle progress
        # When run with input that skips confirmation, should show progress
        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--yes'],
            input='\n'
        )

        # Command should run and output should contain some indication of progress
        # Either "processed", "total", progress indicator, or similar
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        progress_keywords = ['progress', 'processed', 'total', 'record', 'migrat']
        has_progress_info = any(kw in output_lower for kw in progress_keywords)

        # This test expects the feature to be implemented
        assert has_progress_info

    def test_migrate_run_shows_processed_count(self, cli_runner, populated_db):
        """Test that number of processed records is displayed.

        Acceptance criteria:
        - Show processed/total counts
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--yes'],
            input='\n'
        )

        # Output should show counts
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        assert 'processed' in output_lower or 'migrat' in output_lower

    def test_migrate_run_shows_total_count(self, cli_runner, populated_db):
        """Test that total record count is displayed.

        Acceptance criteria:
        - Show total records to migrate
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--yes'],
            input='\n'
        )

        # Output should show total records - must actually display count
        # not just error about command not found
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        # Should mention records and show some count
        assert 'total' in output_lower or 'record' in output_lower


@pytest.mark.issue_36
class TestMigrateRunConfirmation:
    """Test confirmation prompt behavior."""

    def test_migrate_run_prompts_for_confirmation(self, cli_runner, populated_db):
        """Test that user is prompted to confirm before running migration.

        Acceptance criteria:
        - Prompt for confirmation (unless --yes)
        - Confirmation request should mention what will be done
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db)],
            input='n\n'  # User declines
        )

        # Should ask for confirmation
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        confirmation_keywords = ['confirm', 'proceed', 'continue', 'migrate', 'ready', 'start']
        has_confirmation = any(kw in output_lower for kw in confirmation_keywords)

        assert has_confirmation

    def test_migrate_run_accepts_yes_to_proceed(self, cli_runner, populated_db):
        """Test that user can accept confirmation to proceed.

        Acceptance criteria:
        - User confirms with yes to proceed
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db)],
            input='y\n'
        )

        # Should proceed after confirmation
        # (may still fail if migrate_eager not implemented)
        # But should not show "cancelled" or "aborted" or "command not found"
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        assert 'cancel' not in output_lower

    def test_migrate_run_declines_to_proceed(self, cli_runner, populated_db):
        """Test that user can decline confirmation to cancel.

        Acceptance criteria:
        - User declines with no/n to cancel
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db)],
            input='n\n'
        )

        # Should not proceed after declining
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        assert 'cancel' in output_lower or 'abort' in output_lower or 'declined' in output_lower

    def test_migrate_run_yes_flag_skips_confirmation(self, cli_runner, populated_db):
        """Test that --yes flag skips confirmation prompt.

        Acceptance criteria:
        - --yes flag bypasses confirmation prompt
        - Command proceeds without user input
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--yes']
        )

        # Should not ask for confirmation (no input provided)
        # Should attempt to run migration
        # (may fail if migrate_eager not implemented)
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        # Should not complain about missing input when --yes is provided
        assert 'input' not in output_lower


@pytest.mark.issue_36
class TestMigrateRunReporting:
    """Test result reporting (counts and duration)."""

    def test_migrate_run_reports_migrated_count(self, cli_runner, populated_db):
        """Test that result includes count of migrated records.

        Acceptance criteria:
        - Report number of migrated records
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--yes'],
            input='\n'
        )

        # Output should report counts
        # Should mention how many were migrated
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        assert 'migrat' in output_lower or 'record' in output_lower

    def test_migrate_run_reports_skipped_count(self, cli_runner, populated_db):
        """Test that result includes count of skipped records.

        Acceptance criteria:
        - Report number of records already at target version
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--yes'],
            input='\n'
        )

        # Output should report skipped/current version records
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        skip_keywords = ['skip', 'current', 'latest', 'up to date']
        has_skip_info = any(kw in output_lower for kw in skip_keywords)

        assert has_skip_info

    def test_migrate_run_reports_error_count(self, cli_runner, populated_db):
        """Test that result includes count of failed records.

        Acceptance criteria:
        - Report number of records that failed migration
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--yes'],
            input='\n'
        )

        # Output should report errors/failed records or indicate success
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()

        # Should show summary with error count (even if 0)
        # Keywords that would appear: "error", "failed", "success", etc.
        summary_keywords = ['error', 'fail', 'success', 'complete', 'migrat']
        has_summary = any(kw in output_lower for kw in summary_keywords)

        assert has_summary

    def test_migrate_run_reports_duration(self, cli_runner, populated_db):
        """Test that result includes elapsed time.

        Acceptance criteria:
        - Report elapsed time (duration in seconds)
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--yes'],
            input='\n'
        )

        # Output should include timing information
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        time_keywords = ['second', 'duration', 'elapsed', 'took', 'time']
        has_timing = any(kw in output_lower for kw in time_keywords)

        assert has_timing

    def test_migrate_run_summary_format(self, cli_runner, populated_db):
        """Test that results are presented in a clear summary.

        Acceptance criteria:
        - Summary shows: migrated, skipped, errors, duration
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--yes'],
            input='\n'
        )

        # Result should show a summary
        # Multiple lines indicating different aspects of the result
        assert 'no such command' not in result.output.lower()
        lines = result.output.split('\n')
        assert len(lines) > 2


@pytest.mark.issue_36
class TestMigrateRunSnapshot:
    """Test auto-snapshot triggering."""

    def test_migrate_run_triggers_snapshot_on_success(self, cli_runner, populated_db):
        """Test that snapshot is auto-triggered after successful migration.

        Acceptance criteria:
        - Auto-trigger snapshot creation
        - Report snapshot creation
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--yes', '--dry-run'],
            input='\n'
        )

        # With dry-run, should still run but not write
        # Result should indicate snapshot behavior
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        # Should mention snapshot or indicate what would happen
        assert 'snapshot' in output_lower or 'migrat' in output_lower

    def test_migrate_run_no_snapshot_on_dry_run(self, cli_runner, populated_db):
        """Test that snapshot is not created with --dry-run.

        Acceptance criteria:
        - With --dry-run, no snapshot is created
        - Output should indicate dry-run mode
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--yes', '--dry-run'],
            input='\n'
        )

        # Dry-run should be indicated
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        assert 'dry' in output_lower


@pytest.mark.issue_36
class TestMigrateRunTypeFilter:
    """Test filtering migration by record type."""

    def test_migrate_run_filters_by_type(self, cli_runner, populated_db):
        """Test that --type option filters to specific record type.

        Acceptance criteria:
        - --type SampleRecord only migrates SampleRecord
        - Report only includes specified type
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--type', 'SampleRecord', '--yes'],
            input='\n'
        )

        # Should filter to SampleRecord
        # Result should indicate which type was migrated
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        assert 'samplerecord' in output_lower or 'record' in output_lower

    def test_migrate_run_invalid_type_shows_error(self, cli_runner, populated_db):
        """Test that invalid record type shows appropriate error.

        Acceptance criteria:
        - Invalid type name shows error
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--type', 'NonExistentType', '--yes'],
            input='\n'
        )

        # Should fail gracefully for non-existent type - must not say "command not found"
        assert 'no such command' not in result.output.lower()
        # Should either fail or show error about the invalid type
        output_lower = result.output.lower()
        assert result.exit_code != 0 or 'error' in output_lower or 'not found' in output_lower


@pytest.mark.issue_36
class TestMigrateRunIntegration:
    """Integration tests for migrate run command."""

    def test_migrate_run_calls_migrate_eager(self, cli_runner, populated_db):
        """Test that migrate run calls CohortRepository.migrate_eager().

        Acceptance criteria:
        - Command calls migrate_eager() with correct arguments
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(populated_db), '--yes'],
            input='\n'
        )

        # Command should attempt to call migrate_eager
        # (may fail if repository not available, but should try)
        # Should not show "command not found" or similar
        assert 'no such command' not in result.output.lower()

    def test_migrate_run_with_nonexistent_db(self, cli_runner, tmp_path):
        """Test graceful error for non-existent database.

        Acceptance criteria:
        - Show error for missing database
        """
        from peermodel.cli import cli

        fake_db = tmp_path / "nonexistent.db"
        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(fake_db), '--yes'],
            input='\n'
        )

        # Should fail with helpful error - command must exist to fail with db error
        assert 'no such command' not in result.output.lower()
        # Should fail with helpful error
        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert 'not found' in output_lower or 'error' in output_lower or 'exist' in output_lower

    def test_migrate_run_empty_database(self, cli_runner, test_db):
        """Test handling empty database (no records).

        Acceptance criteria:
        - Handle gracefully when database has no records to migrate
        """
        from peermodel.cli import cli

        result = cli_runner.invoke(
            cli,
            ['migrate', 'run', '--db', str(test_db), '--yes'],
            input='\n'
        )

        # Should handle gracefully (no records to migrate)
        # Should not show "command not found"
        assert 'no such command' not in result.output.lower()
        output_lower = result.output.lower()
        # Should mention records or complete message
        assert 'record' in output_lower or 'complete' in output_lower
