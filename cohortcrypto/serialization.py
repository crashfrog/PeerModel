"""Canonical CBOR serialization for all CohortCrypto data structures.

All serialization uses canonical CBOR encoding (RFC 7049 section 3.9) to ensure
identical output across platforms and multiple serializations.
"""

import cbor2
from datetime import datetime
from typing import Any, Dict
from dataclasses import asdict

from .primitives import MemberCredential
from .cohort import CohortIdentity
from .envelope import KeyBundle, KeyBundleEntry
from .signing import CohortRecord
from peermodel.membership import MembershipProposal, MembershipVote


def _datetime_to_cbor(dt: datetime) -> str:
    """Convert datetime to ISO8601 string for CBOR serialization."""
    if dt is None:
        return None
    return dt.isoformat()


def _datetime_from_cbor(s: str) -> datetime:
    """Parse datetime from ISO8601 string."""
    if s is None:
        return None
    return datetime.fromisoformat(s)


def _dataclass_to_dict(obj: Any) -> Dict:
    """Convert dataclass to dict, handling datetime fields recursively."""
    data = asdict(obj)
    return _convert_datetimes(data)


def _convert_datetimes(obj: Any) -> Any:
    """Recursively convert all datetime objects to ISO strings."""
    if isinstance(obj, datetime):
        return _datetime_to_cbor(obj)
    elif isinstance(obj, dict):
        return {key: _convert_datetimes(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_datetimes(item) for item in obj]
    else:
        return obj


# MemberCredential Serialization


def serialize_member_credential(cred: MemberCredential) -> bytes:
    """Serialize MemberCredential to canonical CBOR."""
    data = _dataclass_to_dict(cred)
    return cbor2.dumps(data, canonical=True)


def deserialize_member_credential(data: bytes) -> MemberCredential:
    """Deserialize MemberCredential from CBOR."""
    obj = cbor2.loads(data)
    return MemberCredential(**obj)


# CohortIdentity Serialization


def serialize_cohort_identity(identity: CohortIdentity) -> bytes:
    """Serialize CohortIdentity to canonical CBOR."""
    data = _dataclass_to_dict(identity)
    return cbor2.dumps(data, canonical=True)


def deserialize_cohort_identity(data: bytes) -> CohortIdentity:
    """Deserialize CohortIdentity from CBOR."""
    obj = cbor2.loads(data)
    # Convert datetime strings back to datetime objects
    if 'created_at' in obj and isinstance(obj['created_at'], str):
        obj['created_at'] = _datetime_from_cbor(obj['created_at'])
    return CohortIdentity(**obj)


# KeyBundle Serialization


def serialize_keybundle(bundle: KeyBundle) -> bytes:
    """Serialize KeyBundle to canonical CBOR."""
    data = _dataclass_to_dict(bundle)
    return cbor2.dumps(data, canonical=True)


def deserialize_keybundle(data: bytes) -> KeyBundle:
    """Deserialize KeyBundle from CBOR."""
    obj = cbor2.loads(data)
    # Convert entry dicts to KeyBundleEntry objects
    entries = [KeyBundleEntry(**entry) for entry in obj['entries']]
    obj['entries'] = entries
    return KeyBundle(**obj)


# CohortRecord Serialization


def serialize_record(record: CohortRecord) -> bytes:
    """Serialize CohortRecord to canonical CBOR."""
    data = _dataclass_to_dict(record)
    return cbor2.dumps(data, canonical=True)


def deserialize_record(data: bytes) -> CohortRecord:
    """Deserialize CohortRecord from CBOR."""
    obj = cbor2.loads(data)
    # Convert datetime strings back to datetime objects
    if 'signed_at' in obj and isinstance(obj['signed_at'], str):
        obj['signed_at'] = _datetime_from_cbor(obj['signed_at'])
    return CohortRecord(**obj)


# MembershipProposal Serialization


def serialize_proposal(proposal: MembershipProposal) -> bytes:
    """Serialize MembershipProposal to canonical CBOR."""
    data = _dataclass_to_dict(proposal)
    return cbor2.dumps(data, canonical=True)


def deserialize_proposal(data: bytes) -> MembershipProposal:
    """Deserialize MembershipProposal from CBOR."""
    obj = cbor2.loads(data)
    # Convert datetime strings back to datetime objects
    if 'proposed_at' in obj and isinstance(obj['proposed_at'], str):
        obj['proposed_at'] = _datetime_from_cbor(obj['proposed_at'])

    # Reconstruct votes
    votes = []
    for vote_data in obj.get('votes', []):
        if isinstance(vote_data, dict):
            if 'voted_at' in vote_data and isinstance(vote_data['voted_at'], str):
                vote_data['voted_at'] = _datetime_from_cbor(vote_data['voted_at'])
            votes.append(MembershipVote(**vote_data))
        else:
            votes.append(vote_data)
    obj['votes'] = votes

    return MembershipProposal(**obj)
