"""Tests for Issue #14: CohortRecord signing.

Acceptance criteria:
- [ ] Sign public records (CID only)
- [ ] Sign encrypted records (CID + key_bundle_cid)
- [ ] Verify signature works
- [ ] Detect tampering
- [ ] Tests: sign/verify, verify tampering detected
"""

import pytest
from datetime import datetime, timezone

from peermodel.primitives import generate_keypair


@pytest.fixture
def founder_identity():
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
    return {
        'identity_id': 'founder',
        'x25519_public': x25519_pub,
        'x25519_private': x25519_priv,
        'ed25519_public': ed25519_pub,
        'ed25519_private': ed25519_priv,
    }


@pytest.fixture
def test_cohort(founder_identity):
    from peermodel.delegation import SimpleCohort
    return SimpleCohort(cohort_id='test_cohort', founder_identity=founder_identity)


PUBLIC_CID = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
CONTENT_CID = "bafybeihpklcq7xzqlvjbxzuyzqxjwavkivl3f4tqyqzqzqzqzqzqzqzqzq"
KEY_BUNDLE_CID = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdj"


@pytest.mark.issue_14
class TestSignCid:
    """Tests for sign_cid() — public record signing."""

    def test_sign_cid_returns_cohort_record(self, test_cohort):
        from peermodel.signing import sign_cid
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        assert record is not None

    def test_sign_cid_record_has_signature(self, test_cohort):
        from peermodel.signing import sign_cid
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        assert isinstance(record.signature, bytes)
        assert len(record.signature) > 0

    def test_sign_cid_record_is_not_encrypted(self, test_cohort):
        from peermodel.signing import sign_cid
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        assert record.is_encrypted is False

    def test_sign_cid_record_has_no_key_bundle_cid(self, test_cohort):
        from peermodel.signing import sign_cid
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        assert record.key_bundle_cid is None

    def test_sign_cid_content_cid_matches(self, test_cohort):
        from peermodel.signing import sign_cid
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        assert record.content_cid == PUBLIC_CID

    def test_sign_cid_cohort_id_matches(self, test_cohort):
        from peermodel.signing import sign_cid
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        assert record.cohort_id == test_cohort.cohort_id

    def test_sign_cid_signed_at_is_datetime(self, test_cohort):
        from peermodel.signing import sign_cid
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        assert isinstance(record.signed_at, datetime)

    def test_sign_cid_signing_algorithm_is_ed25519(self, test_cohort):
        from peermodel.signing import sign_cid
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        assert record.signing_algorithm == "ed25519"

    def test_sign_cid_with_metadata(self, test_cohort):
        from peermodel.signing import sign_cid
        metadata = {"dataset": "test", "version": "1.0"}
        record = sign_cid(cid=PUBLIC_CID, metadata=metadata, cohort=test_cohort)
        assert record.metadata == metadata

    def test_sign_cid_record_has_record_id(self, test_cohort):
        from peermodel.signing import sign_cid
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        assert record.record_id is not None
        assert isinstance(record.record_id, str)

    def test_sign_cid_schema_version_default(self, test_cohort):
        from peermodel.signing import sign_cid
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        assert record.schema_version is not None


@pytest.mark.issue_14
class TestSignEncryptedRecord:
    """Tests for sign_encrypted_record() — encrypted record signing."""

    def test_sign_encrypted_record_returns_cohort_record(self, test_cohort):
        from peermodel.signing import sign_encrypted_record
        record = sign_encrypted_record(
            content_cid=CONTENT_CID,
            key_bundle_cid=KEY_BUNDLE_CID,
            cohort=test_cohort,
        )
        assert record is not None

    def test_sign_encrypted_record_is_encrypted(self, test_cohort):
        from peermodel.signing import sign_encrypted_record
        record = sign_encrypted_record(
            content_cid=CONTENT_CID,
            key_bundle_cid=KEY_BUNDLE_CID,
            cohort=test_cohort,
        )
        assert record.is_encrypted is True

    def test_sign_encrypted_record_has_key_bundle_cid(self, test_cohort):
        from peermodel.signing import sign_encrypted_record
        record = sign_encrypted_record(
            content_cid=CONTENT_CID,
            key_bundle_cid=KEY_BUNDLE_CID,
            cohort=test_cohort,
        )
        assert record.key_bundle_cid == KEY_BUNDLE_CID

    def test_sign_encrypted_record_content_cid_matches(self, test_cohort):
        from peermodel.signing import sign_encrypted_record
        record = sign_encrypted_record(
            content_cid=CONTENT_CID,
            key_bundle_cid=KEY_BUNDLE_CID,
            cohort=test_cohort,
        )
        assert record.content_cid == CONTENT_CID

    def test_sign_encrypted_record_has_signature(self, test_cohort):
        from peermodel.signing import sign_encrypted_record
        record = sign_encrypted_record(
            content_cid=CONTENT_CID,
            key_bundle_cid=KEY_BUNDLE_CID,
            cohort=test_cohort,
        )
        assert isinstance(record.signature, bytes)
        assert len(record.signature) > 0

    def test_sign_encrypted_record_cohort_id_matches(self, test_cohort):
        from peermodel.signing import sign_encrypted_record
        record = sign_encrypted_record(
            content_cid=CONTENT_CID,
            key_bundle_cid=KEY_BUNDLE_CID,
            cohort=test_cohort,
        )
        assert record.cohort_id == test_cohort.cohort_id

    def test_sign_encrypted_record_signing_algorithm_is_ed25519(self, test_cohort):
        from peermodel.signing import sign_encrypted_record
        record = sign_encrypted_record(
            content_cid=CONTENT_CID,
            key_bundle_cid=KEY_BUNDLE_CID,
            cohort=test_cohort,
        )
        assert record.signing_algorithm == "ed25519"

    def test_sign_encrypted_record_with_metadata(self, test_cohort):
        from peermodel.signing import sign_encrypted_record
        metadata = {"dataset": "test", "encrypted": True}
        record = sign_encrypted_record(
            content_cid=CONTENT_CID,
            key_bundle_cid=KEY_BUNDLE_CID,
            cohort=test_cohort,
            metadata=metadata,
        )
        assert record.metadata == metadata


@pytest.mark.issue_14
class TestSignatureVerification:
    """Tests for signature verification."""

    def test_verify_public_record_signature(self, test_cohort):
        from peermodel.signing import sign_cid, verify_cohort_record
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        public_keys = test_cohort.get_cohort_public_keys()
        assert verify_cohort_record(record, public_keys['ed25519_public']) is True

    def test_verify_encrypted_record_signature(self, test_cohort):
        from peermodel.signing import sign_encrypted_record, verify_cohort_record
        record = sign_encrypted_record(
            content_cid=CONTENT_CID,
            key_bundle_cid=KEY_BUNDLE_CID,
            cohort=test_cohort,
        )
        public_keys = test_cohort.get_cohort_public_keys()
        assert verify_cohort_record(record, public_keys['ed25519_public']) is True

    def test_verify_rejects_wrong_public_key(self, test_cohort, founder_identity):
        from peermodel.signing import sign_cid, verify_cohort_record
        from peermodel.delegation import SimpleCohort
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        other_cohort = SimpleCohort(
            cohort_id='other_cohort',
            founder_identity=founder_identity,
        )
        other_keys = other_cohort.get_cohort_public_keys()
        assert verify_cohort_record(record, other_keys['ed25519_public']) is False


@pytest.mark.issue_14
class TestTamperingDetection:
    """Tests for detecting record tampering."""

    def test_tampered_content_cid_fails_verification(self, test_cohort):
        from peermodel.signing import sign_cid, verify_cohort_record
        from dataclasses import replace
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        tampered = replace(record, content_cid="bafybeiATAMPEREDCID")
        public_keys = test_cohort.get_cohort_public_keys()
        assert verify_cohort_record(tampered, public_keys['ed25519_public']) is False

    def test_tampered_key_bundle_cid_fails_verification(self, test_cohort):
        from peermodel.signing import sign_encrypted_record, verify_cohort_record
        from dataclasses import replace
        record = sign_encrypted_record(
            content_cid=CONTENT_CID,
            key_bundle_cid=KEY_BUNDLE_CID,
            cohort=test_cohort,
        )
        tampered = replace(record, key_bundle_cid="bafybeiATAMPEREDKEYBUNDLE")
        public_keys = test_cohort.get_cohort_public_keys()
        assert verify_cohort_record(tampered, public_keys['ed25519_public']) is False

    def test_tampered_cohort_id_fails_verification(self, test_cohort):
        from peermodel.signing import sign_cid, verify_cohort_record
        from dataclasses import replace
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        tampered = replace(record, cohort_id="evil_cohort")
        public_keys = test_cohort.get_cohort_public_keys()
        assert verify_cohort_record(tampered, public_keys['ed25519_public']) is False

    def test_tampered_signature_fails_verification(self, test_cohort):
        from peermodel.signing import sign_cid, verify_cohort_record
        from dataclasses import replace
        record = sign_cid(cid=PUBLIC_CID, metadata=None, cohort=test_cohort)
        tampered = replace(record, signature=b"\x00" * 64)
        public_keys = test_cohort.get_cohort_public_keys()
        assert verify_cohort_record(tampered, public_keys['ed25519_public']) is False
