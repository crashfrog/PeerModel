# PeerModel — Append-Only IPFS Database Layer Specification

## Purpose and Scope

This document specifies the database persistence layer for PeerModel. It replaces and supersedes the `PersistedDatabase`, `PersistedCapabilitiesDatabase`, and `NamespacedIPLDDictionary` stubs in `iplddict.py` and `peermodel.py` with a production architecture based on an append-only IPFS operation log, a local SQLite query index, and periodic snapshots to bound cold-start cost.

This spec should be read alongside `IMPLEMENTATION_CRYPTOSYSTEM_SPEC.md`. The cryptosystem handles signing, encryption, envelope key management, and hardware token access. This spec handles persistence, indexing, sync, and the ORM interface that library users interact with.

---

## Relationship to Existing Code

### What this spec replaces

| Existing | Replaced by |
|---|---|
| `PersistedDatabase` in `peermodel.py` | `CohortRepository` in `repository.py` |
| `PersistedCapabilitiesDatabase` in `peermodel.py` | `CohortRepository` + encryption layer from `capabilities.py` |
| `NamespacedIPLDDictionary` in `iplddict.py` | `MappingShim` in `iplddict.py` (thin wrapper, see below) |
| `SqliteRecordManagerDictionary` in `iplddict.py` | `IndexDB` in `index.py` |

### What this spec preserves and builds on

- `DocumentObj` base mixin, `_to_storage()` / `_from_storage()`, and the type registry in `peermodel.py` — unchanged. The log layer serializes whatever `_to_storage()` produces.
- `App` and its `@model`, `@event`, `@aggregated`, `@indexed` decorators — unchanged. `@indexed` gains a SQLite-backed implementation (currently a stub).
- `SimpleCohort`, `MembershipProposal`, `MembershipVote` in `delegation.py` and `membership.py` — unchanged. Cohort identity and signing objects from these classes are passed into the repository layer.
- `ECDSAKeysystem` and `IdentityManager` in `capabilities.py` — unchanged. Encryption wraps record payloads before they enter the log layer.
- CLI commands in `cli.py` — unchanged at the interface level. CRUD commands route through `App` which routes through `CohortRepository`.

### What changes in existing files

**`peermodel.py`**: `PersistedDatabase` and `PersistedCapabilitiesDatabase` are removed. `App` is updated so that when a `PersistedCapabilitiesDatabase` was previously instantiated, it now instantiates a `CohortRepository`. The `@indexed` decorator is updated to register field metadata consumed by `index.py` schema generation (see Schema section).

**`iplddict.py`**: `NamespacedIPLDDictionary` is reimplemented as `MappingShim` — a thin `collections.abc.MutableMapping` over `CohortRepository`. The cohort namespace is carried as a constructor argument. `SqliteRecordManagerDictionary` is removed; its role is taken by `IndexDB`.

---

## Architecture Overview

```
App (@model, @indexed decorators)
    |
    v
CohortRepository          ← primary interface for all persistence
    |          |
    v          v
OperationLog  IndexDB (SQLite)
    |
    v
IPFS (content-addressed, immutable)
    |
    v
IPNS (mutable pointer to log head)
```

**Write path**: `CohortRepository.save()` → encrypt payload (via `Keysystem`) → `OperationLog.append()` → publish `OperationRecord` to IPFS → update IPNS head → `IndexDB.apply_operation()` → check snapshot threshold → optionally trigger `SnapshotManager.create_snapshot()`.

**Read path**: `CohortRepository.query()` → `IndexDB.query()` → returns index rows (all indexed fields present) → optionally fetch full record from IPFS by CID for non-indexed fields.

**Sync path**: `SyncManager.sync()` → resolve IPNS head → compare to `NodeState.last_synced_head_cid` → `OperationLog.traverse()` (parallel fetch) → verify signatures → `IndexDB.apply_operation()` for each → update `NodeState`.

**Cold start**: `SyncManager.cold_start()` → `SnapshotManager.load_latest()` → `IndexDB.apply_snapshot()` → replay delta from snapshot head to current IPNS head.

---

## Module Structure

New modules added to `peermodel/`:

```
peermodel/
    repository.py       # CohortRepository — primary ORM interface
    log.py              # OperationRecord, OperationLog — log construction and traversal
    index.py            # IndexDB — SQLite index management
    snapshot.py         # SnapshotManager — snapshot creation, publication, loading
    sync.py             # SyncManager — cold start, incremental sync, parallel fetch
    state.py            # NodeState — per-cohort sync state persistence
    exceptions.py       # Extended exception hierarchy (adds to existing UnauthorizedAccess)
```

Modified existing modules:

```
peermodel/
    peermodel.py        # Remove PersistedDatabase, PersistedCapabilitiesDatabase;
                        # update App to instantiate CohortRepository
    iplddict.py         # Replace NamespacedIPLDDictionary with MappingShim;
                        # remove SqliteRecordManagerDictionary
```

---

## Data Structures

### OperationRecord

The atomic unit of the log. Every write produces exactly one `OperationRecord`, published to IPFS as a CBOR-encoded object.

```python
@dataclass
class OperationRecord:
    op_id: str                  # UUID, unique per operation
    op_type: str                # "insert" | "update" | "tombstone"
    cohort_id: str
    record_type: str            # DocumentObj subclass name, e.g. "SampleCollection"
    record_id: str              # stable _id across operations for the same logical record
    sequence_number: int        # monotonically increasing per cohort log; 1-based
    payload: dict | None        # serialized record fields; None for tombstone
                                # payload is the output of DocumentObj._to_storage(),
                                # encrypted by Keysystem before being placed here
    previous_head_cid: str | None   # CID of previous OperationRecord; None at genesis
    timestamp: str              # ISO8601 UTC
    schema_version: str         # semver; bumped on breaking changes to this structure
    signature: bytes            # cohort signature over canonical_op_bytes()
    signing_algorithm: str      # "ed25519" | "p256_ecdsa"
```

`canonical_op_bytes()` is the authoritative byte string for signing: CBOR encoding of all fields except `signature` and `signing_algorithm`, keys in alphabetical order. This function must be stable; any change requires a `schema_version` bump.

### Snapshot

Point-in-time serialization of full derived index state for one record type. Published to IPFS.

```python
@dataclass
class Snapshot:
    cohort_id: str
    snapshot_id: str            # UUID
    record_type: str
    log_head_cid: str           # OperationRecord CID at snapshot time
    sequence_number: int        # sequence number of log_head_cid
    records: list[dict]         # current state of all live (non-tombstoned) records
                                # each dict is the decrypted _to_storage() output
    created_at: str             # ISO8601 UTC
    schema_version: str
    signature: bytes
    signing_algorithm: str
```

Snapshots cover one `record_type` per object. A cohort with three model classes has three independent snapshot chains.

### NodeState

Persisted locally in a `_node_state` SQLite table. One row per `(cohort_id, record_type)`.

```python
@dataclass
class NodeState:
    cohort_id: str
    record_type: str
    last_synced_head_cid: str | None
    last_synced_sequence: int           # 0 if never synced
    snapshot_cid: str | None
    snapshot_sequence: int              # 0 if no snapshot loaded
    index_status: str                   # "cold" | "building" | "current" | "stale"
    last_sync_at: str | None            # ISO8601 UTC
```

---

## Module: `log.py`

```python
def create_operation(
    op_type: str,                       # "insert" | "update" | "tombstone"
    record_type: str,
    record_id: str,
    payload: dict | None,               # already encrypted by caller; None for tombstone
    cohort_identity,                    # SimpleCohort or CohortIdentity from delegation.py
    cohort_private_key_bytes: bytes,
    current_head_cid: str | None,
    current_sequence: int,
    schema_version: str = "1.0.0"
) -> OperationRecord:
    """
    Construct and sign an OperationRecord. Does not publish to IPFS.
    sequence_number = current_sequence + 1.
    Signs over canonical_op_bytes() using the cohort signing key.
    Caller is responsible for encrypting payload before passing it in.
    """

def publish_operation(
    op: OperationRecord,
    ipfs_client
) -> str:
    """
    Serialize op to CBOR and publish to IPFS. Returns the new head CID.
    Called immediately after create_operation(). The returned CID is
    passed to ipns_update() and stored in NodeState.
    """

def verify_operation(
    op: OperationRecord,
    cohort_identity
) -> bool:
    """
    Verify the cohort signature on an OperationRecord using the cohort's
    public signing key. Returns True if valid, False otherwise.
    Does not raise; invalid signatures are caller's responsibility to handle.
    Called during log traversal on every fetched record before applying to index.
    """

def canonical_op_bytes(op: OperationRecord) -> bytes:
    """
    Authoritative canonical serialization for signing and verification.
    CBOR-encodes all OperationRecord fields except signature and
    signing_algorithm, in alphabetical key order.
    This function is the single source of truth for what gets signed.
    It must not change without a schema_version bump.
    """

async def traverse(
    head_cid: str,
    stop_at_cid: str | None,
    ipfs_client,
    concurrency: int = 50
) -> list[OperationRecord]:
    """
    Traverse the log DAG from head_cid back to stop_at_cid (exclusive),
    or to genesis if stop_at_cid is None.

    Three-phase strategy:

    Phase 1 — Sequential discovery:
      Fetch head_cid. Extract previous_head_cid. Repeat until stop_at_cid
      or None is reached. Collect all intermediate CIDs not yet fetched.
      This phase is sequential because each CID is learned from its successor.
      Yields batches of newly discovered CIDs to Phase 2 as they are found,
      rather than waiting for full discovery before fetching. Target batch
      size: concurrency * 2, so Phase 2 is always fed.

    Phase 2 — Parallel fetch:
      Fetch all batched CIDs concurrently using asyncio with a semaphore
      limiting to `concurrency` simultaneous requests. Deserialize each
      CBOR response to OperationRecord.

    Phase 3 — Verify and sort:
      Call verify_operation() on each fetched record. Records with invalid
      signatures are logged as warnings and excluded from results — they are
      not applied to the index. Emit a single LogIntegrityError if more than
      10% of records in a batch fail signature verification (suggests a
      compromised or corrupted log rather than isolated bad records).
      Sort remaining records by sequence_number ascending (oldest first).

    Returns list of verified OperationRecords in chronological order.

    Raises:
      LogIntegrityError: if a CID cannot be fetched after 3 retries,
        if sequence_numbers are non-contiguous, or if >10% of records
        fail signature verification.
    """

def get_current_head(
    cohort_id: str,
    ipfs_client
) -> str | None:
    """
    Resolve the cohort's IPNS name to the current log head CID.
    IPNS key name is derived as: f"peermodel:{cohort_id}:log"
    Returns None if the IPNS name is not yet published (empty log).
    """

def update_head(
    cohort_id: str,
    new_head_cid: str,
    ipfs_client,
    ttl: str = "24h"
) -> None:
    """
    Publish new_head_cid to the cohort's IPNS log name.
    IPNS key must be registered with the local IPFS node.
    Called after every successful publish_operation().
    """
```

---

## Module: `index.py`

```python
class IndexDB:
    """
    Manages the SQLite index for one or more record types within a cohort.
    The database file lives at the path configured in App (default:
    ~/.peermodel/<cohort_id>/index.db).

    One IndexDB instance is shared across all record types for a cohort.
    Each record type gets its own table, named by snake_casing the record_type.
    A shared _node_state table holds NodeState rows.
    """

    def __init__(self, db_path: Path): ...

    def ensure_schema(self, model_class: type) -> None:
        """
        Create or verify the SQLite schema for a DocumentObj subclass.
        Derives schema from the class's field annotations and @indexed
        decorator metadata (see Schema Generation below).

        Creates:
          - Record table named snake_case(record_type) with columns for
            each annotated field, plus system columns:
              _record_id TEXT PRIMARY KEY
              _op_id TEXT NOT NULL
              _sequence INTEGER NOT NULL
              _timestamp TEXT NOT NULL
              _head_cid TEXT NOT NULL     -- CID of the OperationRecord
              _tombstoned INTEGER NOT NULL DEFAULT 0
          - CREATE INDEX on each field decorated with @indexed.
          - CREATE INDEX on _tombstoned (for live-record filtering).
          - _node_state table if not exists.

        Idempotent: safe to call on an existing database.
        Raises SchemaMismatchError if the existing table has incompatible
        columns (different types or missing non-nullable columns).
        Does not auto-migrate; migration is out of scope for this spec.
        """

    def apply_operation(self, op: OperationRecord) -> None:
        """
        Apply a verified OperationRecord to the index. All applies are
        wrapped in a SQLite transaction.

        "insert": INSERT OR REPLACE the payload fields plus system columns.
          Payload must contain all non-nullable fields; raises
          MissingFieldError otherwise.
        "update": UPDATE existing row. Raises RecordNotFoundError if
          no row exists for record_id (update without prior insert is invalid).
        "tombstone": SET _tombstoned=1 for the row. Raises RecordNotFoundError
          if no row exists.

        Idempotent: if op_id already exists in the table (checked via
        _op_id column), silently return without applying. This makes
        replay safe — the same operation can be applied twice without
        corrupting the index.
        """

    def apply_snapshot(self, snapshot: Snapshot) -> None:
        """
        Bulk-load a snapshot into the SQLite index.
        Drops and recreates the record table for snapshot.record_type
        (does NOT drop other record type tables or _node_state).
        Bulk-inserts all records from snapshot.records in a single transaction.
        Updates the NodeState row for (cohort_id, record_type) to reflect
        snapshot_cid and snapshot_sequence.
        After this call, apply_operation() should be called for any
        operations with sequence_number > snapshot.sequence_number.
        """

    def query(
        self,
        record_type: str,
        filters: dict | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_tombstoned: bool = False
    ) -> list[dict]:
        """
        Query the index for a record type. Returns list of row dicts
        including all stored columns (indexed fields + system columns).

        filters: {field_name: value} for equality. For range queries,
          value may be a 2-tuple: (">=", value), ("<", value), etc.
          Multiple filters are AND-combined.
        order_by: field name string. Prefix with "-" for DESC.
        include_tombstoned: default False; adds WHERE _tombstoned=0.

        Does not hit IPFS. Returns raw SQLite rows, not DocumentObj instances.
        For non-indexed fields, caller uses get_record_cid() then fetches
        the full OperationRecord from IPFS.
        """

    def get_record_cid(self, record_type: str, record_id: str) -> str | None:
        """
        Return the _head_cid of the most recent operation for record_id.
        Used when a caller needs the full record from IPFS.
        Returns None if record_id not found or tombstoned.
        """

    def get_node_state(self, cohort_id: str, record_type: str) -> NodeState:
        """
        Retrieve NodeState for a (cohort_id, record_type) pair.
        If no row exists, returns a NodeState with all None/0/"cold" defaults.
        """

    def set_node_state(self, state: NodeState) -> None:
        """
        Upsert a NodeState row. Called after every sync operation and
        after snapshot load.
        """
```

### Schema Generation from `@indexed`

The `@indexed` decorator in `App` is updated to store field metadata on the class so `IndexDB.ensure_schema()` can read it:

```python
# In peermodel.py App class — updated @indexed implementation:
def indexed(self, field_name: str, **kwargs):
    """
    Mark a field on a @model class as indexed in the SQLite layer.
    Stores metadata as _peermodel_indexed_fields on the class.
    Usage:
        @peer.model
        class Sample(DocumentObj):
            sample_id: str
            collection_date: str
            pathogen: str

        peer.indexed('Sample', 'collection_date')
        peer.indexed('Sample', 'pathogen')
    """
```

`IndexDB.ensure_schema()` reads `model_class._peermodel_indexed_fields` to determine which columns get `CREATE INDEX`. Fields not decorated with `@indexed` are stored as columns but not indexed. All fields present in the dataclass annotation are stored as columns; type mapping is:

| Python type | SQLite type |
|---|---|
| `str` | `TEXT` |
| `int` | `INTEGER` |
| `float` | `REAL` |
| `bool` | `INTEGER` (0/1) |
| `dict`, `list` | `BLOB` (CBOR-encoded) |
| `bytes` | `BLOB` |

---

## Module: `snapshot.py`

```python
class SnapshotManager:

    def __init__(self, ipfs_client, cohort_identity): ...

    def should_snapshot(
        self,
        node_state: NodeState,
        current_sequence: int,
        threshold_ops: int = 500,
        threshold_days: int = 30
    ) -> bool:
        """
        Return True if a new snapshot should be created:
          - (current_sequence - node_state.snapshot_sequence) >= threshold_ops, OR
          - days since node_state.last_sync_at >= threshold_days.
        Both thresholds come from the model class Meta if defined there;
        the parameters here are fallback defaults.
        Called by CohortRepository after every successful save().
        """

    def create_snapshot(
        self,
        record_type: str,
        index_db: IndexDB,
        log_head_cid: str,
        sequence_number: int,
        cohort_private_key_bytes: bytes
    ) -> tuple[Snapshot, str]:
        """
        Snapshot current index state for record_type.
        Reads all live (_tombstoned=0) rows from IndexDB.
        Constructs a Snapshot, signs it with the cohort key.
        Publishes to IPFS. Updates IPNS snapshot pointer:
          key name: f"peermodel:{cohort_id}:{record_type}:snapshot"
        Returns (Snapshot, snapshot_cid).
        Snapshot creation reads only from SQLite; does not traverse IPFS.
        This makes it cheap: ~milliseconds regardless of log length.
        Caller (CohortRepository) updates NodeState after return.
        """

    def load_latest(
        self,
        cohort_id: str,
        record_type: str
    ) -> tuple[Snapshot, str] | tuple[None, None]:
        """
        Resolve the snapshot IPNS pointer for (cohort_id, record_type).
        Fetch and deserialize the Snapshot. Verify cohort signature.
        Returns (Snapshot, snapshot_cid), or (None, None) if no snapshot exists.
        Raises InvalidSignatureError if signature verification fails.
        Raises SnapshotSchemaMismatchError if the snapshot's schema_version
        is incompatible with the current model schema.
        """
```

---

## Module: `sync.py`

```python
class SyncManager:
    """
    Orchestrates cold start, warm incremental sync, and index freshness.
    One SyncManager per cohort. Holds references to OperationLog helpers,
    IndexDB, SnapshotManager, and the IPFS client.
    """

    def __init__(
        self,
        cohort_identity,
        index_db: IndexDB,
        snapshot_manager: SnapshotManager,
        ipfs_client,
        traverse_concurrency: int = 50
    ): ...

    async def sync(
        self,
        record_type: str,
        model_class: type,
        force_full_rebuild: bool = False
    ) -> SyncResult:
        """
        Main sync entry point. Selects strategy based on NodeState:

        Strategy selection:
          node_state.index_status == "cold" OR force_full_rebuild:
            → cold_start()
          node_state.last_synced_head_cid is not None:
            → incremental_sync()
          else:
            → cold_start()

        In all cases:
          1. Resolve current IPNS log head.
          2. If head matches last_synced_head_cid: index is current, return early.
          3. Execute selected strategy.
          4. Update NodeState.index_status = "current", last_sync_at = now.
          5. Return SyncResult.
        """

    async def cold_start(
        self,
        record_type: str,
        model_class: type,
        current_head_cid: str
    ) -> SyncResult:
        """
        Full index build from snapshot + delta.

        1. SnapshotManager.load_latest() → (snapshot, snapshot_cid).
        2. If snapshot exists:
             IndexDB.apply_snapshot(snapshot).
             delta_start_cid = snapshot.log_head_cid.
             delta_start_seq = snapshot.sequence_number.
           Else:
             delta_start_cid = None (traverse from genesis).
             delta_start_seq = 0.
        3. log.traverse(current_head_cid, stop_at_cid=delta_start_cid,
             concurrency=self.traverse_concurrency)
           → list[OperationRecord] in chronological order.
        4. For each op in order:
             verify_operation(op, cohort_identity) — skip if invalid.
             IndexDB.apply_operation(op).
        5. Update NodeState: last_synced_head_cid, last_synced_sequence,
           snapshot_cid, snapshot_sequence, index_status="current".
        """

    async def incremental_sync(
        self,
        record_type: str,
        current_head_cid: str
    ) -> SyncResult:
        """
        Replay only operations since last_synced_head_cid.

        1. log.traverse(current_head_cid,
             stop_at_cid=node_state.last_synced_head_cid,
             concurrency=self.traverse_concurrency)
        2. For each op in chronological order:
             verify and apply as in cold_start.
        3. Update NodeState.
        For a write-light cohort syncing daily, this traverses only the
        handful of operations added since the last sync. Very cheap.
        """

@dataclass
class SyncResult:
    record_type: str
    ops_applied: int
    ops_skipped_invalid_sig: int
    snapshot_loaded: bool
    previous_head_cid: str | None
    new_head_cid: str
    duration_seconds: float
```

---

## Module: `repository.py`

Primary ORM interface. This is what `App` instantiates and what all `@model` operations route through.

```python
class CohortRepository:
    """
    Append-only repository for a single cohort. Composes OperationLog,
    IndexDB, SnapshotManager, and SyncManager.

    Instantiated by App when a persisted database is requested. One instance
    per cohort. App holds a registry of CohortRepository instances keyed
    by cohort_id.
    """

    def __init__(
        self,
        cohort_identity,                # SimpleCohort from delegation.py
        cohort_private_key_bytes: bytes,
        keysystem,                      # ECDSAKeysystem from capabilities.py
        ipfs_client,
        db_path: Path,
        traverse_concurrency: int = 50
    ): ...

    def save(self, instance: DocumentObj) -> str:
        """
        Persist a DocumentObj instance. Returns the CID of the new
        OperationRecord (the new log head).

        1. Determine op_type:
             "insert" if record_id not in index, "update" otherwise.
        2. Serialize: typename, record_id, record_dict = instance._to_storage(db).
        3. Encrypt record_dict via self.keysystem (envelope encryption as
           specified in IMPLEMENTATION_CRYPTOSYSTEM_SPEC.md). Encrypted
           payload replaces record_dict.
        4. create_operation(op_type, ..., payload=encrypted_payload).
        5. publish_operation(op) → new_head_cid.
        6. update_head(cohort_id, new_head_cid).
        7. IndexDB.apply_operation(op).
           Note: indexed fields must be stored unencrypted in the index
           for queryability. See Encryption and Indexing below.
        8. Check SnapshotManager.should_snapshot(); if True, trigger
           create_snapshot() — non-blocking, run in background thread.
        9. Return new_head_cid.
        """

    def get(self, record_type: str, record_id: str) -> DocumentObj | None:
        """
        Retrieve a record by its record_id.
        1. IndexDB.get_record_cid(record_type, record_id) → head_cid.
        2. If None: return None.
        3. Fetch OperationRecord from IPFS by head_cid.
        4. Decrypt payload via self.keysystem.
        5. Deserialize via DocumentObj._from_storage().
        6. Return instance.
        Raises UnauthorizedAccess (from capabilities.py) if decryption fails.
        """

    def query(
        self,
        record_type: str,
        filters: dict | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None
    ) -> list[DocumentObj]:
        """
        Query records using the SQLite index.
        1. IndexDB.query(record_type, filters, order_by, limit, offset).
        2. For each result row: fetch full record via get(record_type, _record_id).
        Returns list of DocumentObj instances.

        Performance note: for queries where all needed fields are indexed,
        callers may use query_index() instead to avoid IPFS fetches.
        """

    def query_index(
        self,
        record_type: str,
        filters: dict | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None
    ) -> list[dict]:
        """
        Query the SQLite index only. Returns raw row dicts without
        fetching from IPFS or decrypting. Fast path for queries where
        indexed fields are sufficient.
        Non-indexed fields are not present in the result dicts.
        Tombstoned records are excluded by default.
        """

    def delete(self, record_type: str, record_id: str) -> str:
        """
        Append a tombstone operation for record_id. Returns new head CID.
        Does not remove data from IPFS (impossible by design).
        The record will be excluded from future queries.
        Raises RecordNotFoundError if record_id not in index.
        """

    async def sync(
        self,
        record_type: str,
        model_class: type,
        force_full_rebuild: bool = False
    ) -> SyncResult:
        """
        Delegate to SyncManager.sync(). Call this before querying on a
        node that may be behind the current log head, or on cold start.
        """

    def get_log_history(
        self,
        record_type: str,
        record_id: str,
        limit: int | None = None
    ) -> list[OperationRecord]:
        """
        Return the operation history for a specific record_id, most recent first.
        Fetches from IPFS by traversing the log and filtering for record_id.
        This is a slow operation (full or partial log traversal); use sparingly.
        limit: stop after finding this many operations for record_id.
        Useful for audit and provenance queries specific to disease surveillance.
        """
```

### Encryption and Indexing

A design constraint: indexed fields must be queryable from SQLite without decrypting the full record. The encryption layer must therefore treat indexed fields differently from non-indexed fields.

**Required behavior in `save()`:**

Before passing the payload to `create_operation()`, split it:

- **Indexed fields**: stored in the SQLite index row in plaintext. Also included in the encrypted payload for record integrity. The index is a convenience cache, not the authoritative source.
- **Non-indexed fields**: encrypted in the payload only. Not stored in SQLite.

This means the `apply_operation()` call to IndexDB receives both the (plaintext) indexed field values for the index row AND the encrypted payload CID for later full-record retrieval. The index row contains enough to answer common queries; the full IPFS record is fetched only when non-indexed fields are needed.

**Implication**: indexed fields on encrypted records are visible to anyone with access to the SQLite index file. Cohort members choosing to mark a field as `@indexed` are accepting that this field will not be encrypted at rest in the local index. Document this clearly to library users.

---

## Module: `iplddict.py` (updated)

`NamespacedIPLDDictionary` is replaced with `MappingShim`: a thin `collections.abc.MutableMapping` over `CohortRepository` for callers that prefer a dict-like interface.

```python
class MappingShim(collections.abc.MutableMapping):
    """
    Thin MutableMapping wrapper over CohortRepository.
    Provides dict-like access for callers that need it.
    The cohort namespace is implicit in the CohortRepository instance.

    Key format: "{record_type}:{record_id}"
    Value: DocumentObj instance or serialized dict.

    This is not the primary interface; use CohortRepository directly
    for query, sync, and history operations that MutableMapping cannot express.
    """

    def __init__(self, repository: CohortRepository, record_type: str): ...

    def __setitem__(self, record_id: str, value: DocumentObj) -> None:
        self.repository.save(value)

    def __getitem__(self, record_id: str) -> DocumentObj:
        result = self.repository.get(self.record_type, record_id)
        if result is None:
            raise KeyError(record_id)
        return result

    def __delitem__(self, record_id: str) -> None:
        self.repository.delete(self.record_type, record_id)

    def __iter__(self):
        rows = self.repository.query_index(self.record_type)
        return iter(row["_record_id"] for row in rows)

    def __len__(self):
        return len(self.repository.query_index(self.record_type))
```

`SqliteRecordManagerDictionary` is removed. Its multi-db support is no longer needed; `IndexDB` uses one SQLite file per cohort.

---

## Module: `state.py`

```python
def get_node_state(
    db: IndexDB,
    cohort_id: str,
    record_type: str
) -> NodeState:
    """Retrieve or initialize NodeState from IndexDB._node_state table."""

def set_node_state(db: IndexDB, state: NodeState) -> None:
    """Upsert NodeState into IndexDB._node_state table."""

def mark_stale(db: IndexDB, cohort_id: str, record_type: str) -> None:
    """
    Set index_status="stale" for a (cohort_id, record_type) pair.
    Called when the node detects its IPNS head is behind the network
    but has not yet synced. Queries on stale indexes are permitted but
    should warn the caller.
    """
```

---

## Module: `exceptions.py` (extended)

Extends the existing `UnauthorizedAccess` from `capabilities.py`. Add:

```python
class PeerModelDBError(Exception): ...         # base for all new exceptions

class LogIntegrityError(PeerModelDBError): ... # non-contiguous sequences, fetch failure,
                                               # or >10% invalid signatures in a batch
class RecordNotFoundError(PeerModelDBError): ...
class MissingFieldError(PeerModelDBError): ...
class SchemaMismatchError(PeerModelDBError): ...
class SnapshotSchemaMismatchError(PeerModelDBError): ...
class DuplicateOperationError(PeerModelDBError): ... # idempotent replay; not re-raised,
                                                      # logged at DEBUG level only
class StaleIndexWarning(UserWarning): ...      # query on stale index; not an error
```

---

## Testing Guidance

Tests go in `peermodel/tests/`. Follow the existing pytest + hypothesis patterns.

### New fixtures (add to test files or conftest.py)

```python
@pytest.fixture
def ipfs_mock():
    """
    Mock IPFS client that stores published CIDs in a local dict.
    Simulates publish_operation(), fetch, and IPNS resolution
    without a running IPFS daemon. Sufficient for unit tests.
    """

@pytest.fixture
def repo(tmp_path, test_cohort, ipfs_mock):
    """
    CohortRepository instance using test_cohort (from existing fixtures),
    ipfs_mock, and a tmp_path SQLite database.
    """

@pytest.fixture
def repo_with_records(repo):
    """repo with 10 pre-inserted records of a test model type."""
```

### Required test cases

**Log integrity**
- `test_operation_canonical_bytes_stable`: serialize the same OperationRecord twice; assert bytes are identical.
- `test_signature_verification`: create and sign an operation; verify it passes. Mutate one byte of the payload; verify it fails.
- `test_traverse_order`: insert 5 records; traverse from head to genesis; assert returned ops are in sequence_number order.
- `test_traverse_stops_at_cid`: traverse with stop_at_cid set; assert only ops after that CID are returned.

**Index correctness**
- `test_insert_queryable`: save a record; query by an indexed field; assert it appears.
- `test_update_reflected`: save, then save again with updated fields; query; assert updated values.
- `test_tombstone_excluded`: save, then delete; query; assert record not in results.
- `test_idempotent_replay`: apply the same OperationRecord twice; assert no error and no duplicate row.

**Snapshot round-trip**
- `test_snapshot_create_load`: create a snapshot; load it from the mock IPFS; verify signature; assert records match index state.
- `test_cold_start_from_snapshot`: populate a repo, create a snapshot, wipe the index, cold_start(); assert index matches original state.
- `test_cold_start_without_snapshot`: cold_start() with no snapshot; assert full log replay produces correct index.

**Sync**
- `test_incremental_sync`: sync to head N; add 3 more records; incremental_sync(); assert only 3 ops applied.
- `test_sync_skips_invalid_sig`: inject one record with a bad signature into the mock log; sync(); assert it is skipped and the rest apply correctly.

**MappingShim**
- `test_shim_setitem_getitem`: set and get via MappingShim; assert round-trip.
- `test_shim_delitem`: delete via shim; assert KeyError on subsequent get.
- `test_shim_iter`: iterate keys; assert all record_ids present.

**Encryption + indexing**
- `test_indexed_fields_in_sqlite`: save an encrypted record; assert indexed fields are present and plaintext in SQLite; assert non-indexed fields are absent from SQLite.
- `test_full_record_fetch_decrypts`: get() a record saved with encryption; assert all fields present and decrypted correctly.

---

## Configuration

Add to `~/.peermodel/idconfig.json` (existing config file):

```json
{
  "db": {
    "index_db_dir": "~/.peermodel",
    "snapshot_threshold_ops": 500,
    "snapshot_threshold_days": 30,
    "traverse_concurrency": 50,
    "ipfs_api_url": "/ip4/127.0.0.1/tcp/5001"
  }
}
```

All values have the defaults shown. `index_db_dir` determines where `<cohort_id>/index.db` files are created.

---

## Out of Scope for This Spec

- **Schema migration**: adding or removing fields from an existing model after records have been written. Not addressed; treat as a future spec.
- **Cross-cohort queries**: querying across multiple cohorts' indexes simultaneously.
- **Full-text search**: field-level substring or full-text search within BLOB fields. SQLite FTS5 could be added later; not specified here.
- **Garbage collection of old snapshots**: old snapshot CIDs accumulate on IPFS. Unpinning strategy is not addressed.
- **Conflict resolution beyond last-write-wins**: concurrent writes from two nodes that both believe they hold the current log head. The append-only log makes this detectable (sequence number gap); resolution policy is not specified here.
