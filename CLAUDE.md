# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

PeerModel is a secure capabilities-based peer-to-peer ORM built on OrbitDB and IPFS. It provides encrypted, decentralized data storage with ring-based access control and capability-based security. The system uses cryptographic keys for both identity management and access control, with support for hardware tokens (PIV cards, YubiKeys).

## Development Commands

### Setup
```bash
# Install development dependencies and editable install
make dev

# Or manually:
python -m pip install -e ".[dev,test]"
```

### Testing
```bash
# Run all tests
make test
# Or: pytest

# Run specific test file
pytest peermodel/tests/test_peermodel.py

# Run with coverage
make coverage
```

### Code Quality
```bash
# Lint with flake8
make lint

# Format code (if using black)
black peermodel/
```

### Build and Release
```bash
# Clean build artifacts
make clean

# Build distribution packages
make dist

# Release to PyPI
make release
```

### CLI Usage
```bash
# Management interface
prmdl --help

# Initialize identity
prmdl init

# Ring management
prmdl ring create
prmdl ring list
prmdl ring invite <ring> <identity>
```

## Architecture

### Core Components

**peermodel.py** — Core ORM and database abstractions
- `DocumentObj`: Base mixin for all model objects, provides serialization, UUIDs, and type registry
- `AbstractTypedDocumentDatabase`: Abstract base for database implementations
- `InMemoryDocumentDatabase`: Basic in-memory storage (no encryption, no persistence)
- `InMemoryCapabilitiesDatabase`: In-memory storage with encryption and ring-based access control
- `PersistedDatabase`: IPFS/IPLD persistence layer
- `PersistedCapabilitiesDatabase`: Full implementation with encryption and IPFS persistence
- `App`: Main application class that provides `@model`, `@event`, `@aggregated`, and `@indexed` decorators

**capabilities.py** — Identity and cryptographic key management
- `IdentityManager`: Abstract base for identity providers (hardware tokens, keyring, etc.)
- `Keysystem`: Abstract base for encryption/decryption operations
- `ECDSAKeysystem`: ECDSA-based key exchange implementation
- `UnauthorizedAccess`: Exception raised when decryption fails due to missing keys

**delegation.py** — Ring-based access control
- `Ring`: Abstract base for access control rings (groups with read/write permissions)
  - Members have full read/write access
  - Guests have read-only access
  - Records are encrypted with ring keys
- `Guest`: Interface for guest access management

**iplddict.py** — IPLD/IPFS persistence layer
- `NamespacedIPLDDictionary`: Dict-like interface to IPLD merkle forest
- `SqliteRecordManagerDictionary`: SQLite-backed record storage with multi-db support

**cli.py** — Command-line interface
- Built with Click
- `build_cli()`: Factory function for creating application-specific CLIs
- Ring commands: create, invite, approve, revoke, regenerate
- CRUD commands: create, retrieve, update, delete, tag, publish

### Key Concepts

**Document Model**
- Models are Python dataclasses decorated with `@peer.model`
- Each document gets a unique `_id` (UUID)
- Documents can contain nested documents or references to aggregated documents
- Type registry (`DocumentObj.Meta._reg`) tracks all model classes for deserialization

**Serialization**
- `_to_storage(db)` → `(typename, id, record_dict)`
- `_from_storage(db, id, record)` → document instance
- Aggregated documents are stored by reference: `("Ref", typename, id)`
- Nested documents are stored inline as tuples

**Encryption and Access Control**
- Records are encrypted with a per-record Fernet key
- Record keys are themselves encrypted for each ring member/guest
- Storage format: `[ring_signature, [encrypted_keys...], encrypted_record]`
- Unauthorized access raises `UnauthorizedAccess` with the encryptor's signature

**Ring Model**
- Users belong to rings; rings control access to records
- Default public ring for public records
- Majority approval required for new ring members
- Any member can grant guest (read-only) access
- Key regeneration revokes all previous access

### Testing Patterns

Tests use pytest with hypothesis for property-based testing. Key fixtures:
- `peer`: Creates an `App` instance
- `memdb`: In-memory database context
- `secdb`: In-memory capabilities database with test ring/identity
- `doc`, `complexdoc`, `aggdoc`: Various document types for testing

Test aggregated documents by checking that references are created (starts with `"Ref"`).

Test encryption by verifying that stored content doesn't match plaintext.

## Notes

- The codebase is transitioning away from a JS-based backend (see commented imports of `js2py`, `libp2p`, `helia`, `orbitdb`)
- Hardware token support (PIV, CAC, YubiKeys) is planned but not fully implemented
- See `IMPLEMENTATION_CRYPTOSYSTEM_SPEC.md` for detailed cryptographic architecture plans
- Identity configuration stored in `~/.peermodel/idconfig.json`
- CLI entry point is `prmdl` (defined in `pyproject.toml`)
