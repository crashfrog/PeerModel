#!/usr/bin/env python

"""Migration registry discovery and version graph traversal.

Provides MigrationEngine for managing schema migrations across versions,
including:
- Loading migration registries from data model packages
- Building version graphs from migration definitions
- Finding migration paths using BFS
- Applying migration transforms sequentially
- Eager migration with dry-run support
"""

import importlib
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Callable


# Exception classes
class MigrationError(Exception):
    """Base exception for migration errors."""
    pass


class MissingMigrationError(MigrationError):
    """Raised when no migration path exists between major versions."""
    pass


class MigrationTransformError(MigrationError):
    """Raised when a migration transform function fails."""
    pass


class MigrationRegistryNotFoundError(MigrationError):
    """Raised when a package's migration registry cannot be loaded."""
    pass


# Global cache for loaded engines
_engine_cache: Dict[str, "MigrationEngine"] = {}


class MigrationEngine:
    """Engine for managing and applying schema migrations.

    A MigrationEngine is initialized with a dictionary of migration functions:
        migrations = {
            ("1.0.0", "2.0.0"): migration_func,
            ("2.0.0", "3.0.0"): migration_func,
        }

    The engine builds a directed graph of versions and provides methods to:
    - Find the shortest migration path between versions (BFS)
    - Apply migrations sequentially along a path
    - Handle additive changes (minor/patch) vs breaking changes (major)
    """

    def __init__(self, migrations: Dict[Tuple[str, str], Callable]):
        """Initialize migration engine with a registry of migrations.

        Args:
            migrations: Dict mapping (from_version, to_version) tuples to
                       migration functions. Each function should have
                       signature: func(record_type: str, record_dict: dict)
                       -> dict
        """
        self.migrations = migrations
        self.graph = self.build_version_graph()

    def build_version_graph(self) -> Dict[str, List[str]]:
        """Build directed graph from migration registry.

        Returns:
            Adjacency list mapping each version to list of reachable
            versions. Example: {"1.0.0": ["1.1.0", "2.0.0"],
            "1.1.0": ["2.0.0"]}
        """
        graph: Dict[str, List[str]] = {}

        for (from_version, to_version) in self.migrations.keys():
            if from_version not in graph:
                graph[from_version] = []
            graph[from_version].append(to_version)

        return graph

    def find_path(self, from_version: str,
                  to_version: str) -> List[Tuple[str, str]]:
        """Find shortest migration path using BFS.

        Args:
            from_version: Starting version
            to_version: Target version

        Returns:
            List of (from, to) tuples representing each migration step.
            Empty list if versions match or for additive changes with no
            path.

        Raises:
            MissingMigrationError: If major version differs and no path
                                   exists.
        """
        # No migration needed if versions match
        if from_version == to_version:
            return []

        # BFS to find shortest path
        queue = deque([(from_version, [])])
        visited = {from_version}

        while queue:
            current_version, path = queue.popleft()

            # Check if we've reached the target
            if current_version == to_version:
                return path

            # Explore neighbors
            if current_version in self.graph:
                for next_version in self.graph[current_version]:
                    if next_version not in visited:
                        visited.add(next_version)
                        new_path = path + [
                            (current_version, next_version)
                        ]
                        queue.append((next_version, new_path))

        # No path found - check if it's a major version gap
        from_major = self._get_major_version(from_version)
        to_major = self._get_major_version(to_version)

        if from_major != to_major:
            raise MissingMigrationError(
                f"No migration path from {from_version} to {to_version} "
                f"(major version gap: {from_major} -> {to_major})"
            )

        # Minor/patch difference with no path - additive change,
        # no transform needed
        return []

    def apply(self, record_type: str, record_dict: dict,
              from_version: str, to_version: str) -> dict:
        """Apply migration transforms sequentially along the path.

        Args:
            record_type: Type name of the record being migrated
            record_dict: Record data to transform
            from_version: Starting version
            to_version: Target version

        Returns:
            Transformed record dict

        Raises:
            MigrationTransformError: If any migration function fails
            MissingMigrationError: If no path exists for major version gap
        """
        # Find the migration path
        path = self.find_path(from_version, to_version)

        # If no path needed, return original record
        if not path:
            return record_dict

        # Apply each migration step sequentially
        current_record = record_dict
        for step in path:
            migration_func = self.migrations[step]
            try:
                current_record = migration_func(record_type, current_record)
            except Exception as e:
                raise MigrationTransformError(
                    f"Migration from {step[0]} to {step[1]} failed: {e}"
                ) from e

        return current_record

    @staticmethod
    def _get_major_version(version: str) -> str:
        """Extract major version component from version string.

        Args:
            version: Version string like "1.2.3"

        Returns:
            Major version component like "1"
        """
        return version.split('.')[0]


def load_engine(package_name: str) -> MigrationEngine:
    """Load migration engine from a package's registry.

    Imports {package_name}.migrations.registry and reads the MIGRATIONS dict
    to construct a MigrationEngine.

    Args:
        package_name: Name of the data model package

    Returns:
        MigrationEngine instance initialized with package's migrations

    Raises:
        MigrationRegistryNotFoundError: If package or registry not found
    """
    try:
        # Import the migrations.registry module
        module_name = f"{package_name}.migrations.registry"
        registry_module = importlib.import_module(module_name)

        # Read the MIGRATIONS dict
        if not hasattr(registry_module, "MIGRATIONS"):
            raise MigrationRegistryNotFoundError(
                f"Package '{package_name}' has migrations module but no "
                f"MIGRATIONS dict"
            )

        migrations = registry_module.MIGRATIONS
        return MigrationEngine(migrations)

    except ImportError as e:
        raise MigrationRegistryNotFoundError(
            f"Could not load migration registry for package "
            f"'{package_name}': {e}"
        ) from e


def get_engine(package_name: str) -> MigrationEngine:
    """Get cached migration engine for a package.

    Loads the engine on first call and caches it for subsequent calls.

    Args:
        package_name: Name of the data model package

    Returns:
        Cached MigrationEngine instance
    """
    if package_name not in _engine_cache:
        _engine_cache[package_name] = load_engine(package_name)
    return _engine_cache[package_name]


@dataclass
class MigrationResult:
    """Result of eager migration operation.

    Attributes:
        migrated: Number of records successfully migrated
        skipped: Number of records already at target version
        errors: Number of records that failed to migrate
        error_details: List of error details for failed records
    """
    migrated: int = 0
    skipped: int = 0
    errors: int = 0
    error_details: List[Dict[str, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Total records processed (migrated + skipped + errors)."""
        return self.migrated + self.skipped + self.errors


async def migrate_eager(
    index_db,
    target_version: str,
    package_name: str,
    dry_run: bool = False
) -> MigrationResult:
    """Eagerly migrate all indexed records to target schema version.

    Executes the full pipeline for each record:
    1. Query index for records grouped by (record_type, current_version)
    2. Fetch and decrypt records
    3. Apply migration transformations via migration path
    4. Re-encrypt records
    5. Write results to IPFS and update index (skipped if dry_run=True)

    In dry-run mode:
    - Full pipeline is executed (fetch, decrypt, transform, re-encrypt)
    - Changes are NOT written to IPFS or index
    - Counts and error details are still reported accurately

    Args:
        index_db: IndexDB instance containing records to migrate
        target_version: Target schema version string (e.g., "2.0.0")
        package_name: Package name for migration registry lookup
        dry_run: If True, execute pipeline but don't write changes

    Returns:
        MigrationResult with migrated/skipped/errors counts

    Raises:
        MigrationError: If migration setup fails
        MissingMigrationError: If no migration path exists for a record type
    """
    # Placeholder: will be implemented by the implementation agent
    # This signature is the contract that tests depend on
    raise NotImplementedError("migrate_eager not yet implemented")
