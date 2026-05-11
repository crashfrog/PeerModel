# PeerModel — Schema Migration Specification

## Purpose and Scope

This document specifies the schema migration system for PeerModel. It covers:

- The conceptual model for how schema versions relate to data model package versions
- The migration registry convention that data model packages must implement
- The migration engine inside the PeerModel library that discovers and applies transforms
- The `prmdl migrate` CLI surface for operational visibility and eager migration runs
- The cookiecutter template scaffold that makes the convention discoverable for new packages

This spec should be read alongside `IMPLEMENTATION_DB_SPEC.md`. The migration engine sits between the log traversal layer and `DocumentObj._from_storage()` — it is invoked at read time by `CohortRepository.get()` and at sync time by `SyncManager` when replaying old operations.

---

## Conceptual Model

### Schema version is package version

Every `OperationRecord` carries a `schema_version` field (specified in `IMPLEMENTATION_DB_SPEC.md`). This value is the version string of the data model package that produced the record — the output of `importlib.metadata.version("your_datamodel_package")` at write time, recorded verbatim.

There is no separate migration tracking table, no Alembic-style version history, no migration lock file. The authoritative record of what schema version produced a given record is the record itself. The authoritative record of what migrations exist is the data model package's `migrations` module.

### The log is immutable; migration is a read-time operation

Old records are never modified in IPFS. A record written by version `1.0.0` stays a `1.0.0` record forever in the log. Migration happens in one of two modes:

**Lazy migration** (default): when `CohortRepository.get()` fetches a record whose `schema_version` differs from the current installed package version, the migration engine transforms the record dict in memory before passing it to `_from_storage()`. The caller receives a fully current instance. Nothing is written back to the log.

**Eager migration**: triggered explicitly via `prmdl migrate run` or programmatically via `CohortRepository.migrate_eager()`. The engine fetches old records, applies transforms, and writes new `update` OperationRecords with the current `schema_version`. This gradually modernizes the log so that future reads pay no migration cost. Old records remain in the log (immutability) but the current-state view of each record is the modernized version.

### Two kinds of schema change

**Additive changes** (minor version bump): new fields added with default values, no fields removed or renamed. No migration function is required. `_from_storage()` already handles missing fields gracefully (see Defensive Deserialization below). The migration engine recognizes an additive change by the absence of a registered transform for that version pair.

**Breaking changes** (major version bump): fields renamed, removed, split, merged, or type-changed. A migration function is required. The data model package author writes it; PeerModel invokes it.

This convention follows semantic versioning: major bumps require migration functions, minor and patch bumps do not. The migration engine enforces this: if a major version gap exists in a version path with no registered transform, it raises `MissingMigrationError` rather than silently producing a malformed record.

---

## Migration Registry Convention

Data model packages expose migrations at a well-known location: `{package}.migrations.registry`.

### Required interface

```python
# your_datamodel/migrations/registry.py

from your_datamodel.migrations import v1_0_to_v1_1, v1_1_to_v2_0

MIGRATIONS: dict[tuple[str, str], callable] = {
    ("1.0.0", "1.1.0"): v1_0_to_v1_1.migrate,
    ("1.1.0", "2.0.0"): v1_1_to_v2_0.migrate,
}
```

Each key is a `(from_version, to_version)` tuple of version strings. Each value is a callable with the signature:

```python
def migrate(record_type: str, record_dict: dict) -> dict:
    """
    Transform a record_dict from from_version to to_version.

    record_type: the DocumentObj subclass name (e.g. "SampleCollection").
      Some migrations may be selective — only transforming certain record
      types. The function should return record_dict unmodified for types
      it does not handle.
    record_dict: the raw deserialized payload dict from the OperationRecord.
      May contain unknown fields from the old schema. Must not mutate the
      input; return a new dict.
    Returns: transformed record_dict ready for the next migration step
      or for _from_storage().
    """
```

Each migration step lives in its own module for readability and testability:

```
your_datamodel/
    migrations/
        __init__.py
        registry.py
        v1_0_to_v1_1.py
        v1_1_to_v2_0.py
```

### Discovery

PeerModel discovers the registry by:

1. Reading `schema_version` from the `OperationRecord`.
2. Extracting the package name from `schema_version` metadata. Package name is stored separately in the `OperationRecord` (see Extended OperationRecord below).
3. `importlib.import_module(f"{package_name}.migrations.registry")`.
4. Reading `MIGRATIONS` from the imported module.

If the package is not installed, or has no `migrations` module, or has no `MIGRATIONS` attribute, the engine raises `MigrationRegistryNotFoundError` with a clear message directing the user to install the correct data model package version.

### Extended OperationRecord

Add one field to `OperationRecord` (specified in `IMPLEMENTATION_DB_SPEC.md`):

```python
datamodel_package: str   # PyPI package name of the data model package,
                         # e.g. "who-searo-datamodel"
                         # Set at write time from package metadata.
                         # Used by the migration engine for registry discovery.
```

This field participates in `canonical_op_bytes()` and is covered by the cohort signature.

---

## Migration Engine

### Location

`peermodel/migrations.py` — a new module in the PeerModel library.

### Version graph

The engine builds a directed graph from the `MIGRATIONS` dict: nodes are version strings, edges are `(from_version, to_version)` pairs with the transform callable as the edge weight. To migrate from version A to version C, it finds the shortest path A → B → C through the graph using BFS.

```python
class MigrationEngine:

    def __init__(self, registry: dict[tuple[str, str], callable]): ...

    def build_version_graph(self) -> dict[str, list[str]]:
        """
        Build adjacency list from MIGRATIONS keys.
        Used by find_path() for BFS traversal.
        """

    def find_path(
        self,
        from_version: str,
        to_version: str
    ) -> list[tuple[str, str]]:
        """
        Find the shortest migration path from from_version to to_version.
        Returns list of (from, to) version pairs representing each step.
        Raises MissingMigrationError if no path exists and the major
        version component of from_version differs from to_version.
        Returns empty list if from_version == to_version (no migration needed).
        If versions differ only in minor/patch and no path exists, returns
        empty list (additive change; no transform needed).
        """

    def apply(
        self,
        record_type: str,
        record_dict: dict,
        from_version: str,
        to_version: str
    ) -> dict:
        """
        Apply the migration path from from_version to to_version to record_dict.
        Calls each transform function in path order.
        Each step receives the output of the previous step.
        Returns the fully migrated record_dict.
        Does not call _from_storage(); that is the caller's responsibility.
        Raises MigrationError if any transform raises an exception,
        wrapping the original exception with version path context.
        """
```

### Integration with CohortRepository

In `repository.py`, `get()` is updated:

```python
def get(self, record_type: str, record_id: str) -> DocumentObj | None:
    # ... fetch OperationRecord from IPFS as before ...

    current_version = importlib.metadata.version(op.datamodel_package)
    if op.schema_version != current_version:
        engine = _get_engine(op.datamodel_package)   # cached per package
        record_dict = engine.apply(
            record_type,
            record_dict,
            from_version=op.schema_version,
            to_version=current_version
        )

    return DocumentObj._from_storage(db, record_id, record_dict)
```

`_get_engine(package_name)` is a module-level cache (dict) mapping package names to `MigrationEngine` instances loaded from their registry. Engines are loaded once per process lifetime and cached. If the registry module changes (e.g. during development), the process must be restarted.

### Integration with SyncManager

During log traversal in `sync.py`, `traverse()` fetches and verifies `OperationRecord` objects but does not deserialize payloads into `DocumentObj` instances — it only applies them to the SQLite index via `IndexDB.apply_operation()`. Migration is therefore **not** applied during sync traversal.

Migration is applied only at `get()` time, when a full record is deserialized for a caller. This is intentional: the index stores raw payload fields, and the migration engine operates on the deserialized record dict, not the index row.

**Exception**: `migrate_eager()` explicitly deserializes, migrates, and re-serializes records. See Eager Migration below.

### Defensive Deserialization

`DocumentObj._from_storage()` must tolerate unknown fields without raising. Add to the base class:

```python
class DocumentObj:
    @classmethod
    def _from_storage(cls, db, record_id, record):
        """
        Existing implementation, updated to:
        - Ignore keys in record that are not present in the current
          class annotation. Log them at DEBUG level.
        - Use field defaults for keys present in the class annotation
          but absent from record (additive schema change; new field
          not present in old record).
        - Never raise on unrecognized fields.
        """
```

This makes additive changes (minor version bumps) require no migration function at all — `_from_storage()` simply uses the default value for the new field when reading old records.

---

## Eager Migration

```python
# In repository.py

async def migrate_eager(
    self,
    record_type: str,
    target_version: str | None = None,
    dry_run: bool = False,
    batch_size: int = 100,
    progress_callback: callable | None = None
) -> MigrationResult:
    """
    Walk the index for records of record_type whose schema_version
    differs from the current installed package version (or target_version
    if specified). For each such record:

    1. Fetch full OperationRecord from IPFS via _head_cid.
    2. Decrypt payload.
    3. Apply migration engine transforms.
    4. Re-encrypt migrated payload.
    5. If not dry_run: append a new "update" OperationRecord with
       current schema_version. This becomes the new head for the record.
    6. Update IndexDB row to reflect new _head_cid and schema_version.

    batch_size: number of records to process per SQLite transaction.
    progress_callback: called after each batch with (processed, total).
    dry_run: fetch and transform but do not write. Reports what would
      change without modifying the log or index.

    Returns MigrationResult with counts and any per-record errors.
    Records that fail migration are logged and skipped; they do not
    abort the run. Their original records remain in the log.
    """

@dataclass
class MigrationResult:
    record_type: str
    total_records: int
    migrated: int
    skipped_current: int        # already at target version
    skipped_error: int          # transform raised; see errors
    errors: list[tuple[str, Exception]]   # (record_id, exception)
    dry_run: bool
    duration_seconds: float
```

---

## `prmdl migrate` CLI

Add a `migrate` command group to the existing Click CLI in `cli.py`. Follows the existing pattern of `prmdl cohort` subcommands.

```
prmdl migrate status [--cohort COHORT_ID] [--record-type TYPE]
prmdl migrate run    [--cohort COHORT_ID] [--record-type TYPE]
                     [--dry-run] [--batch-size N] [--yes]
prmdl migrate verify [--cohort COHORT_ID] [--record-type TYPE]
                     [--sample N]
```

### `prmdl migrate status`

Inspects the SQLite index and reports schema version distribution. Does not touch IPFS.

Example output:

```
Cohort: who-searo-v1
Package: who-searo-datamodel (installed: 2.1.0)

Record type: SampleCollection
  2.1.0 (current)   3,847 records   76.9%
  2.0.0              891 records   17.8%
  1.1.0              267 records    5.3%

  Migration path available: 1.1.0 → 2.0.0 → 2.1.0  ✓
  Estimated records to migrate: 1,158

Record type: SequenceRun
  2.1.0 (current)   2,104 records  100.0%
  Nothing to migrate.
```

Implementation: query `SELECT schema_version, COUNT(*) FROM sample_collection GROUP BY schema_version` from IndexDB. Build migration paths for each non-current version using `MigrationEngine.find_path()`. Report `MissingMigrationError` if any version has no path.

### `prmdl migrate run`

Calls `CohortRepository.migrate_eager()`. Prompts for confirmation unless `--yes` is passed. Streams progress to stdout.

```
Migrating SampleCollection (1,158 records)...
  [████████████████████░░░░░░░░░░░] 800/1158 (69%)
  Migrated: 800  Errors: 0

Done. 1158 records migrated in 42.3s.
New snapshot triggered automatically.
```

After a successful run, automatically triggers `SnapshotManager.create_snapshot()` so the next cold-start node does not need to replay the pre-migration log. The snapshot captures the post-migration state.

`--dry-run`: runs the full pipeline (fetch, decrypt, transform, re-encrypt) but writes nothing. Reports what would be migrated and any transform errors. Useful for validating a new migration function before committing.

### `prmdl migrate verify`

Fetches a random sample of `--sample N` (default 50) old records, applies transforms, attempts `_from_storage()` deserialization, and reports any errors. Does not write anything. Faster than `--dry-run` on a full run; intended for pre-flight checks when deploying a new data model package version.

```
Verifying migration for SampleCollection (sample: 50 records)...
  Sampled from versions: 1.1.0 (12), 2.0.0 (38)
  All 50 records deserialized successfully.
  No errors found.
```

---

## Cookiecutter Template Scaffold

The PeerModel cookiecutter template (separate repository: `peermodel-cookiecutter`) scaffolds the following structure for new data model packages:

```
{{cookiecutter.package_name}}/
    pyproject.toml                  # versioned independently from application
    CHANGELOG.md                    # human-readable version history
    Makefile                        # see Makefile targets below
    {{cookiecutter.module_name}}/
        __init__.py
        models.py                   # DocumentObj subclasses go here
        migrations/
            __init__.py
            registry.py             # MIGRATIONS dict; initially empty
```

### Scaffolded `registry.py`

```python
# {{cookiecutter.module_name}}/migrations/registry.py
#
# Migration registry for {{cookiecutter.package_name}}.
#
# Add an entry here for each breaking schema change (major version bump).
# Additive changes (new fields with defaults) do not require entries.
#
# Format:
#   ("from_version", "to_version"): migration_function
#
# Each migration function lives in its own module in this directory.
# Signature: migrate(record_type: str, record_dict: dict) -> dict
#
# Example:
#   from {{cookiecutter.module_name}}.migrations import v1_0_to_v2_0
#   MIGRATIONS = {
#       ("1.0.0", "2.0.0"): v1_0_to_v2_0.migrate,
#   }

MIGRATIONS: dict[tuple[str, str], callable] = {}
```

### Makefile targets

```makefile
# Create a new migration stub for a breaking schema change.
# Usage: make migration FROM=1.0.0 TO=2.0.0
migration:
	@test -n "$(FROM)" || (echo "Usage: make migration FROM=x.x.x TO=x.x.x" && exit 1)
	@test -n "$(TO)"   || (echo "Usage: make migration FROM=x.x.x TO=x.x.x" && exit 1)
	python scripts/new_migration.py $(FROM) $(TO)
	@echo "Created migration stub. Edit $(MODULE)/migrations/v$(FROM_CLEAN)_to_v$(TO_CLEAN).py"
	@echo "Then register it in $(MODULE)/migrations/registry.py"
	@echo "Then bump the version in pyproject.toml to $(TO)"

# Verify migrations against a live cohort (requires COHORT env var)
verify-migrations:
	prmdl migrate verify --cohort $(COHORT) --sample 100
```

`scripts/new_migration.py` is a small scaffolding script (included in the template) that:
1. Creates `migrations/v{from_clean}_to_v{to_clean}.py` from a stub template.
2. Prints a reminder to register it in `registry.py` and bump `pyproject.toml`.
3. Does NOT automatically edit `registry.py` — the author must do this manually. Automatic edits to a registry file invite subtle errors; the explicit step is the ceremony that makes the author think about what changed.

### Stub migration module

`scripts/new_migration.py` creates:

```python
# {{module}}/migrations/v{from_clean}_to_v{to_clean}.py
#
# Migration: {from_version} → {to_version}
# Created: {date}
#
# Describe what changed in this version:
#   -
#   -

def migrate(record_type: str, record_dict: dict) -> dict:
    """
    Migrate a record_dict from {from_version} to {to_version}.
    Return a new dict; do not mutate the input.
    """
    result = dict(record_dict)

    # TODO: implement transform
    # Examples:
    #   Rename field:  result["new_name"] = result.pop("old_name", None)
    #   Remove field:  result.pop("removed_field", None)
    #   Add field:     result.setdefault("new_field", default_value)
    #   Split field:   parts = result.pop("combined").split(",")
    #                  result["field_a"], result["field_b"] = parts

    return result
```

---

## Module: `peermodel/migrations.py`

```python
class MigrationEngine:
    # (full spec above)

def load_engine(package_name: str) -> MigrationEngine:
    """
    Import {package_name}.migrations.registry, read MIGRATIONS,
    construct and return a MigrationEngine.
    Raises MigrationRegistryNotFoundError if the module or attribute
    is not found.
    """

_engine_cache: dict[str, MigrationEngine] = {}

def get_engine(package_name: str) -> MigrationEngine:
    """
    Return cached MigrationEngine for package_name, loading if needed.
    """
    if package_name not in _engine_cache:
        _engine_cache[package_name] = load_engine(package_name)
    return _engine_cache[package_name]

def needs_migration(op: OperationRecord) -> bool:
    """
    Return True if op.schema_version differs from the currently installed
    version of op.datamodel_package. Returns False if the package is not
    installed (caller handles that case separately).
    """

def get_version_distribution(
    index_db: IndexDB,
    record_type: str
) -> dict[str, int]:
    """
    Query the SQLite index and return {schema_version: count} for all
    records of record_type. Used by `prmdl migrate status`.
    Requires a _schema_version column in the index table.
    See note below.
    """
```

### Required index column: `_schema_version`

Add `_schema_version TEXT NOT NULL` to the system columns of every record table (specified in `IMPLEMENTATION_DB_SPEC.md`, Table Schema section). This is set from `op.schema_version` during `IndexDB.apply_operation()`. It enables `prmdl migrate status` to report version distribution from SQLite without touching IPFS.

---

## Exceptions

Add to `peermodel/exceptions.py`:

```python
class MigrationError(PeerModelDBError): ...

class MissingMigrationError(MigrationError):
    """
    No migration path exists between two versions with differing
    major version components.
    """

class MigrationRegistryNotFoundError(MigrationError):
    """
    The data model package is not installed, has no migrations module,
    or has no MIGRATIONS attribute. Includes the package name and
    attempted import path in the message.
    """

class MigrationTransformError(MigrationError):
    """
    A migration transform function raised an exception.
    Wraps the original exception; includes record_id, record_type,
    and the from/to version step that failed.
    """
```

---

## Testing Guidance

### Unit tests for migration engine

```python
def test_find_path_direct():
    """Single-step path found correctly."""

def test_find_path_multi_step():
    """Multi-step path walks graph correctly."""

def test_find_path_missing_major():
    """MissingMigrationError raised when major version gap has no path."""

def test_find_path_minor_no_migration():
    """Empty path returned for minor-only version difference with no registered transform."""

def test_apply_single_step():
    """Transform function called with correct arguments; output returned."""

def test_apply_multi_step():
    """Transforms called in sequence; each receives output of previous."""

def test_apply_transform_error_wrapped():
    """MigrationTransformError raised with context when transform raises."""
```

### Integration tests (use existing `repo` fixture from DB spec)

```python
def test_lazy_migration_on_get(repo):
    """
    Write a record with schema_version="1.0.0" directly (bypassing
    the current write path). Install a mock registry that renames a field.
    get() the record; assert the field is present under its new name.
    """

def test_additive_change_no_migration(repo):
    """
    Write a record missing a field present in the current schema.
    Ensure _from_storage() returns the instance with the field's default value.
    No migration function registered; no error raised.
    """

def test_eager_migration_writes_new_op(repo):
    """
    Write old-schema records. Run migrate_eager(). Assert that new
    OperationRecords appear in the log with updated schema_version.
    Assert that get() on each record returns a fully migrated instance.
    """

def test_eager_migration_dry_run_no_writes(repo):
    """dry_run=True: assert MigrationResult.migrated > 0 but no new ops in log."""

def test_migrate_status_output(repo, capsys):
    """prmdl migrate status: assert version distribution matches inserted records."""

def test_missing_registry_error(repo):
    """
    Write a record whose datamodel_package is not installed.
    get() raises MigrationRegistryNotFoundError with helpful message.
    """
```

---

## Out of Scope

- **Automatic registry.py editing**: the `make migration` target creates the stub module but does not edit `registry.py`. Manual registration is the intended ceremony.
- **Downgrade migrations**: transforms are one-directional (old → new). Reading a record newer than the installed package version raises `MigrationRegistryNotFoundError` directing the user to upgrade their package.
- **Cross-record-type migrations**: transforms operate on one record dict at a time. Migrations that require reading other records (e.g. denormalizing a reference) are not supported by the engine; they must be handled as application-level data repair scripts outside PeerModel.
- **Index backfill for new indexed fields**: if a migration adds a new field that is also `@indexed`, old records in the SQLite index will have NULL for that column until `migrate_eager()` is run. The query layer must handle NULLs on indexed fields gracefully. Backfill strategy is the operator's responsibility.
