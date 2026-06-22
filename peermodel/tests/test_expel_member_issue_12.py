#!/usr/bin/env python

"""
Tests for Issue #12: Member expulsion & forward secrecy.

Covers the acceptance criteria for expel_member():
- Expel member from cohort
- New cohort key regenerated
- Expelled member cannot decrypt new content
- Remaining members can decrypt new content
- Past content remains encrypted under old key

Tests are marked with @pytest.mark.issue_12 for filtering.
These tests will FAIL until expel_member() is implemented.

API under test:
    from peermodel.delegation import expel_member

    def expel_member(
        keybundle: KeyBundle,
        expelled_member_id: str,
        remaining_member_identities: List[dict],  # each with 'member_id', 'x25519_public'
        initiator_identity: dict,                  # must have 'member_id' in keybundle
    ) -> Tuple[CohortIdentity, KeyBundle, bytes]:
        ...

    Returns (new_cohort_identity, new_keybundle, new_cohort_private_key_bytes).
    Raises ValueError if expelled_member_id or initiator not in keybundle.
"""

import pytest

from peermodel.primitives import (
    generate_keypair,
    deserialize_from_cbor,
    encrypt_to_recipient,
    decrypt_from_sender,
)
from peermodel.exceptions import DecryptionError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def founder_identity():
    """Founder's full keypair dict."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
    return {
        'member_id': 'founder',
        'x25519_public': x25519_pub,
        'x25519_private': x25519_priv,
        'ed25519_public': ed25519_pub,
        'ed25519_private': ed25519_priv,
    }


@pytest.fixture
def member_b_identity():
    """Member B's full keypair dict (will be expelled)."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
    return {
        'member_id': 'member_b',
        'x25519_public': x25519_pub,
        'x25519_private': x25519_priv,
        'ed25519_public': ed25519_pub,
        'ed25519_private': ed25519_priv,
    }


@pytest.fixture
def cohort_with_two_members(founder_identity, member_b_identity):
    """Cohort with founder + member_b, returns (cohort_identity, keybundle, old_key_bytes)."""
    from peermodel.delegation import create_cohort, add_member

    cohort_identity, keybundle, old_key_bytes = create_cohort(
        cohort_id='test_cohort_12',
        founder_identity=founder_identity,
    )

    keybundle = add_member(
        keybundle=keybundle,
        new_member_identity=member_b_identity,
        initiator_identity=founder_identity,
        cohort_private_key_bytes=old_key_bytes,
    )

    return (cohort_identity, keybundle, old_key_bytes)


# ---------------------------------------------------------------------------
# TestExpelMemberReturn
# ---------------------------------------------------------------------------

class TestExpelMemberReturn:
    """expel_member() returns the right types."""

    @pytest.mark.issue_12
    def test_expel_member_returns_three_tuple(
        self, cohort_with_two_members, founder_identity, member_b_identity
    ):
        """expel_member returns (CohortIdentity, KeyBundle, bytes)."""
        from peermodel.delegation import expel_member, CohortIdentity, KeyBundle

        _, keybundle, _ = cohort_with_two_members

        result = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        assert isinstance(result, tuple), f"expel_member must return a tuple, got {type(result)}"
        assert len(result) == 3, f"expel_member must return a 3-tuple, got length {len(result)}"

        new_identity, new_keybundle, new_key_bytes = result
        assert isinstance(new_identity, CohortIdentity), (
            f"First element must be CohortIdentity, got {type(new_identity)}"
        )
        assert isinstance(new_keybundle, KeyBundle), (
            f"Second element must be KeyBundle, got {type(new_keybundle)}"
        )
        assert isinstance(new_key_bytes, bytes), (
            f"Third element must be bytes, got {type(new_key_bytes)}"
        )

    @pytest.mark.issue_12
    def test_expel_member_preserves_cohort_id(
        self, cohort_with_two_members, founder_identity
    ):
        """New KeyBundle and CohortIdentity keep the original cohort_id."""
        from peermodel.delegation import expel_member

        _, keybundle, _ = cohort_with_two_members

        new_identity, new_keybundle, _ = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        assert new_keybundle.cohort_id == keybundle.cohort_id, (
            f"New KeyBundle must preserve cohort_id '{keybundle.cohort_id}', "
            f"got '{new_keybundle.cohort_id}'"
        )
        assert new_identity.cohort_id == keybundle.cohort_id, (
            f"New CohortIdentity must preserve cohort_id '{keybundle.cohort_id}', "
            f"got '{new_identity.cohort_id}'"
        )

    @pytest.mark.issue_12
    def test_expel_member_new_keybundle_version_incremented(
        self, cohort_with_two_members, founder_identity
    ):
        """New KeyBundle version is greater than the current version."""
        from peermodel.delegation import expel_member

        _, keybundle, _ = cohort_with_two_members
        original_version = keybundle.version

        _, new_keybundle, _ = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        assert new_keybundle.version > original_version, (
            f"New KeyBundle version must exceed {original_version}, "
            f"got {new_keybundle.version}"
        )


# ---------------------------------------------------------------------------
# TestExpelledMemberRemoved
# ---------------------------------------------------------------------------

class TestExpelledMemberRemoved:
    """Expelled member has no access in the new KeyBundle."""

    @pytest.mark.issue_12
    def test_expelled_member_not_in_new_keybundle(
        self, cohort_with_two_members, founder_identity
    ):
        """New KeyBundle contains no entry for the expelled member.

        Acceptance criterion: Expel member from cohort
        """
        from peermodel.delegation import expel_member

        _, keybundle, _ = cohort_with_two_members

        _, new_keybundle, _ = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        member_ids = [e.member_id for e in new_keybundle.entries]
        assert 'member_b' not in member_ids, (
            f"Expelled member 'member_b' must not appear in new KeyBundle entries, "
            f"got entries: {member_ids}"
        )

    @pytest.mark.issue_12
    def test_expelled_member_cannot_get_cohort_key(
        self, cohort_with_two_members, founder_identity, member_b_identity
    ):
        """get_cohort_private_key raises ValueError for expelled member.

        Acceptance criterion: Expelled member cannot decrypt new content
        """
        from peermodel.delegation import expel_member, get_cohort_private_key

        _, keybundle, _ = cohort_with_two_members

        _, new_keybundle, _ = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        with pytest.raises(ValueError) as exc_info:
            get_cohort_private_key(
                keybundle=new_keybundle,
                member_id='member_b',
                member_x25519_private=member_b_identity['x25519_private'],
                member_ed25519_private=member_b_identity['ed25519_private'],
            )

        assert 'member_b' in str(exc_info.value), (
            f"ValueError must identify the expelled member 'member_b', "
            f"got: {exc_info.value}"
        )

    @pytest.mark.issue_12
    def test_new_keybundle_entry_count_excludes_expelled(
        self, cohort_with_two_members, founder_identity
    ):
        """New KeyBundle has exactly one fewer entry than the original.

        Acceptance criterion: Expel member from cohort
        """
        from peermodel.delegation import expel_member

        _, keybundle, _ = cohort_with_two_members
        original_count = len(keybundle.entries)

        _, new_keybundle, _ = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        assert len(new_keybundle.entries) == original_count - 1, (
            f"New KeyBundle must have {original_count - 1} entries, "
            f"got {len(new_keybundle.entries)}"
        )


# ---------------------------------------------------------------------------
# TestRemainingMembersRetainAccess
# ---------------------------------------------------------------------------

class TestRemainingMembersRetainAccess:
    """Remaining members can still access new key material.

    Acceptance criterion: Remaining members can decrypt new content
    """

    @pytest.mark.issue_12
    def test_remaining_member_entry_in_new_keybundle(
        self, cohort_with_two_members, founder_identity
    ):
        """Founder's entry is present in the new KeyBundle."""
        from peermodel.delegation import expel_member

        _, keybundle, _ = cohort_with_two_members

        _, new_keybundle, _ = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        member_ids = [e.member_id for e in new_keybundle.entries]
        assert 'founder' in member_ids, (
            f"Remaining member 'founder' must be in new KeyBundle entries, "
            f"got: {member_ids}"
        )

    @pytest.mark.issue_12
    def test_remaining_member_can_decrypt_new_cohort_key(
        self, cohort_with_two_members, founder_identity
    ):
        """Founder can call get_cohort_private_key() on the new KeyBundle."""
        from peermodel.delegation import expel_member, get_cohort_private_key

        _, keybundle, _ = cohort_with_two_members

        _, new_keybundle, new_key_bytes = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        decrypted = get_cohort_private_key(
            keybundle=new_keybundle,
            member_id='founder',
            member_x25519_private=founder_identity['x25519_private'],
            member_ed25519_private=founder_identity['ed25519_private'],
        )

        assert decrypted == new_key_bytes, (
            "Remaining member's decrypted key must equal new_cohort_private_key_bytes"
        )

    @pytest.mark.issue_12
    def test_remaining_member_decrypted_key_has_private_key_fields(
        self, cohort_with_two_members, founder_identity
    ):
        """Remaining member's decrypted new key is valid CBOR with private key fields."""
        from peermodel.delegation import expel_member, get_cohort_private_key

        _, keybundle, _ = cohort_with_two_members

        _, new_keybundle, _ = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        decrypted = get_cohort_private_key(
            keybundle=new_keybundle,
            member_id='founder',
            member_x25519_private=founder_identity['x25519_private'],
            member_ed25519_private=founder_identity['ed25519_private'],
        )

        key_dict = deserialize_from_cbor(decrypted, dict)

        has_signing_key = 'signing_private_key' in key_dict or 'ed25519_private' in key_dict
        has_encryption_key = 'encryption_private_key' in key_dict or 'x25519_private' in key_dict

        assert has_signing_key, (
            f"New cohort key material must contain signing private key, "
            f"got keys: {list(key_dict.keys())}"
        )
        assert has_encryption_key, (
            f"New cohort key material must contain encryption private key, "
            f"got keys: {list(key_dict.keys())}"
        )


# ---------------------------------------------------------------------------
# TestNewCohortKeyGenerated
# ---------------------------------------------------------------------------

class TestNewCohortKeyGenerated:
    """New cohort keypair is freshly generated after expulsion.

    Acceptance criterion: New cohort key regenerated
    """

    @pytest.mark.issue_12
    def test_new_cohort_key_bytes_differ_from_old(
        self, cohort_with_two_members, founder_identity
    ):
        """expel_member returns different cohort private key bytes than the original.

        Acceptance criterion: New cohort key regenerated
        """
        from peermodel.delegation import expel_member

        _, keybundle, old_key_bytes = cohort_with_two_members

        _, _, new_key_bytes = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        assert new_key_bytes != old_key_bytes, (
            "expel_member must generate a new cohort key; "
            "new_cohort_private_key_bytes must differ from old"
        )

    @pytest.mark.issue_12
    def test_new_cohort_identity_encryption_public_key_changed(
        self, cohort_with_two_members, founder_identity
    ):
        """New CohortIdentity has a different encryption public key than the original.

        Acceptance criterion: New cohort key regenerated
        """
        from peermodel.delegation import expel_member

        old_identity, keybundle, _ = cohort_with_two_members

        new_identity, _, _ = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        assert new_identity.encryption_public_key != old_identity.encryption_public_key, (
            "New CohortIdentity must have a freshly generated encryption_public_key"
        )

    @pytest.mark.issue_12
    def test_new_cohort_identity_signing_public_key_changed(
        self, cohort_with_two_members, founder_identity
    ):
        """New CohortIdentity has a different signing public key than the original.

        Acceptance criterion: New cohort key regenerated
        """
        from peermodel.delegation import expel_member

        old_identity, keybundle, _ = cohort_with_two_members

        new_identity, _, _ = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        assert new_identity.signing_public_key != old_identity.signing_public_key, (
            "New CohortIdentity must have a freshly generated signing_public_key"
        )


# ---------------------------------------------------------------------------
# TestForwardSecrecy
# ---------------------------------------------------------------------------

class TestForwardSecrecy:
    """Forward secrecy: expelled member's old key cannot decrypt new content.

    Acceptance criteria:
    - Expelled member cannot decrypt new content
    - Past content remains encrypted under old key
    """

    @pytest.mark.issue_12
    def test_expelled_member_old_key_cannot_decrypt_new_content(
        self, cohort_with_two_members, founder_identity, member_b_identity
    ):
        """Expelled member's copy of old cohort x25519 private key cannot decrypt
        content that was encrypted to the new cohort's public key.

        Acceptance criterion: Expelled member cannot decrypt new content
        """
        from peermodel.delegation import expel_member, get_cohort_private_key

        _, keybundle, old_key_bytes = cohort_with_two_members

        # member_b decrypts the old cohort key before expulsion
        member_b_old_cohort_key_bytes = get_cohort_private_key(
            keybundle=keybundle,
            member_id='member_b',
            member_x25519_private=member_b_identity['x25519_private'],
            member_ed25519_private=member_b_identity['ed25519_private'],
        )
        member_b_old_key_dict = deserialize_from_cbor(member_b_old_cohort_key_bytes, dict)
        member_b_old_x25519_private = member_b_old_key_dict['x25519_private']

        # Expel member_b
        new_identity, _, _ = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        # Simulate new content encrypted to new cohort public key
        new_content = b"secret new record after expulsion"
        ciphertext, nonce, tag, ephemeral_pub = encrypt_to_recipient(
            new_content,
            new_identity.encryption_public_key,
        )

        # Expelled member's old private key cannot decrypt new-key-encrypted content
        with pytest.raises(DecryptionError):
            decrypt_from_sender(
                ciphertext=ciphertext,
                nonce=nonce,
                tag=tag,
                ephemeral_public_key_der=ephemeral_pub,
                recipient_private_key_der=member_b_old_x25519_private,
            )

    @pytest.mark.issue_12
    def test_past_content_inaccessible_via_new_key_but_accessible_via_old(
        self, cohort_with_two_members, founder_identity, member_b_identity
    ):
        """Content encrypted under the OLD cohort public key is NOT decryptable
        with the new cohort private key, confirming forward secrecy: old and new
        key material are cryptographically independent.

        Acceptance criterion: Past content remains encrypted under old key (old key still works;
        new key does NOT decrypt old content — they are different keys)
        """
        from peermodel.delegation import expel_member, get_cohort_private_key

        old_identity, keybundle, _ = cohort_with_two_members

        # Simulate past content encrypted to old cohort public key
        past_content = b"old record created before expulsion"
        ciphertext, nonce, tag, ephemeral_pub = encrypt_to_recipient(
            past_content,
            old_identity.encryption_public_key,
        )

        # Expel member_b — generates fresh cohort keypair
        _, new_keybundle, new_key_bytes = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        # Founder retrieves the NEW cohort private key
        founder_new_key_bytes = get_cohort_private_key(
            keybundle=new_keybundle,
            member_id='founder',
            member_x25519_private=founder_identity['x25519_private'],
            member_ed25519_private=founder_identity['ed25519_private'],
        )
        new_key_dict = deserialize_from_cbor(founder_new_key_bytes, dict)
        new_x25519_private = new_key_dict['x25519_private']

        # New cohort private key CANNOT decrypt old content (different key — forward secrecy)
        with pytest.raises(DecryptionError):
            decrypt_from_sender(
                ciphertext=ciphertext,
                nonce=nonce,
                tag=tag,
                ephemeral_public_key_der=ephemeral_pub,
                recipient_private_key_der=new_x25519_private,
            )

    @pytest.mark.issue_12
    def test_remaining_member_can_decrypt_new_content(
        self, cohort_with_two_members, founder_identity
    ):
        """Remaining members can decrypt content encrypted to new cohort public key.

        Acceptance criterion: Remaining members can decrypt new content
        """
        from peermodel.delegation import expel_member, get_cohort_private_key

        _, keybundle, _ = cohort_with_two_members

        new_identity, new_keybundle, _ = expel_member(
            keybundle=keybundle,
            expelled_member_id='member_b',
            remaining_member_identities=[founder_identity],
            initiator_identity=founder_identity,
        )

        # New content encrypted to new cohort public key
        new_content = b"secret new record after expulsion"
        ciphertext, nonce, tag, ephemeral_pub = encrypt_to_recipient(
            new_content,
            new_identity.encryption_public_key,
        )

        # Founder gets new cohort private key from new keybundle
        new_key_bytes = get_cohort_private_key(
            keybundle=new_keybundle,
            member_id='founder',
            member_x25519_private=founder_identity['x25519_private'],
            member_ed25519_private=founder_identity['ed25519_private'],
        )
        new_key_dict = deserialize_from_cbor(new_key_bytes, dict)
        new_x25519_private = new_key_dict['x25519_private']

        # Founder decrypts new content with new cohort private key
        recovered = decrypt_from_sender(
            ciphertext=ciphertext,
            nonce=nonce,
            tag=tag,
            ephemeral_public_key_der=ephemeral_pub,
            recipient_private_key_der=new_x25519_private,
        )

        assert recovered == new_content, (
            f"Remaining member must decrypt new content; "
            f"expected {new_content!r}, got {recovered!r}"
        )


# ---------------------------------------------------------------------------
# TestExpelMemberErrorCases
# ---------------------------------------------------------------------------

class TestExpelMemberErrorCases:
    """Error cases: invalid inputs raise ValueError with identifying messages."""

    @pytest.mark.issue_12
    def test_expel_member_not_in_keybundle_raises_error(
        self, cohort_with_two_members, founder_identity
    ):
        """expel_member raises ValueError when expelled_member_id is not in the KeyBundle."""
        from peermodel.delegation import expel_member

        _, keybundle, _ = cohort_with_two_members

        with pytest.raises(ValueError) as exc_info:
            expel_member(
                keybundle=keybundle,
                expelled_member_id='nonexistent_member',
                remaining_member_identities=[founder_identity],
                initiator_identity=founder_identity,
            )

        assert 'nonexistent_member' in str(exc_info.value), (
            f"ValueError must identify the unknown member 'nonexistent_member', "
            f"got: {exc_info.value}"
        )

    @pytest.mark.issue_12
    def test_expel_member_initiator_not_in_keybundle_raises_error(
        self, cohort_with_two_members, member_b_identity
    ):
        """expel_member raises ValueError when initiator is not in the KeyBundle."""
        from peermodel.delegation import expel_member

        _, keybundle, _ = cohort_with_two_members

        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        outsider_identity = {
            'member_id': 'outsider',
            'x25519_public': x25519_pub,
            'x25519_private': x25519_priv,
            'ed25519_public': ed25519_pub,
            'ed25519_private': ed25519_priv,
        }

        with pytest.raises(ValueError) as exc_info:
            expel_member(
                keybundle=keybundle,
                expelled_member_id='member_b',
                remaining_member_identities=[member_b_identity],
                initiator_identity=outsider_identity,
            )

        assert 'outsider' in str(exc_info.value), (
            f"ValueError must identify the unauthorized initiator 'outsider', "
            f"got: {exc_info.value}"
        )
