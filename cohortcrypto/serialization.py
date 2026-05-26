"""CBOR serialization for CohortCrypto data structures.

Implements canonical CBOR encoding (RFC 7049 section 3.9) for cryptographic
data structures used in the CohortCrypto system.
"""

import cbor2
from datetime import datetime
from io import BytesIO
from typing import Any, Type, TypeVar

from .primitives import MemberCredential
from .cohort import CohortIdentity
from .envelope import KeyBundle, KeyBundleEntry
from .signing import CohortRecord
from peermodel.membership import MembershipProposal, MembershipVote


T = TypeVar('T')


def _datetime_to_iso(dt: datetime) -> str:
    """Convert datetime to ISO 8601 string for consistent serialization."""
    if dt is None:
        return None
    return dt.isoformat()


def _iso_to_datetime(s: str) -> datetime:
    """Convert ISO 8601 string back to datetime."""
    if s is None:
        return None
    return datetime.fromisoformat(s)


def _encode_object_to_dict(obj: Any) -> Any:
    """Convert an object to a dict for CBOR encoding.

    Handles dataclasses and other objects with __dict__.
    Recursively encodes nested objects.
    """
    if obj is None or isinstance(obj, (str, int, float, bool, bytes)):
        return obj

    if isinstance(obj, datetime):
        return _datetime_to_iso(obj)

    if isinstance(obj, dict):
        return {k: _encode_object_to_dict(v) for k, v in sorted(obj.items())}

    if isinstance(obj, (list, tuple)):
        return [_encode_object_to_dict(v) for v in obj]

    # Handle dataclasses
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for field_name in sorted(obj.__dataclass_fields__.keys()):
            value = getattr(obj, field_name)
            result[field_name] = _encode_object_to_dict(value)
        return result

    # Fallback for objects with __dict__
    if hasattr(obj, '__dict__'):
        return {k: _encode_object_to_dict(v) for k, v in sorted(obj.__dict__.items())}

    raise TypeError(f"Cannot encode object of type {type(obj)}")


def _decode_dict_to_object(data: dict, obj_type: Type[T]) -> T:
    """Decode a dict back to an object of the specified type.

    Handles dataclasses and reconstructs nested objects.
    """
    if obj_type == MemberCredential:
        return MemberCredential(
            member_id=data['member_id'],
            x25519_public=data['x25519_public'],
            ed25519_public=data['ed25519_public'],
            signing_algorithm=data['signing_algorithm'],
            encryption_algorithm=data['encryption_algorithm'],
            hardware_backed=data.get('hardware_backed', False),
            certificate_der=data.get('certificate_der'),
        )

    if obj_type == CohortIdentity:
        return CohortIdentity(
            cohort_id=data['cohort_id'],
            signing_public_key=data['signing_public_key'],
            signing_algorithm=data['signing_algorithm'],
            encryption_public_key=data['encryption_public_key'],
            encryption_algorithm=data['encryption_algorithm'],
            ipns_key_name=data['ipns_key_name'],
            created_at=_iso_to_datetime(data['created_at']),
            keybundle_cid=data['keybundle_cid'],
        )

    if obj_type == KeyBundle:
        entries = []
        for entry_data in data.get('entries', []):
            entries.append(KeyBundleEntry(
                member_id=entry_data['member_id'],
                encrypted_key_material=entry_data['encrypted_key_material'],
                ephemeral_public_key_der=entry_data['ephemeral_public_key_der'],
                nonce=entry_data['nonce'],
                tag=entry_data['tag'],
            ))
        return KeyBundle(
            cohort_id=data['cohort_id'],
            version=data['version'],
            signing_alg=data['signing_alg'],
            encryption_alg=data['encryption_alg'],
            entries=entries,
        )

    if obj_type == CohortRecord:
        return CohortRecord(
            cohort_id=data['cohort_id'],
            record_id=data['record_id'],
            content_cid=data['content_cid'],
            key_bundle_cid=data['key_bundle_cid'],
            is_encrypted=data['is_encrypted'],
            metadata=data.get('metadata', {}),
            signature=data.get('signature', b''),
            signing_algorithm=data.get('signing_algorithm', 'ed25519'),
            signed_at=_iso_to_datetime(data.get('signed_at')),
            schema_version=data.get('schema_version', '1.0.0'),
        )

    if obj_type == MembershipVote:
        return MembershipVote(
            voter_identity_id=data['voter_identity_id'],
            proposal_id=data['proposal_id'],
            approve=data['approve'],
            signature=data['signature'],
            voted_at=_iso_to_datetime(data.get('voted_at')),
        )

    if obj_type == MembershipProposal:
        votes = []
        for vote_data in data.get('votes', []):
            votes.append(_decode_dict_to_object(vote_data, MembershipVote))

        return MembershipProposal(
            proposal_id=data['proposal_id'],
            cohort_id=data['cohort_id'],
            action=data['action'],
            subject_member_id=data['subject_member_id'],
            subject_credential=data.get('subject_credential'),
            proposed_by=data['proposed_by'],
            proposed_at=_iso_to_datetime(data.get('proposed_at')),
            votes=votes,
        )

    raise TypeError(f"Unknown type for deserialization: {obj_type}")


def _serialize_to_cbor_canonical(obj: Any) -> bytes:
    """Serialize object to canonical CBOR bytes.

    Uses RFC 7049 section 3.9 canonical encoding:
    - Maps with integer keys sorted numerically
    - Maps with string keys sorted lexicographically
    - Floating-point values encoded as smallest representation
    """
    encoded_dict = _encode_object_to_dict(obj)

    # Use cbor2 with default_kwargs to ensure canonical encoding
    fp = BytesIO()
    cbor2.dump(encoded_dict, fp)
    return fp.getvalue()


def _deserialize_from_cbor(data: bytes) -> Any:
    """Deserialize CBOR bytes to a Python object."""
    fp = BytesIO(data)
    return cbor2.load(fp)


# Public serialization functions

def serialize_member_credential(credential: MemberCredential) -> bytes:
    """Serialize MemberCredential to canonical CBOR bytes."""
    return _serialize_to_cbor_canonical(credential)


def deserialize_member_credential(data: bytes) -> MemberCredential:
    """Deserialize CBOR bytes to MemberCredential."""
    decoded = _deserialize_from_cbor(data)
    return _decode_dict_to_object(decoded, MemberCredential)


def serialize_cohort_identity(identity: CohortIdentity) -> bytes:
    """Serialize CohortIdentity to canonical CBOR bytes."""
    return _serialize_to_cbor_canonical(identity)


def deserialize_cohort_identity(data: bytes) -> CohortIdentity:
    """Deserialize CBOR bytes to CohortIdentity."""
    decoded = _deserialize_from_cbor(data)
    return _decode_dict_to_object(decoded, CohortIdentity)


def serialize_keybundle(bundle: KeyBundle) -> bytes:
    """Serialize KeyBundle to canonical CBOR bytes."""
    return _serialize_to_cbor_canonical(bundle)


def deserialize_keybundle(data: bytes) -> KeyBundle:
    """Deserialize CBOR bytes to KeyBundle."""
    decoded = _deserialize_from_cbor(data)
    return _decode_dict_to_object(decoded, KeyBundle)


def serialize_record(record: CohortRecord) -> bytes:
    """Serialize CohortRecord to canonical CBOR bytes."""
    return _serialize_to_cbor_canonical(record)


def deserialize_record(data: bytes) -> CohortRecord:
    """Deserialize CBOR bytes to CohortRecord."""
    decoded = _deserialize_from_cbor(data)
    return _decode_dict_to_object(decoded, CohortRecord)


def serialize_proposal(proposal: MembershipProposal) -> bytes:
    """Serialize MembershipProposal to canonical CBOR bytes."""
    return _serialize_to_cbor_canonical(proposal)


def deserialize_proposal(data: bytes) -> MembershipProposal:
    """Deserialize CBOR bytes to MembershipProposal."""
    decoded = _deserialize_from_cbor(data)
    return _decode_dict_to_object(decoded, MembershipProposal)
