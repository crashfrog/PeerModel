# Migrations

This directory contains data migration scripts for {{ cookiecutter.project_name }}.

## Overview

Migrations allow you to transform records from one schema version to another. This is essential when you need to change your data model while preserving existing data.

## Creating a New Migration

Use the `make migration` command to generate a migration stub:

```bash
make migration FROM=1.0.0 TO=1.1.0
```

Or directly with the scaffolder script:

```bash
python scripts/new_migration.py --from 1.0.0 --to 1.1.0
```

This creates a new file `migrations/v1_0_to_v1_1.py` with a template migration function.

## Implementing a Migration

Edit the generated migration file to implement your transformation logic:

```python
def migrate(record_type: str, record_dict: dict) -> dict:
    """Transform a record from 1.0.0 to 1.1.0."""

    # Example: Add a new field
    record_dict["new_field"] = "default_value"

    # Example: Rename a field
    if "old_name" in record_dict:
        record_dict["new_name"] = record_dict.pop("old_name")

    # Example: Type-specific transformations
    if record_type == "MyModel":
        # Apply model-specific changes
        pass

    return record_dict
```

## Registering a Migration

After implementing your migration, register it in `migrations/registry.py`:

```python
from .v1_0_to_v1_1 import migrate as migrate_v1_0_to_v1_1

MIGRATIONS[("1.0.0", "1.1.0")] = migrate_v1_0_to_v1_1
```

The registry maps version transitions to migration functions. The migration system uses this registry to apply the correct transformations.

## Testing Migrations

Always test your migrations thoroughly:

1. **Create test data** in the old format
2. **Run the migration** function with your test data
3. **Verify the output** matches the expected new format
4. **Test edge cases** (missing fields, null values, nested objects)
5. **Test error handling** (invalid data, unexpected types)

Example test structure:

```python
def test_v1_0_to_v1_1_migration():
    """Test migration from 1.0.0 to 1.1.0."""
    from {{ cookiecutter.pkg_name }}.migrations.v1_0_to_v1_1 import migrate

    # Arrange: Create old format record
    old_record = {
        "id": "123",
        "old_field": "value"
    }

    # Act: Run migration
    new_record = migrate("MyModel", old_record)

    # Assert: Verify new format
    assert "new_field" in new_record
    assert new_record["new_field"] == "default_value"
```

## Migration Best Practices

1. **Keep migrations small** - One migration per version increment
2. **Make migrations idempotent** - Running twice should be safe
3. **Test thoroughly** - Migrations run on production data
4. **Document changes** - Explain why the migration is needed
5. **Handle missing fields** - Use `.get()` with defaults
6. **Preserve data** - Don't delete fields unless necessary
7. **Version carefully** - Follow semantic versioning

## Migration Registry

The `registry.py` file contains the `MIGRATIONS` dictionary that maps version transitions to migration functions:

```python
MIGRATIONS = {
    ("1.0.0", "1.1.0"): migrate_v1_0_to_v1_1,
    ("1.1.0", "1.2.0"): migrate_v1_1_to_v1_2,
    # Add more migrations here
}
```

The migration system can automatically chain migrations to transform records across multiple versions.

## Troubleshooting

**Migration file not found**
- Ensure you're running `make migration` from the project root
- Check that the migrations directory exists

**Import errors**
- Make sure `__init__.py` exists in the migrations directory
- Verify the migration is registered in `registry.py`
- Check your Python path includes the project root

**Migration not applied**
- Verify the version numbers in the registry match exactly
- Check that the migration function has the correct signature
- Look for exceptions in the migration function

## See Also

- PeerModel migration specification: [IMPLEMENTATION_MIGRATION_SPEC.md](https://github.com/crashfrog/peermodel)
- Migration system design: See the parent project documentation
