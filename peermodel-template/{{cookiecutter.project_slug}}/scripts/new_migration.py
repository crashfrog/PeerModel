#!/usr/bin/env python
"""Scaffolder script for creating new migration stubs.

Usage:
    python scripts/new_migration.py --from 1.0.0 --to 1.1.0
    make migration FROM=1.0.0 TO=1.1.0
"""

import argparse
import re
from pathlib import Path


MIGRATION_TEMPLATE = '''"""Migration from version {from_version} to {to_version}.

This migration transforms records from {from_version} format to
{to_version} format.

Instructions:
1. Implement the migrate() function below
2. Test your migration with sample data
3. Register it in migrations/registry.py:
   from .{module_name} import migrate
   MIGRATIONS[("{from_version}", "{to_version}")] = migrate
"""


def migrate(record_type: str, record_dict: dict) -> dict:
    """Transform a record from {from_version} to {to_version}.

    Args:
        record_type: The type name of the record being migrated
        record_dict: The record data as a dictionary

    Returns:
        The transformed record dictionary

    Example transformations:
        # Add a new field with default value
        record_dict["new_field"] = "default_value"

        # Rename a field
        if "old_field" in record_dict:
            record_dict["new_field"] = record_dict.pop("old_field")

        # Transform nested objects
        if "nested" in record_dict:
            record_dict["nested"]["updated"] = True

        # Type-specific transformations
        if record_type == "MyModelType":
            # Apply model-specific changes
            pass
    """
    # TODO: Implement your migration logic here
    # For now, return the record unchanged
    return record_dict
'''


def normalize_version(version: str) -> str:
    """Normalize version string for use in filenames.

    Args:
        version: Version string (e.g., "1.0.0", "1.2.3-alpha")

    Returns:
        Normalized version for filename (e.g., "v1_0", "v1_2_3_alpha")
    """
    # Remove common prefixes
    version = version.lstrip("vV")

    # Split by dots to handle version parts
    parts = version.split('.')

    # Remove trailing zeros from version parts (e.g., "1.0.0" -> "1.0")
    # Keep at least 2 parts for clarity
    while len(parts) > 2 and parts[-1] == '0':
        parts.pop()

    # Rejoin with dots, then replace dots and hyphens with underscores
    version = '.'.join(parts)
    version = re.sub(r'[.-]', '_', version)
    return f"v{version}"


def main():
    """Generate a new migration stub."""
    parser = argparse.ArgumentParser(
        description="Generate a migration stub file"
    )
    parser.add_argument(
        "--from", "--from-version",
        dest="from_version",
        required=True,
        help="Source version (e.g., 1.0.0)"
    )
    parser.add_argument(
        "--to", "--to-version",
        dest="to_version",
        required=True,
        help="Target version (e.g., 1.1.0)"
    )

    args = parser.parse_args()

    # Normalize version strings for filename
    from_normalized = normalize_version(args.from_version)
    to_normalized = normalize_version(args.to_version)

    # Generate module name
    module_name = f"{from_normalized}_to_{to_normalized}"
    filename = f"{module_name}.py"

    # Find the migrations directory
    # Assume script is run from project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    pkg_name = "{{ cookiecutter.pkg_name }}"
    migrations_dir = project_root / pkg_name / "migrations"

    if not migrations_dir.exists():
        print(f"Error: migrations directory not found at {migrations_dir}")
        return 1

    # Create migration file
    migration_file = migrations_dir / filename

    if migration_file.exists():
        print(f"Warning: {migration_file} already exists, skipping...")
        return 0

    # Write the migration stub
    content = MIGRATION_TEMPLATE.format(
        from_version=args.from_version,
        to_version=args.to_version,
        module_name=module_name
    )

    migration_file.write_text(content)
    print(f"Created migration stub: {migration_file}")
    print()
    print("Next steps:")
    print(f"  1. Edit {filename} to implement your migration")
    print("  2. Test the migration with sample data")
    print("  3. Register in migrations/registry.py:")
    print(f"     from .{module_name} import migrate")
    from_ver = args.from_version
    to_ver = args.to_version
    print(f'     MIGRATIONS[("{from_ver}", "{to_ver}")] = migrate')

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
