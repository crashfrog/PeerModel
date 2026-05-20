"""Migration registry for {{ cookiecutter.project_name }}.

This module contains the MIGRATIONS dictionary that maps version transitions
to migration functions.

Migration Function Signature
-----------------------------
Each migration function should accept two parameters and return a dict:

    def migrate(record_type: str, record_dict: dict) -> dict:
        '''
        Transform a record from one version to another.

        Args:
            record_type: The type name of the record being migrated
            record_dict: The record data as a dictionary

        Returns:
            The transformed record dictionary
        '''
        # Apply transformations here
        return record_dict

Registering Migrations
----------------------
Add your migration functions to the MIGRATIONS dict using the format:
    MIGRATIONS[("from_version", "to_version")] = migration_function

Example:
    from .v1_0_to_v1_1 import migrate as migrate_v1_0_to_v1_1
    MIGRATIONS[("1.0.0", "1.1.0")] = migrate_v1_0_to_v1_1

Creating New Migrations
-----------------------
Use the scaffolder script to generate migration stubs:
    make migration FROM=1.0.0 TO=1.1.0

Or directly:
    python scripts/new_migration.py --from 1.0.0 --to 1.1.0

Testing Migrations
------------------
Always test your migrations with sample data:
    1. Create test records in the old format
    2. Run the migration function
    3. Verify the output matches the new format
    4. Test edge cases and error conditions
"""

# Migration registry: maps (from_version, to_version) -> migration_function
MIGRATIONS = {}

# Example (uncomment and modify when you create your first migration):
# from .v1_0_to_v1_1 import migrate as migrate_v1_0_to_v1_1
# MIGRATIONS[("1.0.0", "1.1.0")] = migrate_v1_0_to_v1_1
