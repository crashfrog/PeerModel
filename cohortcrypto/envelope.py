"""Envelope encryption data structures."""

from dataclasses import dataclass
from typing import List


@dataclass
class KeyBundleEntry:
    """An encrypted copy of the cohort key for a single member."""
    member_id: str
    encrypted_key_material: bytes
    ephemeral_public_key_der: bytes
    nonce: bytes
    tag: bytes


@dataclass
class KeyBundle:
    """The encrypted cohort private key material with one copy per authorized member."""
    cohort_id: str
    version: int
    signing_alg: str
    encryption_alg: str
    entries: List[KeyBundleEntry]
