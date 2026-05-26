"""Cohort identity and membership structures."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CohortIdentity:
    """Cohort cryptographic identity and metadata."""
    cohort_id: str
    signing_public_key: bytes
    signing_algorithm: str  # "ed25519" or "p256_ecdsa"
    encryption_public_key: bytes
    encryption_algorithm: str  # "x25519" or "p256_ecdh"
    ipns_key_name: str
    created_at: datetime
    keybundle_cid: str
