"""Key envelope structures for cohort key distribution."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class KeyBundleEntry:
    """Encrypted key material for a single cohort member."""
    member_id: str
    encrypted_key_material: bytes
    ephemeral_public_key_der: bytes
    nonce: bytes
    tag: bytes


@dataclass
class KeyBundle:
    """Collection of encrypted keys for all cohort members."""
    cohort_id: str
    version: int
    signing_alg: str  # "ed25519" or "p256_ecdsa"
    encryption_alg: str  # "x25519" or "p256_ecdh"
    entries: List[KeyBundleEntry] = field(default_factory=list)
