"""Record signing and verification structures."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any


@dataclass
class CohortRecord:
    """Signed record with metadata and content references."""
    cohort_id: str
    record_id: str
    content_cid: str
    key_bundle_cid: str
    is_encrypted: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature: bytes = b''
    signing_algorithm: str = "ed25519"
    signed_at: datetime = None
    schema_version: str = "1.0.0"

    def __post_init__(self):
        if self.signed_at is None:
            self.signed_at = datetime.utcnow()
