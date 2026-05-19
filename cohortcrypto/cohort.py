"""Cohort identity and lifecycle management."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CohortIdentity:
    """Represents a cohort's identity and public keys."""
    cohort_id: str
    signing_public_key: bytes
    signing_algorithm: str
    encryption_public_key: bytes
    encryption_algorithm: str
    ipns_key_name: str
    created_at: datetime
    keybundle_cid: str
