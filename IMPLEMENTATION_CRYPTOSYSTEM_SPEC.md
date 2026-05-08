# CohortCrypto — Python Library Specification

## Purpose

A Python library providing cryptographic plumbing for decentralized, multi-institutional data publishing cohorts, intended for use in public health and disease surveillance contexts. Data is published to IPFS; access control and attribution are enforced cryptographically rather than at the application layer.

## Design Philosophy

- **No custom cryptographic primitives.** All cryptographic operations delegate to audited, well-maintained libraries.
- **Legible plumbing, not magic.** Each library function does one coherent thing and is usable independently.
- **Honest trust model.** The library makes no claims about real-world identity. It guarantees integrity and attribution to a keypair, not to a legal entity or person.
- **Hardware-first key custody.** Hardware token support (PIV cards, YubiKeys) is a first-class feature, not an afterthought. Software key fallback exists but is explicitly second-class.
- **IPFS-native.** Content is addressed by CID; mutable state uses IPNS.

---

## Dependencies

| Purpose | Library |
|---|---|
| Asymmetric key operations (signing, key agreement) | `cryptography` (PyCA) |
| Symmetric encryption | `cryptography` (AES-GCM via PyCA) |
| PKCS#11 hardware token interface | `python-pkcs11` |
| PIV card operations | `yubikey-manager` (`ykman`) |
| IPFS interaction | `ipfshttpclient` or `kubo-rpc-client` |
| Serialization | `cbor2` |
| Key derivation | `cryptography` (HKDF, PBKDF2) |

All dependencies declared in `pyproject.toml` with pinned minimum versions. Hardware support is not optional — it is part of the base install. No `[hardware]` extras group; the library assumes hardware token availability and degrades gracefully to software keys with explicit warnings.

---

## Hardware Token Architecture

### Supported Token Classes

The library supports three hardware token classes through a unified abstract interface. All three store private keys in tamper-resistant hardware; private key bytes never appear in Python memory.

**PIV Cards (including U.S. Federal PIV/CAC)**
Standard X.509-based smart cards. The PIV standard defines four key slots; this library uses two:
- Slot 9A (Authentication): used for ECDH key agreement (X25519 equivalent via P-256 ECDH)
- Slot 9C (Digital Signature): used for Ed25519/ECDSA signing

PIV cards are accessed via PKCS#11 middleware. On federal systems, the middleware is typically the OpenSC PKCS#11 module or the official GSA middleware. The library detects available PKCS#11 modules by searching standard system paths and a user-configurable search list.

**YubiKey (5 series and later)**
Supports both PIV applet (PKCS#11-accessible) and OpenPGP applet. The library uses the PIV applet by default for consistency with the PIV card path, but can use the OpenPGP applet if preferred. YubiKey 5 series supports P-256, P-384, and RSA in hardware; Ed25519 is supported in PIV slot 9A on firmware 5.2.3+.

**PKCS#11 tokens (generic)**
Any PKCS#11-compliant token (HSMs, other smart card platforms) is supported through the generic PKCS#11 path. The library does not require knowledge of the specific token type.

### Key Algorithm Constraints

The X25519 key agreement algorithm preferred for envelope encryption is not universally supported in hardware PIV implementations. The library handles this as follows:

- If the token supports X25519 natively (YubiKey 5.2.3+ in PIV slot 9A, some PKCS#11 HSMs): use it directly.
- If the token supports P-256 ECDH but not X25519 (most PIV cards, older YubiKeys): perform ECDH on P-256 in hardware, then pass the resulting shared secret through HKDF to derive the encryption key. The security properties are equivalent; only the curve differs.
- If neither is available: raise `HardwareCapabilityError` with a clear message. Do not silently fall back to software keys for operations that the caller has designated as hardware-required.

Ed25519 for signing follows the same pattern: native Ed25519 if available, P-256 ECDSA otherwise, with the algorithm recorded in the `MemberCredential` so verifiers know which to use.

### PKCS#11 Session Lifecycle

PKCS#11 sessions are stateful and must be managed carefully. The library provides a context manager:

```python
with cohortcrypto.hardware.open_token(
    pkcs11_lib_path: str | None = None,   # None = auto-detect
    slot_id: int | None = None,            # None = first available slot with token
    pin: str | None = None,                # None = prompt interactively
    piv_slot: PIVSlot = PIVSlot.AUTO
) as token_session:
    # token_session is a TokenSession passed to operations requiring hardware
    ...
```

`open_token` performs: library load → slot enumeration → session open → PIN verification (if required by token policy) → slot detection. On exit, it closes the session and logs out. It does not cache the PIN in memory beyond the duration of the `with` block.

For long-lived processes (daemons, servers) that cannot use interactive PIN entry, the library supports PIN providers:

```python
cohortcrypto.hardware.set_pin_provider(callable: Callable[[], str])
```

The callable is invoked when a PIN is needed. Implementers are responsible for secure PIN storage in their environment (e.g. a secrets manager, a hardware security module PIN cache).

### PIV Slot Auto-Detection

When `piv_slot=PIVSlot.AUTO`, the library inspects the token to determine the best available slot:
1. Prefer slot 9A if it contains a key and the key type supports the required operation.
2. Fall back to slot 9C for signing if 9A does not support the signing algorithm.
3. Raise `PIVSlotError` if no usable slot is found, with a message describing what was found and what was needed.

---

## Module Structure

```
cohortcrypto/
    hardware/
        __init__.py         # Public hardware API: open_token, TokenSession, enumerate_tokens
        pkcs11.py           # PKCS#11 session management and operations
        piv.py              # PIV-specific slot logic and certificate handling
        detection.py        # Auto-detection of PKCS#11 libraries and tokens
        exceptions.py       # Hardware-specific exceptions
    primitives.py           # Low-level crypto operations (software path)
    cohort.py               # Cohort lifecycle and membership
    envelope.py             # Envelope encryption/decryption
    signing.py              # Content signing and verification
    ipfs.py                 # IPFS/IPNS publish and fetch
    serialization.py        # CohortRecord and KeyBundle formats
    exceptions.py           # Library-wide exception hierarchy
```

---

## Data Structures

### TokenSession
Represents an open, authenticated session with a hardware token. Opaque to callers; passed to operations that require hardware key access.

```
TokenSession:
    token_type: Literal["piv", "yubikey", "pkcs11_generic"]
    slot_id: int
    signing_key_info: KeyInfo         # algorithm, public key, certificate if present
    encryption_key_info: KeyInfo      # algorithm, public key
    supports_x25519: bool
    supports_ed25519: bool
    firmware_version: str | None      # YubiKey only
```

### KeyInfo
Describes a key slot on a hardware token.

```
KeyInfo:
    algorithm: Literal["ed25519", "p256", "p384", "rsa2048", "rsa4096"]
    public_key: bytes                 # DER-encoded SubjectPublicKeyInfo
    certificate: bytes | None         # DER-encoded X.509 certificate if present
    piv_slot: str | None              # "9A", "9C", etc.
```

### MemberCredential
Represents a cohort member's identity and public keys. Records whether keys are hardware-backed.

```
MemberCredential:
    member_id: str                    # opaque identifier chosen by member
    signing_public_key: bytes         # DER-encoded public key
    signing_algorithm: Literal["ed25519", "p256_ecdsa", "p384_ecdsa"]
    encryption_public_key: bytes      # DER-encoded public key
    encryption_algorithm: Literal["x25519", "p256_ecdh", "p384_ecdh"]
    hardware_backed: bool
    token_type: str | None            # "piv", "yubikey", "pkcs11_generic", or None
    certificate_der: bytes | None     # X.509 certificate if token issued one
    created_at: datetime
```

### CohortIdentity
Represents the cohort's keypair and metadata. The cohort private key is never stored in this structure; it is always held encrypted in a KeyBundle.

```
CohortIdentity:
    cohort_id: str
    signing_public_key: bytes         # DER-encoded Ed25519 or P-256 public key
    signing_algorithm: str
    encryption_public_key: bytes      # DER-encoded X25519 or P-256 public key
    encryption_algorithm: str
    ipns_key_name: str
    created_at: datetime
    keybundle_cid: str                # current KeyBundle CID; updated on membership changes
```

### KeyBundle
The encrypted cohort private key material, with one encrypted copy per authorized member.

```
KeyBundle:
    cohort_id: str
    version: int                      # incremented on each re-key
    signing_alg: str                  # algorithm of the enclosed cohort signing key
    encryption_alg: str               # algorithm of the enclosed cohort encryption key
    entries: List[KeyBundleEntry]

KeyBundleEntry:
    member_id: str
    encrypted_key_material: bytes     # cohort private key material, AES-GCM encrypted
    ephemeral_public_key_der: bytes   # ephemeral public key used in ECDH
    nonce: bytes                      # AES-GCM nonce
    tag: bytes                        # AES-GCM authentication tag
```

### CohortRecord
A signed, optionally encrypted data record published to IPFS.

```
CohortRecord:
    cohort_id: str
    record_id: str                    # UUID
    content_cid: str
    key_bundle_cid: str | None
    is_encrypted: bool
    metadata: dict | None
    signature: bytes
    signing_algorithm: str
    signed_at: datetime
    schema_version: str               # semver; breaking changes require bump
```

### MembershipProposal
A signed proposal to add or expel a member.

```
MembershipProposal:
    proposal_id: str
    cohort_id: str
    action: Literal["add", "expel"]
    subject_member_id: str
    subject_credential: MemberCredential | None   # populated for "add"
    proposed_by: str
    proposed_at: datetime
    votes: List[MembershipVote]

MembershipVote:
    member_id: str
    signature: bytes
    signing_algorithm: str
    voted_at: datetime
```

---

## Module: `hardware/__init__.py`

Public hardware API. All token interaction goes through these functions.

```python
def enumerate_tokens() -> List[TokenInfo]:
    """
    Detect all available hardware tokens on this system.
    Searches for PKCS#11 libraries in standard system paths
    (platform-specific: /usr/lib/*, %WINDIR%\System32\*, etc.)
    plus any paths in COHORTCRYPTO_PKCS11_PATH environment variable.
    Returns a list of TokenInfo describing each detected token.
    Does not open sessions or require PIN.
    """

def open_token(
    pkcs11_lib_path: str | None = None,
    slot_id: int | None = None,
    pin: str | None = None,
    piv_slot: PIVSlot = PIVSlot.AUTO,
    require_hardware_signing: bool = True,
    require_hardware_encryption: bool = True
) -> ContextManager[TokenSession]:
    """
    Context manager. Opens an authenticated session with a hardware token.
    pkcs11_lib_path: path to PKCS#11 .so/.dll. None = auto-detect.
    slot_id: PKCS#11 slot index. None = first slot with a present token.
    pin: token PIN. None = prompt interactively via getpass.
    piv_slot: PIVSlot.AUTO detects best slot; or specify PIVSlot.SLOT_9A, etc.
    require_hardware_*: if True (default), raises HardwareCapabilityError
      if the token cannot perform that operation class in hardware.
      Set False only when testing with software token emulators.
    Raises: TokenNotFoundError, PKCSLibraryNotFoundError, PINError,
            HardwareCapabilityError, PIVSlotError.
    """

def credential_from_token(
    session: TokenSession,
    member_id: str
) -> MemberCredential:
    """
    Create a MemberCredential from an open token session.
    Reads the public keys from the token (and the certificate, if present).
    Sets hardware_backed=True. Does not require the PIN again if the
    session is already authenticated.
    """

def generate_keys_on_token(
    session: TokenSession,
    overwrite: bool = False
) -> TokenSession:
    """
    Generate a new keypair on the hardware token, in-place.
    Generates a signing key in PIV slot 9C and an encryption key in slot 9A.
    Algorithm selection: Ed25519 if firmware supports it, otherwise P-256.
    overwrite: if False (default), raises SlotOccupiedError if the slot
      already contains a key. Set True only with explicit user confirmation.
    Returns an updated TokenSession reflecting the new keys.
    WARNING: Key generation is irreversible. The generated private key
      cannot be exported. If the token is lost, the member must be
      re-enrolled with a new token and new keypair.
    """
```

---

## Module: `hardware/pkcs11.py`

Internal PKCS#11 operations. Not part of the public API; called by `hardware/__init__.py` and `primitives.py`.

```python
def pkcs11_sign(
    session: TokenSession,
    message: bytes
) -> bytes:
    """
    Sign message using the token's signing key slot.
    For Ed25519: signs the message directly (Ed25519 is not prehash by default).
    For P-256 ECDSA: hashes with SHA-256 first, then signs.
    Returns DER-encoded signature for ECDSA; raw 64-byte signature for Ed25519.
    The private key never leaves the hardware.
    """

def pkcs11_ecdh(
    session: TokenSession,
    peer_public_key_der: bytes
) -> bytes:
    """
    Perform ECDH key agreement between the token's encryption key and a
    peer's public key. Returns the raw shared secret bytes.
    The computation occurs on the token; the private key never leaves hardware.
    peer_public_key_der: DER-encoded SubjectPublicKeyInfo of the peer's key.
    """
```

---

## Module: `primitives.py`

Low-level cryptographic operations. Each function accepts either software keys or a `TokenSession` for hardware-backed operations.

```python
def generate_software_keypair() -> tuple[bytes, bytes, bytes, bytes]:
    """
    Generate Ed25519 signing keypair and X25519 encryption keypair in software.
    Returns (signing_private_key_der, signing_public_key_der,
             encryption_private_key_der, encryption_public_key_der).
    Software keys are returned as DER-encoded private key bytes.
    CAUTION: Caller is responsible for secure storage. Hardware tokens are
    strongly preferred. This function should be used only in environments
    where hardware tokens are unavailable, and that fact should be logged.
    """

def derive_symmetric_key(
    shared_secret: bytes,
    salt: bytes,
    info: bytes,
    length: int = 32
) -> bytes:
    """
    Derive a symmetric key from a shared secret using HKDF-SHA256.
    Used internally after ECDH to derive AES keys.
    """

def encrypt_symmetric(plaintext: bytes, key: bytes) -> tuple[bytes, bytes, bytes]:
    """
    AES-256-GCM encryption. Returns (ciphertext, nonce, tag).
    Nonce is 96-bit random, generated fresh per call via os.urandom.
    Never reuse (ciphertext, nonce, tag) tuples or cache nonces.
    """

def decrypt_symmetric(
    ciphertext: bytes,
    key: bytes,
    nonce: bytes,
    tag: bytes
) -> bytes:
    """
    AES-256-GCM decryption. Raises DecryptionError if tag verification fails.
    """

def encrypt_to_recipient(
    plaintext: bytes,
    recipient_credential: MemberCredential,
    session: TokenSession | None = None
) -> tuple[bytes, bytes, bytes, bytes]:
    """
    Encrypt plaintext to a recipient's public key using ECDH + HKDF + AES-GCM.
    Selects the ECDH algorithm based on recipient_credential.encryption_algorithm:
      - x25519: ephemeral X25519 keypair generated in software, ECDH performed,
        shared secret passed through HKDF, plaintext encrypted with AES-256-GCM.
      - p256_ecdh: same pattern on P-256.
    session: unused for encryption (encryption is always to the *recipient's*
      public key; no private key operation needed for the sender).
    Returns (ciphertext, nonce, tag, ephemeral_public_key_der).
    All four values must be stored; none is secret.
    """

def decrypt_from_sender(
    ciphertext: bytes,
    nonce: bytes,
    tag: bytes,
    ephemeral_public_key_der: bytes,
    recipient_credential: MemberCredential,
    session: TokenSession | None = None,
    software_private_key_der: bytes | None = None
) -> bytes:
    """
    Decrypt ciphertext produced by encrypt_to_recipient.
    If session is provided: performs ECDH on the hardware token (private key
      never leaves hardware). software_private_key_der must be None.
    If software_private_key_der is provided: performs ECDH in software.
      session must be None.
    Exactly one of (session, software_private_key_der) must be provided.
    Raises DecryptionError on failure (bad tag, ECDH mismatch, etc.).
    """

def sign_bytes(
    message: bytes,
    credential: MemberCredential,
    session: TokenSession | None = None,
    software_private_key_der: bytes | None = None
) -> bytes:
    """
    Sign arbitrary bytes.
    If session is provided: signing occurs on the hardware token.
    If software_private_key_der is provided: signing occurs in software.
    Exactly one must be provided.
    Returns a signature whose encoding and length depend on the algorithm
    recorded in credential.signing_algorithm. Verifiers must check the
    algorithm field before verifying.
    """

def verify_bytes(
    message: bytes,
    signature: bytes,
    credential: MemberCredential
) -> bool:
    """
    Verify a signature using the public key in credential.
    Selects verification algorithm from credential.signing_algorithm.
    Returns True or False; does not raise on invalid signature.
    Verification is always a public-key operation; no session required.
    """
```

---

## Module: `cohort.py`

Cohort lifecycle and membership management.

```python
def create_cohort(
    cohort_id: str,
    founder_credential: MemberCredential,
    founder_session: TokenSession | None = None,
    founder_software_key_der: bytes | None = None
) -> tuple[CohortIdentity, KeyBundle, bytes]:
    """
    Create a new cohort. Generates a fresh cohort keypair (always in software —
    the cohort keypair is not stored on any single token; it lives encrypted
    in the KeyBundle). Encrypts the cohort private key for the founding member
    using their public key. Signs the initial CohortIdentity with the
    founder's key (hardware or software as specified).
    Returns (CohortIdentity, KeyBundle, cohort_private_key_bytes).
    cohort_private_key_bytes contains both signing and encryption private keys,
    CBOR-serialized. The caller must hold this in memory only for the duration
    of the operation, then zero the buffer. It is not retained by the library.
    """

def add_member(
    cohort_identity: CohortIdentity,
    cohort_private_key_bytes: bytes,
    new_member_credential: MemberCredential,
    existing_keybundle: KeyBundle,
    authorizing_credential: MemberCredential,
    authorizing_session: TokenSession | None = None,
    authorizing_software_key_der: bytes | None = None
) -> KeyBundle:
    """
    Add a new member by encrypting the cohort private key to their public key.
    authorizing_credential: the existing member performing the addition.
    Their signature over (new_member_id, cohort_id, keybundle_version)
    is embedded in the new KeyBundleEntry as an authorization record.
    Returns an updated KeyBundle. Does not modify existing entries.
    Precondition: caller must have already obtained cohort_private_key_bytes
    via get_cohort_private_key, confirming their own membership.
    """

def expel_member(
    cohort_identity: CohortIdentity,
    cohort_private_key_bytes: bytes,
    expelled_member_id: str,
    remaining_credentials: List[MemberCredential],
    authorizing_credential: MemberCredential,
    authorizing_session: TokenSession | None = None,
    authorizing_software_key_der: bytes | None = None
) -> tuple[CohortIdentity, KeyBundle, bytes]:
    """
    Expel a member by generating a new cohort keypair and re-distributing
    to remaining members only. Returns (new_CohortIdentity, new_KeyBundle,
    new_cohort_private_key_bytes). Caller must publish both to IPFS and
    update the IPNS pointer.
    The expelled member's entry does not appear in the new KeyBundle.
    NOTE: Forward secrecy only. Past records encrypted under the old
    cohort key remain accessible to the expelled member if they retained
    a copy. This is by design and must be documented clearly to users.
    """

def get_cohort_private_key(
    keybundle: KeyBundle,
    member_credential: MemberCredential,
    session: TokenSession | None = None,
    software_private_key_der: bytes | None = None
) -> bytes:
    """
    Retrieve and decrypt the cohort private key from a KeyBundle.
    Finds the entry for member_credential.member_id, then decrypts
    using the member's encryption key (hardware or software).
    Raises NotAuthorizedError if no matching entry exists.
    Raises DecryptionError if decryption fails.
    """

def create_membership_proposal(
    action: Literal["add", "expel"],
    subject_member_id: str,
    cohort_id: str,
    proposer_credential: MemberCredential,
    proposer_session: TokenSession | None = None,
    proposer_software_key_der: bytes | None = None,
    subject_credential: MemberCredential | None = None
) -> MembershipProposal:
    """
    Create a signed membership proposal. The proposer's vote is included
    automatically. For "add" actions, subject_credential must be provided.
    """

def vote_on_proposal(
    proposal: MembershipProposal,
    voter_credential: MemberCredential,
    voter_session: TokenSession | None = None,
    voter_software_key_der: bytes | None = None
) -> MembershipProposal:
    """
    Add a signed vote to a proposal. Returns updated proposal.
    Raises DuplicateVoteError if voter has already voted.
    Signatures are over: proposal_id + action + subject_member_id + voted_at.
    """

def check_proposal_outcome(
    proposal: MembershipProposal,
    current_credentials: List[MemberCredential],
    threshold: float = 0.5
) -> Literal["approved", "rejected", "pending"]:
    """
    Evaluate proposal outcome. Verifies all vote signatures before counting.
    Invalid signatures are excluded from the count (not an error; a bad
    signature is treated as a non-vote). threshold is fraction of current
    membership required; default 0.5 is simple majority.
    """
```

---

## Module: `envelope.py`

Encrypt and decrypt content using the envelope pattern.

```python
def encrypt_record(
    plaintext: bytes,
    cohort_private_key_bytes: bytes,
    cohort_identity: CohortIdentity,
    authorized_credentials: List[MemberCredential],
    authorizing_credential: MemberCredential,
    authorizing_session: TokenSession | None = None,
    authorizing_software_key_der: bytes | None = None
) -> tuple[bytes, KeyBundle]:
    """
    Encrypt plaintext for a set of authorized recipients.
    1. Generate a fresh 256-bit symmetric content key via os.urandom.
    2. Encrypt plaintext with AES-256-GCM.
    3. For each authorized member, encrypt the content key to their
       public key using encrypt_to_recipient.
    4. Sign the (ciphertext_hash, member_id_list, timestamp) with the
       cohort signing key.
    Returns (ciphertext_bytes, KeyBundle).
    Both should be published to IPFS; CIDs go into a CohortRecord.
    """

def decrypt_record(
    ciphertext: bytes,
    keybundle: KeyBundle,
    cohort_private_key_bytes: bytes,
    member_credential: MemberCredential,
    session: TokenSession | None = None,
    software_private_key_der: bytes | None = None
) -> bytes:
    """
    Decrypt a record using the caller's member credential.
    Finds the caller's KeyBundleEntry, decrypts the content key using
    their encryption key (hardware or software), then decrypts the ciphertext.
    Raises NotAuthorizedError if no matching entry found.
    Raises DecryptionError if AES-GCM tag verification fails.
    """

def encrypt_file(
    file_path: Path,
    cohort_private_key_bytes: bytes,
    cohort_identity: CohortIdentity,
    authorized_credentials: List[MemberCredential],
    authorizing_credential: MemberCredential,
    authorizing_session: TokenSession | None = None,
    authorizing_software_key_der: bytes | None = None,
    chunk_size: int = 1024 * 1024
) -> tuple[Path, KeyBundle]:
    """
    Streaming encryption for large files (bulk genomic sequencing data, etc.).
    Uses a single content key for the whole file, but encrypts in chunks.
    Each chunk's AES-GCM AAD includes: chunk_index (big-endian uint64) +
    file_content_hash + total_chunk_count. This prevents reordering,
    truncation, and splicing attacks across chunks.
    chunk_size defaults to 1MB. Written to a temp file alongside the input.
    Returns (encrypted_file_path, KeyBundle).
    """

def decrypt_file(
    encrypted_file_path: Path,
    output_path: Path,
    keybundle: KeyBundle,
    cohort_private_key_bytes: bytes,
    member_credential: MemberCredential,
    session: TokenSession | None = None,
    software_private_key_der: bytes | None = None
) -> None:
    """
    Streaming file decryption. Validates each chunk's AAD and GCM tag before
    writing to output_path. On any chunk failure, raises DecryptionError and
    deletes the partial output file. Caller must not use a partial output.
    """
```

---

## Module: `signing.py`

Content signing and verification.

```python
def sign_cid(
    cid: str,
    cohort_identity: CohortIdentity,
    cohort_private_key_bytes: bytes,
    metadata: dict | None = None
) -> CohortRecord:
    """
    Sign an IPFS CID on behalf of a cohort for public (unencrypted) content.
    Signed payload (canonical_signing_bytes): CBOR encoding of
    {cid, cohort_id, schema_version, signed_at (ISO8601), metadata_sha256}.
    """

def sign_encrypted_record(
    content_cid: str,
    key_bundle_cid: str,
    cohort_identity: CohortIdentity,
    cohort_private_key_bytes: bytes,
    metadata: dict | None = None
) -> CohortRecord:
    """
    As sign_cid but for encrypted records. Includes key_bundle_cid in the
    signed payload so tampering with the key bundle is detectable.
    """

def verify_record(
    record: CohortRecord,
    cohort_identity: CohortIdentity
) -> bool:
    """
    Verify the cohort's signature on a CohortRecord.
    Uses cohort_identity.signing_algorithm to select the verification method.
    Returns True if valid. Does not fetch or verify content.
    Caller must separately verify that the content at content_cid hashes to
    the value recorded in the record. This function only verifies the
    record's internal signature.
    """
```

---

## Module: `ipfs.py`

Thin wrapper around IPFS/IPNS operations.

```python
def publish_bytes(data: bytes, ipfs_client) -> str:
def publish_cbor(obj: dict, ipfs_client) -> str:
def fetch_bytes(cid: str, ipfs_client) -> bytes:
def fetch_cbor(cid: str, ipfs_client) -> dict:
def publish_record(record: CohortRecord, ipfs_client) -> str:
def fetch_record(cid: str, ipfs_client) -> CohortRecord:

def update_ipns(
    ipns_key_name: str,
    cid: str,
    ipfs_client,
    ttl: str = "24h"
) -> str:
    """
    Update an IPNS name to point to a new CID. The IPNS key must be
    registered with the local IPFS node (ipfs key gen). Returns the
    IPNS address. Used to update cohort's mutable pointer after
    re-keying or new publications.
    """

def resolve_ipns(ipns_address: str, ipfs_client) -> str:
    """Resolve an IPNS address to its current CID."""
```

---

## Module: `serialization.py`

Canonical serialization for all data structures.

```python
def serialize_cohort_identity(identity: CohortIdentity) -> bytes:
def deserialize_cohort_identity(data: bytes) -> CohortIdentity:
def serialize_keybundle(bundle: KeyBundle) -> bytes:
def deserialize_keybundle(data: bytes) -> KeyBundle:
def serialize_record(record: CohortRecord) -> bytes:
def deserialize_record(data: bytes) -> CohortRecord:
def serialize_member_credential(cred: MemberCredential) -> bytes:
def deserialize_member_credential(data: bytes) -> MemberCredential:
def serialize_proposal(proposal: MembershipProposal) -> bytes:
def deserialize_proposal(data: bytes) -> MembershipProposal:

def canonical_signing_bytes(record: CohortRecord) -> bytes:
    """
    Authoritative definition of the byte string that is signed and verified
    for a CohortRecord. Stable across patch versions; breaking changes
    require schema_version bump. Uses CBOR canonical encoding (RFC 7049
    section 3.9) to ensure identical output across platforms.
    """
```

---

## Module: `exceptions.py`

```python
class CohortCryptoError(Exception): ...
class DecryptionError(CohortCryptoError): ...
class NotAuthorizedError(CohortCryptoError): ...
class InvalidSignatureError(CohortCryptoError): ...
class DuplicateVoteError(CohortCryptoError): ...
class QuorumNotReachedError(CohortCryptoError): ...
class SerializationError(CohortCryptoError): ...

# Hardware-specific
class HardwareError(CohortCryptoError): ...
class TokenNotFoundError(HardwareError): ...
class PKCSLibraryNotFoundError(HardwareError): ...
class PINError(HardwareError): ...
class HardwareCapabilityError(HardwareError): ...  # token doesn't support required operation
class PIVSlotError(HardwareError): ...             # slot empty, wrong type, or occupied
class SlotOccupiedError(PIVSlotError): ...
class SessionExpiredError(HardwareError): ...      # PKCS#11 session invalidated
```

---

## Security Notes for Implementer

**Private key memory hygiene.** Functions that return `cohort_private_key_bytes` or software key DER bytes expect the caller to hold these in memory only for the duration of the operation. Use `bytearray` rather than `bytes` so the buffer can be explicitly zeroed with `buf[:] = b'\x00' * len(buf)` after use. Document this expectation loudly in the API.

**Hardware key operations never return private material.** `pkcs11_sign` and `pkcs11_ecdh` return outputs (signatures, shared secrets) but never private key bytes. If a function signature would require returning a private key from a hardware operation, the design is wrong.

**Nonce uniqueness.** AES-GCM is catastrophically broken by nonce reuse under the same key. The library generates fresh 96-bit nonces via `os.urandom` per call. Never cache, serialize, or reuse nonce values. In `encrypt_file`, each chunk gets an independent nonce; the chunk index is in the AAD, not the nonce.

**Chunk AAD is mandatory.** The chunk index, total chunk count, and file hash in each chunk's AAD are not optional safety theater. Without them, an adversary can reorder chunks, truncate the file, or splice chunks from different encrypted files, and each individual chunk's GCM tag still passes. The AAD makes these attacks detectable.

**`verify_record` does not fetch content.** Callers must separately verify the content at `content_cid` matches the recorded CID. This is intentional separation of concerns and must be documented prominently.

**PKCS#11 sessions can be invalidated by token removal.** Long-lived processes should catch `SessionExpiredError` and re-open the session. The library does not auto-reconnect.

**PIV certificate chains.** When a PIV card presents an X.509 certificate, the library stores it in `MemberCredential.certificate_der` but does not validate the certificate chain. Chain validation is out of scope; the library makes no identity claims. If a caller wants to validate the chain (e.g. to confirm a federal PIV certificate chains to a known GSA root), they should do so using the `cryptography` library's X.509 facilities on the stored DER bytes.

**Expulsion is forward secrecy only.** Past content encrypted under the old cohort key remains decryptable by the expelled member if they retained a copy. Re-keying protects future content only. This must be communicated clearly to end users; the library should emit a warning log on every `expel_member` call.

---

## Out of Scope

- **Voting enforcement.** `check_proposal_outcome` returns an assessment; it does not prevent operations from executing without a passing vote. Enforcement is the caller's responsibility.
- **IPFS node management.**
- **Key backup and recovery.** Users should understand that hardware token loss means loss of membership access until re-enrolled with a new token via majority vote.
- **Certificate chain validation.**
- **Real-world identity binding.**
