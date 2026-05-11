# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

PeerModel is a secure capabilities-based peer-to-peer ORM built on OrbitDB and IPFS. It provides encrypted, decentralized data storage with cohort-based access control and capability-based security. The system uses cryptographic keys for both identity management and access control, with support for hardware tokens (PIV cards, YubiKeys).

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

# Run a single test
pytest peermodel/tests/test_peermodel.py::test_function_name

# Run with coverage
make coverage

# Run with verbose output and stop on first failure
pytest -v -x
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

# Cohort management
prmdl cohort create
prmdl cohort list
prmdl cohort invite <cohort> <identity>
```

## Architecture

### Module Dependency Graph

```
App (peermodel.py)
├── IdentityManager (capabilities.py)
├── Keysystem (capabilities.py)
├── Cohort & Guest (delegation.py)
└── Database implementations (peermodel.py)
    ├── NamespacedIPLDDictionary (iplddict.py)
    └── Fernet encryption (cryptography)

CLI (cli.py)
├── App
└── Cohort commands
```

### Core Components

**peermodel.py** — Core ORM and database abstractions
- `DocumentObj`: Base mixin for all model objects, provides serialization, UUIDs, and type registry
- `AbstractTypedDocumentDatabase`: Abstract base for database implementations
- `InMemoryDocumentDatabase`: Basic in-memory storage (no encryption, no persistence)
- `InMemoryCapabilitiesDatabase`: In-memory storage with encryption and cohort-based access control
- `PersistedDatabase`: IPFS/IPLD persistence layer
- `PersistedCapabilitiesDatabase`: Full implementation with encryption and IPFS persistence
- `App`: Main application class that provides `@model`, `@event`, `@aggregated`, and `@indexed` decorators

**capabilities.py** — Identity and cryptographic key management
- `IdentityManager`: Abstract base for identity providers (hardware tokens, keyring, etc.)
- `Keysystem`: Abstract base for encryption/decryption operations
- `ECDSAKeysystem`: ECDSA-based key exchange implementation
- `UnauthorizedAccess`: Exception raised when decryption fails due to missing keys

**delegation.py** — Cohort-based access control (NEW — part of cryptosystem architecture)
- `Cohort`: Abstract base for access control cohorts (groups with read/write permissions)
  - Members have full read/write access
  - Guests have read-only access
  - Records are encrypted with cohort keys
- `SimpleCohort`: Concrete implementation with membership proposals and voting
- `Guest`: Interface for guest access management

**membership.py** — Membership proposal and voting structures (NEW — Phase 2)
- `MembershipProposal`: Data structure for add/expel proposals with voting
- `MembershipVote`: Cryptographically signed vote on a proposal

**iplddict.py** — IPLD/IPFS persistence layer (NEW — part of cryptosystem architecture)
- `NamespacedIPLDDictionary`: Dict-like interface to IPLD merkle forest
- `SqliteRecordManagerDictionary`: SQLite-backed record storage with multi-db support

**cli.py** — Command-line interface
- Built with Click
- `build_cli()`: Factory function for creating application-specific CLIs
- Cohort commands: create, invite, vote, approve, revoke, regenerate
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
- Record keys are themselves encrypted for each cohort member/guest
- Storage format: `[cohort_signature, [encrypted_keys...], encrypted_record]`
- Unauthorized access raises `UnauthorizedAccess` with the encryptor's signature

**Cohort Model**
- Users belong to cohorts; cohorts control access to records
- Default public cohort for public records
- Majority approval (>50%) required for new cohort members
- Membership decisions use cryptographically signed voting
- Any member can grant guest (read-only) access
- Key regeneration revokes all previous access (forward secrecy)
- Expelled members cannot decrypt records created after expulsion

### Testing Patterns

Tests use pytest with hypothesis for property-based testing. Test fixtures are defined in test files:

- `peer`: Creates an `App` instance with default model decorators
- `memdb`: In-memory database context (no encryption, no persistence)
- `secdb`: In-memory capabilities database with test cohort/identity (encryption enabled)
- `test_cohort`: Single-founder cohort for membership tests
- `multi_member_cohort`: Two-member cohort for voting tests
- `alice_identity`, `bob_identity`, `carol_identity`: Generated identities with keypairs

**Aggregated documents**: References are stored as `("Ref", typename, id)`. Assert that stored content matches this pattern.

**Encryption**: Verify that stored content in encrypted databases doesn't match plaintext by checking the storage format: `[cohort_signature, [encrypted_keys...], encrypted_record]`.

**Cohort access control**: Use fixtures with pre-configured cohorts and verify that unauthorized members raise `UnauthorizedAccess` when attempting to decrypt.

**Membership proposals**: Test voting thresholds (majority >50%), signature verification, and forward secrecy on expulsion.

## Notes

- **Cryptosystem Architecture**: The repo is implementing a multi-institutional cohort-based cryptosystem. See `IMPLEMENTATION_CRYPTOSYSTEM_SPEC.md` for the complete specification, including hardware token support (PIV, YubiKey, PKCS#11), envelope encryption, and membership voting. The `delegation.py` and `iplddict.py` modules are key to this implementation.
  
- **Hardware Token Support**: PIV/CAC/YubiKey integration is designed but not yet fully integrated into the ORM layer. The spec defines the API but production code is still being written.

- **Legacy Code**: Commented imports of `js2py`, `libp2p`, `helia`, `orbitdb` are from earlier JS-based backend; safe to ignore or remove when refactoring.

- **Configuration**: Identity and cohort state stored in `~/.peermodel/idconfig.json` and SQLite databases (location depends on cohort).

- **CLI Entry Point**: `prmdl` command-line tool (defined in `pyproject.toml`); see `peermodel/cli.py` for `build_cli()` factory.

- **Python Version**: Requires Python 3.7+; uses dataclass syntax and type hints extensively.
