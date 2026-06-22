"""CohortRecord signing for public and encrypted records.

Cohort signs records using its Ed25519 private key.
Canonical signing bytes are CBOR-encoded for determinism.
"""

import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import cbor2

from peermodel import primitives


@dataclass
class CohortRecord:
    """Signed record envelope produced by a cohort."""
    cohort_id: str
    record_id: str
    content_cid: str
    key_bundle_cid: Optional[str]
    is_encrypted: bool
    metadata: Optional[dict]
    signature: bytes
    signing_algorithm: str
    signed_at: datetime
    schema_version: str


def _canonical_signing_bytes(record: CohortRecord) -> bytes:
    """Return deterministic CBOR bytes over the signable fields."""
    signable = {
        "cohort_id": record.cohort_id,
        "record_id": record.record_id,
        "content_cid": record.content_cid,
        "key_bundle_cid": record.key_bundle_cid,
        "is_encrypted": record.is_encrypted,
        "signing_algorithm": record.signing_algorithm,
        "signed_at": record.signed_at.isoformat(),
        "schema_version": record.schema_version,
    }
    buf = io.BytesIO()
    cbor2.dump(signable, buf, canonical=True)
    return buf.getvalue()


def sign_cid(
    cid: str,
    metadata: Optional[dict],
    cohort,
    record_id: Optional[str] = None,
    schema_version: str = "1.0.0",
) -> CohortRecord:
    """Sign a public record CID with the cohort's Ed25519 key.

    Args:
        cid: Content identifier of the public record
        metadata: Optional metadata dict
        cohort: SimpleCohort instance with signing key
        record_id: Optional record ID (generated if omitted)
        schema_version: Schema version string

    Returns:
        CohortRecord with signature over (cohort_id, record_id, content_cid, ...)
    """
    record = CohortRecord(
        cohort_id=cohort.cohort_id,
        record_id=record_id or str(uuid4()),
        content_cid=cid,
        key_bundle_cid=None,
        is_encrypted=False,
        metadata=metadata,
        signature=b"",
        signing_algorithm="ed25519",
        signed_at=datetime.now(timezone.utc),
        schema_version=schema_version,
    )
    record.signature = cohort.sign_cohort_message(_canonical_signing_bytes(record))
    return record


def sign_encrypted_record(
    content_cid: str,
    key_bundle_cid: str,
    cohort,
    record_id: Optional[str] = None,
    schema_version: str = "1.0.0",
    metadata: Optional[dict] = None,
) -> CohortRecord:
    """Sign an encrypted record's content_cid + key_bundle_cid.

    Args:
        content_cid: CID of the encrypted content blob
        key_bundle_cid: CID of the key bundle for member access
        cohort: SimpleCohort instance with signing key
        record_id: Optional record ID (generated if omitted)
        schema_version: Schema version string
        metadata: Optional metadata dict

    Returns:
        CohortRecord with signature over
        (cohort_id, record_id, content_cid, key_bundle_cid, ...)
    """
    record = CohortRecord(
        cohort_id=cohort.cohort_id,
        record_id=record_id or str(uuid4()),
        content_cid=content_cid,
        key_bundle_cid=key_bundle_cid,
        is_encrypted=True,
        metadata=metadata,
        signature=b"",
        signing_algorithm="ed25519",
        signed_at=datetime.now(timezone.utc),
        schema_version=schema_version,
    )
    record.signature = cohort.sign_cohort_message(_canonical_signing_bytes(record))
    return record


def verify_cohort_record(record: CohortRecord, cohort_ed25519_public_key_der: bytes) -> bool:
    """Verify a CohortRecord's signature against the cohort's public key.

    Args:
        record: CohortRecord to verify
        cohort_ed25519_public_key_der: DER-encoded Ed25519 public key

    Returns:
        True if signature is valid, False otherwise
    """
    message = _canonical_signing_bytes(record)
    return primitives.verify_bytes(
        message,
        record.signature,
        cohort_ed25519_public_key_der,
        algorithm="ed25519",
    )
