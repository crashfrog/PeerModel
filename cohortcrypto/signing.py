"""Content signing and verification data structures."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CohortRecord:
    """A signed, optionally encrypted data record published to IPFS."""
    cohort_id: str
    record_id: str
    content_cid: str
    key_bundle_cid: str
    is_encrypted: bool
    metadata: Optional[dict]
    signature: bytes
    signing_algorithm: str
    signed_at: datetime
    schema_version: str
