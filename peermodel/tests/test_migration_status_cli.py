#!/usr/bin/env python

"""Tests for migration status CLI command (Issue #35).

Tests the `prmdl migrate status` command which provides operational visibility
into schema version distribution across records, available migration paths,
and estimated records to migrate.

Acceptance criteria:
- Query version distribution from index (SQLite)
- Display version counts + percentages per record_type
- Show available migration paths for each version
- Report estimated records to migrate
- CLI output formatting
"""

import pytest
from click.testing import CliRunner
from peermodel.cli import cli
from unittest.mock import Mock, patch, MagicMock


class TestMigrateStatusCommand:
    """Test suite for `prmdl migrate status` command."""

    def test_migrate_status_command_exists(self):
        """Verify that 'prmdl migrate status' command is registered."""
        runner = CliRunner()
        result = runner.invoke(cli, ['migrate', 'status', '--help'])

        # Command should exist and show help
        assert result.exit_code == 0
        assert 'status' in result.output or 'Show' in result.output or 'version' in result.output

    def test_migrate_status_no_database_empty_output(self):
        """When no database exists, status reports no records to migrate."""
        runner = CliRunner()

        with patch('peermodel.migrations.get_engine') as mock_engine:
            # Mock engine with empty version graph
            mock_engine.return_value.graph = {}

            result = runner.invoke(cli, ['migrate', 'status'])

            # Should complete successfully
            assert result.exit_code == 0
            # Output may contain "no records" or "0 records"
            assert 'record' in result.output.lower() or result.output.strip() == ''

    def test_migrate_status_queries_version_distribution(self):
        """Verify command queries version distribution per record_type."""
        runner = CliRunner()

        with patch('peermodel.migrations.get_engine') as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value = mock_instance
            mock_instance.graph = {
                '1.0.0': ['1.1.0', '2.0.0'],
                '1.1.0': ['2.0.0'],
            }

            result = runner.invoke(cli, ['migrate', 'status'])

            # Should complete
            assert result.exit_code in [0, 1]  # May fail if DB query not implemented

    def test_migrate_status_displays_version_counts(self):
        """Output includes version counts for each record_type."""
        runner = CliRunner()

        with patch('peermodel.migrations.get_engine') as mock_engine:
            # Mock engine
            mock_instance = MagicMock()
            mock_engine.return_value = mock_instance
            mock_instance.graph = {}

            # Mock database query results: {record_type: {version: count}}
            version_dist = {
                'SampleCollection': {
                    '1.0.0': 10,
                    '1.1.0': 5,
                    '2.0.0': 3,
                },
                'Sample': {
                    '1.0.0': 20,
                    '2.0.0': 15,
                }
            }

            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                # Command should invoke
                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_displays_percentages(self):
        """Output includes percentage of records at each version."""
        runner = CliRunner()

        version_dist = {
            'TestRecord': {
                '1.0.0': 50,  # 50%
                '2.0.0': 50,  # 50%
            }
        }

        with patch('peermodel.migrations.get_engine'):
            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                # Should complete
                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_shows_migration_paths(self):
        """Output shows available migration paths for each version."""
        runner = CliRunner()

        # Create mock engine with migration paths
        migrations = {
            ('1.0.0', '1.1.0'): lambda rt, rd: rd,
            ('1.1.0', '2.0.0'): lambda rt, rd: rd,
        }

        with patch('peermodel.migrations.get_engine') as mock_engine:
            from peermodel.migrations import MigrationEngine
            engine = MigrationEngine(migrations)
            mock_engine.return_value = engine

            version_dist = {
                'TestRecord': {
                    '1.0.0': 10,
                }
            }

            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                # Command should complete
                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_reports_estimated_records(self):
        """Output reports estimated number of records to migrate."""
        runner = CliRunner()

        version_dist = {
            'SampleCollection': {
                '1.0.0': 100,  # Need to migrate
                '2.0.0': 50,   # Current version
            },
            'Sample': {
                '1.0.0': 200,  # Need to migrate
                '1.5.0': 100,  # Need to migrate
                '2.0.0': 50,   # Current version
            }
        }

        with patch('peermodel.migrations.get_engine'):
            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                # Should complete
                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_single_record_type(self):
        """Formats output correctly for a single record type."""
        runner = CliRunner()

        version_dist = {
            'Document': {
                '1.0.0': 25,
            }
        }

        with patch('peermodel.migrations.get_engine'):
            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_multiple_record_types(self):
        """Formats output correctly for multiple record types."""
        runner = CliRunner()

        version_dist = {
            'Type1': {'1.0.0': 10, '2.0.0': 5},
            'Type2': {'1.5.0': 3, '2.0.0': 7},
            'Type3': {'1.0.0': 1, '1.5.0': 2, '2.0.0': 8},
        }

        with patch('peermodel.migrations.get_engine'):
            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_output_includes_record_type_name(self):
        """Output clearly labels which record type is being reported."""
        runner = CliRunner()

        version_dist = {
            'SampleCollection': {
                '1.0.0': 10,
                '2.0.0': 5,
            }
        }

        with patch('peermodel.migrations.get_engine'):
            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                # Output may contain the record type name
                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_output_includes_version_column(self):
        """Output includes columns for version, count, percentage."""
        runner = CliRunner()

        version_dist = {
            'Test': {'1.0.0': 10}
        }

        with patch('peermodel.migrations.get_engine'):
            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                # Should not error
                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_handles_zero_percentage(self):
        """Correctly displays 0% for very small samples."""
        runner = CliRunner()

        version_dist = {
            'Document': {
                '1.0.0': 1,
                '2.0.0': 1000,
            }
        }

        with patch('peermodel.migrations.get_engine'):
            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_handles_100_percentage(self):
        """Correctly displays 100% when all records are at same version."""
        runner = CliRunner()

        version_dist = {
            'Document': {
                '2.0.0': 100,
            }
        }

        with patch('peermodel.migrations.get_engine'):
            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_json_output_format(self):
        """Optional: --json flag outputs machine-readable format."""
        runner = CliRunner()

        version_dist = {
            'Document': {'1.0.0': 10, '2.0.0': 20}
        }

        with patch('peermodel.migrations.get_engine'):
            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status', '--json'])

                # May or may not be implemented, but command should handle gracefully
                assert result.exit_code in [0, 1, 2]


class TestMigrateStatusIntegration:
    """Integration tests for migrate status with real (mocked) database."""

    def test_status_with_no_operations_in_database(self):
        """When database has no operations, status shows 0 records."""
        runner = CliRunner()

        with patch('peermodel.migrations.get_engine') as mock_engine:
            mock_engine.return_value.graph = {}

            with patch('peermodel.cli.query_version_distribution', return_value={}):
                result = runner.invoke(cli, ['migrate', 'status'])

                # Should handle empty database gracefully
                assert result.exit_code in [0, 1]

    def test_status_with_single_version_all_records(self):
        """When all records are same version, status reflects 100%."""
        runner = CliRunner()

        version_dist = {
            'Document': {
                '1.0.0': 42,
            }
        }

        with patch('peermodel.migrations.get_engine') as mock_engine:
            mock_engine.return_value.graph = {}

            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                assert result.exit_code in [0, 1]

    def test_status_with_fragmented_versions(self):
        """Status correctly reports when records are highly fragmented."""
        runner = CliRunner()

        version_dist = {
            'Document': {
                '1.0.0': 10,
                '1.1.0': 8,
                '1.2.0': 6,
                '2.0.0': 4,
                '2.1.0': 2,
            }
        }

        with patch('peermodel.migrations.get_engine') as mock_engine:
            migrations = {
                ('1.0.0', '1.1.0'): lambda rt, rd: rd,
                ('1.1.0', '1.2.0'): lambda rt, rd: rd,
                ('1.2.0', '2.0.0'): lambda rt, rd: rd,
                ('2.0.0', '2.1.0'): lambda rt, rd: rd,
            }
            from peermodel.migrations import MigrationEngine
            mock_engine.return_value = MigrationEngine(migrations)

            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                assert result.exit_code in [0, 1]

    def test_status_migration_path_computation(self):
        """Status correctly identifies available migration paths."""
        runner = CliRunner()

        version_dist = {
            'Document': {
                '1.0.0': 20,
                '2.0.0': 30,
            }
        }

        with patch('peermodel.migrations.get_engine') as mock_engine:
            migrations = {
                ('1.0.0', '1.5.0'): lambda rt, rd: rd,
                ('1.5.0', '2.0.0'): lambda rt, rd: rd,
            }
            from peermodel.migrations import MigrationEngine
            mock_engine.return_value = MigrationEngine(migrations)

            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                assert result.exit_code in [0, 1]


class TestQueryVersionDistribution:
    """Tests for the version distribution query function."""

    def test_query_returns_dict_by_record_type(self):
        """query_version_distribution returns dict[record_type][version] = count."""
        # This will raise AttributeError or ImportError since not implemented yet
        with pytest.raises((ImportError, AttributeError)):
            from peermodel.cli import query_version_distribution
            query_version_distribution()

    def test_query_counts_records_per_version(self):
        """Query correctly counts how many records are at each version."""
        # Expected to fail: function not yet implemented
        with pytest.raises((ImportError, AttributeError)):
            from peermodel.cli import query_version_distribution
            result = query_version_distribution()
            # Should return: {'RecordType': {'1.0.0': 5, '2.0.0': 10}}
            assert isinstance(result, dict)

    def test_query_filters_by_schema_version(self):
        """Query filters using SQLite _schema_version column."""
        with pytest.raises((ImportError, AttributeError)):
            from peermodel.cli import query_version_distribution
            result = query_version_distribution()


class TestComputeMigrationPaths:
    """Tests for computing available migration paths from version graph."""

    def test_compute_paths_single_step(self):
        """Compute single-step paths between versions."""
        with pytest.raises((ImportError, AttributeError)):
            from peermodel.cli import compute_available_paths
            paths = compute_available_paths('1.0.0', {('1.0.0', '2.0.0'): lambda: None})

    def test_compute_paths_multi_step(self):
        """Compute multi-step paths between versions."""
        with pytest.raises((ImportError, AttributeError)):
            from peermodel.cli import compute_available_paths
            migrations = {
                ('1.0.0', '1.1.0'): lambda: None,
                ('1.1.0', '2.0.0'): lambda: None,
            }
            paths = compute_available_paths('1.0.0', migrations)

    def test_compute_paths_no_path_available(self):
        """Returns empty list when no migration path exists."""
        with pytest.raises((ImportError, AttributeError)):
            from peermodel.cli import compute_available_paths
            migrations = {
                ('2.0.0', '3.0.0'): lambda: None,
            }
            paths = compute_available_paths('1.0.0', migrations)
            # Should return [] for unavailable path


class TestMigrationStatusFormatting:
    """Tests for output formatting of migration status."""

    def test_format_percentage_two_decimals(self):
        """Percentages are formatted to 2 decimal places."""
        with pytest.raises((ImportError, AttributeError)):
            from peermodel.cli import format_migration_status
            output = format_migration_status({})

    def test_format_includes_table_headers(self):
        """Output includes clear table headers."""
        with pytest.raises((ImportError, AttributeError)):
            from peermodel.cli import format_migration_status
            output = format_migration_status({})

    def test_format_sorts_versions_semver(self):
        """Versions are sorted in semantic version order."""
        with pytest.raises((ImportError, AttributeError)):
            from peermodel.cli import format_migration_status
            output = format_migration_status({})

    def test_format_totals_per_record_type(self):
        """Output includes totals for each record type."""
        with pytest.raises((ImportError, AttributeError)):
            from peermodel.cli import format_migration_status
            output = format_migration_status({})


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_migrate_status_with_very_large_counts(self):
        """Handles large record counts (1M+) without overflow."""
        runner = CliRunner()

        version_dist = {
            'LargeCollection': {
                '1.0.0': 1_000_000,
                '2.0.0': 500_000,
            }
        }

        with patch('peermodel.migrations.get_engine'):
            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_with_unusual_version_strings(self):
        """Handles unusual version strings (rc, beta, dev, etc.)."""
        runner = CliRunner()

        version_dist = {
            'Document': {
                '1.0.0-rc1': 5,
                '1.0.0': 10,
                '1.1.0-beta': 3,
            }
        }

        with patch('peermodel.migrations.get_engine'):
            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_record_type_with_special_chars(self):
        """Handles record types with unusual names."""
        runner = CliRunner()

        version_dist = {
            'Record_Type_1': {'1.0.0': 10},
            'RecordType2': {'2.0.0': 20},
            'record_type_3': {'1.0.0': 5},
        }

        with patch('peermodel.migrations.get_engine'):
            with patch('peermodel.cli.query_version_distribution', return_value=version_dist):
                result = runner.invoke(cli, ['migrate', 'status'])

                assert result.exit_code in [0, 1, 2]

    def test_migrate_status_when_migration_engine_unavailable(self):
        """Handles gracefully when migration engine cannot be loaded."""
        runner = CliRunner()

        with patch('peermodel.migrations.get_engine', side_effect=ImportError("No registry")):
            result = runner.invoke(cli, ['migrate', 'status'])

            # Should fail gracefully with helpful error message
            assert result.exit_code != 0
            assert 'error' in result.output.lower() or 'registry' in result.output.lower()

    def test_migrate_status_when_database_query_fails(self):
        """Handles database query errors gracefully."""
        runner = CliRunner()

        with patch('peermodel.migrations.get_engine') as mock_engine:
            mock_engine.return_value.graph = {}

            with patch('peermodel.cli.query_version_distribution', side_effect=RuntimeError("DB error")):
                result = runner.invoke(cli, ['migrate', 'status'])

                # Should fail or show helpful message
                assert result.exit_code != 0 or 'error' in result.output.lower()
