"""Migration registry discovery and version graph traversal."""

import importlib
from collections import defaultdict, deque
from typing import Dict, List, Tuple, Callable, Optional, Any

# Exception Classes


class MigrationError(Exception):
    """Base exception for migration-related errors."""

    pass


class MissingMigrationError(MigrationError):
    """Raised when no migration path exists for a version gap."""

    pass


class MigrationRegistryNotFoundError(MigrationError):
    """Raised when a package's migration registry cannot be found."""

    pass


class MigrationTransformError(MigrationError):
    """Raised when a migration transform function fails."""

    pass


# Type definitions
MigrationFunc = Callable[[str, Dict[str, Any]], Dict[str, Any]]
VersionPair = Tuple[str, str]
MigrationDict = Dict[VersionPair, MigrationFunc]


class MigrationEngine:
    """Migration engine for managing version transformations.

    Builds a version graph from a migrations registry and provides
    utilities to find migration paths and apply transformations.
    """

    def __init__(self, migrations: MigrationDict):
        """Initialize migration engine with a migrations registry.

        Args:
            migrations: Dict mapping (from_version, to_version) tuples
                       to migration functions.
        """
        self.migrations = migrations
        self._graph: Optional[Dict[str, List[str]]] = None

    def build_version_graph(self) -> Dict[str, List[str]]:
        """Build version graph from migration registry.

        Returns:
            Adjacency list: {version: [reachable_versions, ...]}
        """
        if self._graph is not None:
            return self._graph

        graph: Dict[str, List[str]] = defaultdict(list)

        for from_version, to_version in self.migrations.keys():
            graph[from_version].append(to_version)
            # Ensure to_version is in graph even if it has no outgoing edges
            if to_version not in graph:
                graph[to_version] = []

        self._graph = dict(graph)
        return self._graph

    def _extract_major_version(self, version: str) -> int:
        """Extract major version number from version string.

        Args:
            version: Version string (e.g., "1.2.3")

        Returns:
            Major version number.
        """
        try:
            major = int(version.split(".")[0])
            return major
        except (IndexError, ValueError):
            return 0

    def find_path(self, from_version: str, to_version: str) -> List[VersionPair]:
        """Find shortest path between versions using BFS.

        Uses breadth-first search to find the shortest path from
        from_version to to_version through the migration graph.

        Args:
            from_version: Starting version.
            to_version: Target version.

        Returns:
            List of (from, to) tuples representing migration steps.
            Empty list if versions are equal or minor version bump
            with no explicit migration.

        Raises:
            MissingMigrationError: If major version gap with no path.
        """
        # No migration needed if versions are equal
        if from_version == to_version:
            return []

        graph = self.build_version_graph()

        # BFS to find shortest path
        queue: deque[Tuple[str, List[VersionPair]]] = deque([(from_version, [])])
        visited = {from_version}

        while queue:
            current, path = queue.popleft()

            # Check if we've reached the target
            if current == to_version:
                return path

            # Explore neighbors
            if current in graph:
                for neighbor in graph[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        new_path = path + [(current, neighbor)]
                        queue.append((neighbor, new_path))

        # No path found. Check if it's a major version gap.
        from_major = self._extract_major_version(from_version)
        to_major = self._extract_major_version(to_version)

        if from_major != to_major:
            # Major version gap with no path - this is an error
            raise MissingMigrationError(
                f"No migration path from {from_version} to {to_version}"
            )

        # Minor/patch version bump with no migration - return empty list
        # (additive changes don't require transformations)
        return []

    def apply(
        self,
        record_type: str,
        record_dict: Dict[str, Any],
        from_version: str,
        to_version: str,
    ) -> Dict[str, Any]:
        """Apply migration transforms along the path.

        Chains migration functions sequentially, passing the output
        of each step to the next.

        Args:
            record_type: Type name of the record being migrated.
            record_dict: Record data dict to transform.
            from_version: Starting version.
            to_version: Target version.

        Returns:
            Transformed record dict.

        Raises:
            MigrationTransformError: If any migration function fails.
        """
        path = self.find_path(from_version, to_version)

        result = record_dict
        for from_ver, to_ver in path:
            migration_func = self.migrations[(from_ver, to_ver)]
            try:
                result = migration_func(record_type, result)
            except Exception as e:
                raise MigrationTransformError(
                    f"Migration {from_ver} -> {to_ver} failed: {str(e)}"
                ) from e

        return result


# Caching for loaded engines
_engine_cache: Dict[str, MigrationEngine] = {}


def load_engine(package_name: str) -> MigrationEngine:
    """Load migration engine from a package's registry.

    Imports {package_name}.migrations.registry and reads its MIGRATIONS dict,
    then returns a MigrationEngine constructed from it.

    Args:
        package_name: Name of the package containing migrations.

    Returns:
        MigrationEngine instance.

    Raises:
        MigrationRegistryNotFoundError: If package or registry not found.
    """
    try:
        # Import the registry module
        registry_module = importlib.import_module(f"{package_name}.migrations.registry")
    except ImportError as e:
        raise MigrationRegistryNotFoundError(
            f"Could not load migrations registry for {package_name}: {str(e)}"
        ) from e

    # Get MIGRATIONS dict
    if not hasattr(registry_module, "MIGRATIONS"):
        raise MigrationRegistryNotFoundError(
            f"Package {package_name} has no MIGRATIONS attribute"
        )

    migrations = registry_module.MIGRATIONS
    return MigrationEngine(migrations)


def get_engine(package_name: str) -> MigrationEngine:
    """Get or load a cached MigrationEngine for a package.

    Caches loaded engines to avoid repeated imports.

    Args:
        package_name: Name of the package containing migrations.

    Returns:
        Cached or newly loaded MigrationEngine instance.

    Raises:
        MigrationRegistryNotFoundError: If package or registry not found.
    """
    if package_name not in _engine_cache:
        _engine_cache[package_name] = load_engine(package_name)
    return _engine_cache[package_name]
