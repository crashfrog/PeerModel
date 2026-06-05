#!/usr/bin/env python

"""
Tests for Issue #14: CohortRecord signing

This test module covers the acceptance criteria for CohortRecord signing:
- Sign public records (CID only)
- Sign encrypted records (CID + key_bundle_cid)
- Verify signature works
- Detect tampering
- Tests: sign/verify, verify tampering detected

Tests are marked with @pytest.mark.issue_14 for filtering.
These tests will FAIL until signing.sign_cid() and signing.sign_encrypted_record() are implemented.
"""

import pytest
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from peermodel.primitives import (
    generate_keypair,
    serialize_to_cbor,
    deserialize_from_cbor,
)


@dataclass
class CohortRecord:
    """A signed, optionally encrypted data record published to IPFS."""
    cohort_id: str
    record_id: str                    # UUID
    content_cid: str
    key_bundle_cid: Optional[str]
    is_encrypted: bool
    metadata: Optional[dict]
    signature: bytes
    signing_algorithm: str
    signed_at: datetime
    schema_version: str               # semver; breaking changes require bump


@pytest.fixture
def founder_identity():
    """Generate founder's identity with keypair."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
    return {
        'member_id': 'founder',
        'x25519_public': x25519_pub,
        'x25519_private': x25519_priv,
        'ed25519_public': ed25519_pub,
        'ed25519_private': ed25519_priv,
    }


@pytest.fixture
def cohort_signing_keypair():
    """Generate a fresh cohort signing keypair."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
    return {
        'x25519_private': x25519_priv,
        'x25519_public': x25519_pub,
        'ed25519_private': ed25519_priv,
        'ed25519_public': ed25519_pub,
    }


class TestSignPublicRecord:
    """Test signing public records (CID only)."""

    @pytest.mark.issue_14
    def test_sign_cid_returns_signature_bytes(self, cohort_signing_keypair):
        """sign_cid() returns signature as bytes."""
        from peermodel.signing import sign_cid

        content_cid = "QmVeryLongCIDStringRepresentingContent123456789"
        signature = sign_cid(
            content_cid=content_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        assert isinstance(signature, bytes), "Signature must be bytes"
        assert len(signature) > 0, "Signature must not be empty"

    @pytest.mark.issue_14
    def test_sign_cid_with_different_cids_produces_different_signatures(self, cohort_signing_keypair):
        """Different CIDs produce different signatures."""
        from peermodel.signing import sign_cid

        cid1 = "QmCID1234567890ABCDEF"
        cid2 = "QmDIFFERENT1234567890"

        sig1 = sign_cid(
            content_cid=cid1,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )
        sig2 = sign_cid(
            content_cid=cid2,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        assert sig1 != sig2, "Different CIDs must produce different signatures"

    @pytest.mark.issue_14
    def test_sign_cid_same_cid_produces_same_signature(self, cohort_signing_keypair):
        """Signing the same CID twice produces identical signatures."""
        from peermodel.signing import sign_cid

        content_cid = "QmSameContentCIDString123456789"

        sig1 = sign_cid(
            content_cid=content_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )
        sig2 = sign_cid(
            content_cid=content_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        assert sig1 == sig2, "Same CID must produce identical signatures (deterministic)"

    @pytest.mark.issue_14
    def test_sign_cid_with_ed25519_key(self, cohort_signing_keypair):
        """sign_cid() works with Ed25519 private key."""
        from peermodel.signing import sign_cid

        content_cid = "QmValidCIDString"
        ed25519_private = cohort_signing_keypair['ed25519_private']

        # Should not raise
        signature = sign_cid(
            content_cid=content_cid,
            cohort_signing_private_key=ed25519_private,
        )

        assert isinstance(signature, bytes)


class TestSignEncryptedRecord:
    """Test signing encrypted records (CID + key_bundle_cid)."""

    @pytest.mark.issue_14
    def test_sign_encrypted_record_returns_signature_bytes(self, cohort_signing_keypair):
        """sign_encrypted_record() returns signature as bytes."""
        from peermodel.signing import sign_encrypted_record

        content_cid = "QmContentCIDString123"
        key_bundle_cid = "QmKeyBundleCIDString456"

        signature = sign_encrypted_record(
            content_cid=content_cid,
            key_bundle_cid=key_bundle_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        assert isinstance(signature, bytes), "Signature must be bytes"
        assert len(signature) > 0, "Signature must not be empty"

    @pytest.mark.issue_14
    def test_sign_encrypted_record_with_different_content_cids_produces_different_signatures(self, cohort_signing_keypair):
        """Different content CIDs produce different signatures."""
        from peermodel.signing import sign_encrypted_record

        key_bundle_cid = "QmSameKeyBundle123"
        content_cid_1 = "QmContent1"
        content_cid_2 = "QmContent2"

        sig1 = sign_encrypted_record(
            content_cid=content_cid_1,
            key_bundle_cid=key_bundle_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )
        sig2 = sign_encrypted_record(
            content_cid=content_cid_2,
            key_bundle_cid=key_bundle_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        assert sig1 != sig2, "Different content CIDs must produce different signatures"

    @pytest.mark.issue_14
    def test_sign_encrypted_record_with_different_key_bundles_produces_different_signatures(self, cohort_signing_keypair):
        """Different key bundle CIDs produce different signatures."""
        from peermodel.signing import sign_encrypted_record

        content_cid = "QmSameContent123"
        key_bundle_cid_1 = "QmKeyBundle1"
        key_bundle_cid_2 = "QmKeyBundle2"

        sig1 = sign_encrypted_record(
            content_cid=content_cid,
            key_bundle_cid=key_bundle_cid_1,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )
        sig2 = sign_encrypted_record(
            content_cid=content_cid,
            key_bundle_cid=key_bundle_cid_2,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        assert sig1 != sig2, "Different key bundle CIDs must produce different signatures"

    @pytest.mark.issue_14
    def test_sign_encrypted_record_same_cids_produces_same_signature(self, cohort_signing_keypair):
        """Signing the same content+key_bundle CIDs twice produces identical signatures."""
        from peermodel.signing import sign_encrypted_record

        content_cid = "QmContentCID123"
        key_bundle_cid = "QmKeyBundleCID456"

        sig1 = sign_encrypted_record(
            content_cid=content_cid,
            key_bundle_cid=key_bundle_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )
        sig2 = sign_encrypted_record(
            content_cid=content_cid,
            key_bundle_cid=key_bundle_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        assert sig1 == sig2, "Same CID pairs must produce identical signatures (deterministic)"


class TestVerifyPublicRecordSignature:
    """Test verification of public record signatures."""

    @pytest.mark.issue_14
    def test_verify_cid_signature_succeeds_for_valid_signature(self, cohort_signing_keypair):
        """verify_cid_signature() returns True for valid signature."""
        from peermodel.signing import sign_cid, verify_cid_signature

        content_cid = "QmValidCIDString123"
        signature = sign_cid(
            content_cid=content_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        is_valid = verify_cid_signature(
            content_cid=content_cid,
            signature=signature,
            cohort_signing_public_key=cohort_signing_keypair['ed25519_public'],
        )

        assert is_valid is True, "Valid signature must verify successfully"

    @pytest.mark.issue_14
    def test_verify_cid_signature_fails_for_tampered_cid(self, cohort_signing_keypair):
        """verify_cid_signature() returns False when CID is tampered."""
        from peermodel.signing import sign_cid, verify_cid_signature

        original_cid = "QmOriginalCID123"
        tampered_cid = "QmTamperedCID456"

        signature = sign_cid(
            content_cid=original_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        is_valid = verify_cid_signature(
            content_cid=tampered_cid,
            signature=signature,
            cohort_signing_public_key=cohort_signing_keypair['ed25519_public'],
        )

        assert is_valid is False, "Tampered CID must fail verification"

    @pytest.mark.issue_14
    def test_verify_cid_signature_fails_for_tampered_signature(self, cohort_signing_keypair):
        """verify_cid_signature() returns False when signature is tampered."""
        from peermodel.signing import sign_cid, verify_cid_signature

        content_cid = "QmCIDString123"
        signature = sign_cid(
            content_cid=content_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        # Tamper with signature by flipping a bit
        tampered_signature = bytes([signature[0] ^ 0xFF]) + signature[1:]

        is_valid = verify_cid_signature(
            content_cid=content_cid,
            signature=tampered_signature,
            cohort_signing_public_key=cohort_signing_keypair['ed25519_public'],
        )

        assert is_valid is False, "Tampered signature must fail verification"

    @pytest.mark.issue_14
    def test_verify_cid_signature_fails_for_signature_with_wrong_key(self, cohort_signing_keypair):
        """verify_cid_signature() returns False when verified with wrong public key."""
        from peermodel.signing import sign_cid, verify_cid_signature

        # Generate a second keypair
        _, _, _, wrong_public_key = generate_keypair()

        content_cid = "QmCIDString123"
        signature = sign_cid(
            content_cid=content_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        is_valid = verify_cid_signature(
            content_cid=content_cid,
            signature=signature,
            cohort_signing_public_key=wrong_public_key,
        )

        assert is_valid is False, "Signature with wrong public key must fail verification"


class TestVerifyEncryptedRecordSignature:
    """Test verification of encrypted record signatures."""

    @pytest.mark.issue_14
    def test_verify_encrypted_record_signature_succeeds_for_valid_signature(self, cohort_signing_keypair):
        """verify_encrypted_record_signature() returns True for valid signature."""
        from peermodel.signing import sign_encrypted_record, verify_encrypted_record_signature

        content_cid = "QmContentCID123"
        key_bundle_cid = "QmKeyBundleCID456"

        signature = sign_encrypted_record(
            content_cid=content_cid,
            key_bundle_cid=key_bundle_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        is_valid = verify_encrypted_record_signature(
            content_cid=content_cid,
            key_bundle_cid=key_bundle_cid,
            signature=signature,
            cohort_signing_public_key=cohort_signing_keypair['ed25519_public'],
        )

        assert is_valid is True, "Valid signature must verify successfully"

    @pytest.mark.issue_14
    def test_verify_encrypted_record_signature_fails_for_tampered_content_cid(self, cohort_signing_keypair):
        """verify_encrypted_record_signature() returns False when content CID is tampered."""
        from peermodel.signing import sign_encrypted_record, verify_encrypted_record_signature

        original_content_cid = "QmOriginalContent123"
        tampered_content_cid = "QmTamperedContent456"
        key_bundle_cid = "QmKeyBundle789"

        signature = sign_encrypted_record(
            content_cid=original_content_cid,
            key_bundle_cid=key_bundle_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        is_valid = verify_encrypted_record_signature(
            content_cid=tampered_content_cid,
            key_bundle_cid=key_bundle_cid,
            signature=signature,
            cohort_signing_public_key=cohort_signing_keypair['ed25519_public'],
        )

        assert is_valid is False, "Tampered content CID must fail verification"

    @pytest.mark.issue_14
    def test_verify_encrypted_record_signature_fails_for_tampered_key_bundle_cid(self, cohort_signing_keypair):
        """verify_encrypted_record_signature() returns False when key bundle CID is tampered."""
        from peermodel.signing import sign_encrypted_record, verify_encrypted_record_signature

        content_cid = "QmContent123"
        original_key_bundle_cid = "QmOriginalKeyBundle456"
        tampered_key_bundle_cid = "QmTamperedKeyBundle789"

        signature = sign_encrypted_record(
            content_cid=content_cid,
            key_bundle_cid=original_key_bundle_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        is_valid = verify_encrypted_record_signature(
            content_cid=content_cid,
            key_bundle_cid=tampered_key_bundle_cid,
            signature=signature,
            cohort_signing_public_key=cohort_signing_keypair['ed25519_public'],
        )

        assert is_valid is False, "Tampered key bundle CID must fail verification"

    @pytest.mark.issue_14
    def test_verify_encrypted_record_signature_fails_for_tampered_signature(self, cohort_signing_keypair):
        """verify_encrypted_record_signature() returns False when signature is tampered."""
        from peermodel.signing import sign_encrypted_record, verify_encrypted_record_signature

        content_cid = "QmContent123"
        key_bundle_cid = "QmKeyBundle456"

        signature = sign_encrypted_record(
            content_cid=content_cid,
            key_bundle_cid=key_bundle_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        # Tamper with signature by flipping a bit
        tampered_signature = bytes([signature[0] ^ 0xFF]) + signature[1:]

        is_valid = verify_encrypted_record_signature(
            content_cid=content_cid,
            key_bundle_cid=key_bundle_cid,
            signature=tampered_signature,
            cohort_signing_public_key=cohort_signing_keypair['ed25519_public'],
        )

        assert is_valid is False, "Tampered signature must fail verification"

    @pytest.mark.issue_14
    def test_verify_encrypted_record_signature_fails_with_wrong_key(self, cohort_signing_keypair):
        """verify_encrypted_record_signature() returns False with wrong public key."""
        from peermodel.signing import sign_encrypted_record, verify_encrypted_record_signature

        # Generate a second keypair
        _, _, _, wrong_public_key = generate_keypair()

        content_cid = "QmContent123"
        key_bundle_cid = "QmKeyBundle456"

        signature = sign_encrypted_record(
            content_cid=content_cid,
            key_bundle_cid=key_bundle_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        is_valid = verify_encrypted_record_signature(
            content_cid=content_cid,
            key_bundle_cid=key_bundle_cid,
            signature=signature,
            cohort_signing_public_key=wrong_public_key,
        )

        assert is_valid is False, "Signature with wrong public key must fail verification"


class TestTamperingDetection:
    """Test that tampering is reliably detected."""

    @pytest.mark.issue_14
    def test_detect_tampering_public_record_cid_modification(self, cohort_signing_keypair):
        """Detect when public record CID is modified after signing."""
        from peermodel.signing import sign_cid, verify_cid_signature

        original_cid = "QmOriginalContent"
        signature = sign_cid(
            content_cid=original_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        # Try to verify with modified CID (single character change)
        modified_cid = "QmModifiedContent"

        is_valid = verify_cid_signature(
            content_cid=modified_cid,
            signature=signature,
            cohort_signing_public_key=cohort_signing_keypair['ed25519_public'],
        )

        assert is_valid is False, "Tampering must be detected"

    @pytest.mark.issue_14
    def test_detect_tampering_encrypted_record_content_swap(self, cohort_signing_keypair):
        """Detect when content and key bundle CIDs are swapped in encrypted record."""
        from peermodel.signing import sign_encrypted_record, verify_encrypted_record_signature

        content_cid = "QmContentCID123"
        key_bundle_cid = "QmKeyBundleCID456"

        signature = sign_encrypted_record(
            content_cid=content_cid,
            key_bundle_cid=key_bundle_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        # Try to verify with swapped CIDs
        is_valid = verify_encrypted_record_signature(
            content_cid=key_bundle_cid,  # swapped
            key_bundle_cid=content_cid,  # swapped
            signature=signature,
            cohort_signing_public_key=cohort_signing_keypair['ed25519_public'],
        )

        assert is_valid is False, "Swapped CIDs must be detected as tampering"

    @pytest.mark.issue_14
    def test_detect_tampering_single_bit_flip_in_signature(self, cohort_signing_keypair):
        """Detect tampering from single bit flip in signature."""
        from peermodel.signing import sign_cid, verify_cid_signature

        content_cid = "QmCIDString123"
        signature = sign_cid(
            content_cid=content_cid,
            cohort_signing_private_key=cohort_signing_keypair['ed25519_private'],
        )

        # Flip the last bit of the last byte
        tampered_sig = signature[:-1] + bytes([signature[-1] ^ 0x01])

        is_valid = verify_cid_signature(
            content_cid=content_cid,
            signature=tampered_sig,
            cohort_signing_public_key=cohort_signing_keypair['ed25519_public'],
        )

        assert is_valid is False, "Single bit flip must be detected"
