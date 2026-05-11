# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

PeerModel is a secure capabilities-based peer-to-peer ORM built on IPFS. It provides encrypted, decentralized data storage with cohort-based access control and capability-based security. The system uses cryptographic keys for both identity management and access control, with support for hardware tokens (PIV cards, YubiKeys).

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

# Hardware token management (Phase 3)
prmdl token list          # List available PIV cards / YubiKeys
prmdl token init          # Initialize identity from hardware token
prmdl token info          # Show details of connected hardware token
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
  - `SoftwareIdentityManager`: Stores keypairs in `~/.peermodel/idconfig.json`
  - `HardwareIdentityManager`: Wraps hardware token sessions (Phase 3)
- `Keysystem`: Abstract base for encryption/decryption operations
  - `SoftwareKeysystem`: Uses software X25519/Ed25519 keypairs (Phase 1)
  - `HardwareKeysystem`: Uses PKCS#11 hardware tokens for decryption (Phase 3)
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
- Token commands (Phase 3): list, init, info (hardware token management)

**cohortcrypto/** — Hardware token cryptography (Phase 3+)
- `hardware/detection.py`: Platform-specific PKCS#11 library detection
- `hardware/piv.py`: PIV slot detection and selection
- `hardware/mock.py`: Mock hardware for testing without real tokens
- `exceptions.py`: Hardware-specific exceptions (PINError, TokenNotFoundError, etc.)

**primitives.py** — Cryptographic primitives (Phase 1+)
- `MemberCredential`: Dataclass for member identity and public keys
- `generate_keypair()`: Generate X25519 and Ed25519 keypairs
- `encrypt_to_recipient()`: Ephemeral ECDH + HKDF + Fernet
- `decrypt_from_sender()`: ECDH recovery + HKDF + Fernet
- `sign_bytes()` / `verify_bytes()`: Ed25519 signatures

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
  
- **Hardware Token Support**: PIV/CAC/YubiKey integration via PKCS#11 (Phase 3 COMPLETE)
  - Phase 3A: Mock hardware infrastructure (✓ complete)
  - Phase 3B: Hardware detection and PIV slot management (✓ complete)
  - Phase 3C: Hardware keysystem and CLI integration (✓ complete)
  - Phase 3D: CLI identity persistence and management (✓ complete)
  - Phase 3E: Real PKCS#11 implementation (✓ complete)
  
  **CLI Commands** (Phase 3D):
  - `prmdl init --hardware`: Initialize identity from hardware token
  - `prmdl init --software`: Initialize software-based identity
  - `prmdl identity show`: Display current identity
  - `prmdl identity delete`: Remove identity configuration
  - `prmdl token select --slot-id N`: Set active token for multi-token systems
  - `prmdl token delete --token-serial S`: Remove hardware token configuration
  
  **Testing**:
  - Mock hardware: `COHORTCRYPTO_MOCK_HARDWARE=1` (default for all tests)
  - Real hardware: Unset env var and have PIV card/YubiKey connected
  - Test with mock: All tests pass without requiring hardware
  - Real hardware tests: Marked with `@pytest.mark.hardware` (skipped by default)
  
  **PKCS#11 Support**:
  - `RealTokenSession` class wraps python-pkcs11 sessions
  - `open_pkcs11_session()` opens real hardware tokens
  - On-token signing and ECDH (private keys never exported)
  - Transparent fallback to mock when hardware unavailable

- **Legacy Code**: Commented imports of `js2py`, `libp2p`, `helia`, `orbitdb` are from earlier JS-based backend; safe to ignore or remove when refactoring.

- **Configuration**: Identity and cohort state stored in `~/.peermodel/idconfig.json` and SQLite databases (location depends on cohort).

- **CLI Entry Point**: `prmdl` command-line tool (defined in `pyproject.toml`); see `peermodel/cli.py` for `build_cli()` factory.

- **Python Version**: Requires Python 3.7+; uses dataclass syntax and type hints extensively.
