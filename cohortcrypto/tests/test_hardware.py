"""Tests for hardware token operations and mock hardware."""

import pytest
import os
from unittest.mock import patch

import cohortcrypto
from cohortcrypto import (
    enumerate_tokens,
    open_token,
    credential_from_token,
    TokenInfo,
    MockTokenSession,
    PIVSlot,
    PINError,
    TokenNotFoundError
)


@pytest.fixture(autouse=True)
def enable_mock_hardware():
    """Enable mock hardware for all tests."""
    os.environ['COHORTCRYPTO_MOCK_HARDWARE'] = '1'
    yield
    if 'COHORTCRYPTO_MOCK_HARDWARE' in os.environ:
        del os.environ['COHORTCRYPTO_MOCK_HARDWARE']


@pytest.fixture
def mock_token_session():
    """Create a mock token session."""
    return MockTokenSession.create()


# Token Enumeration Tests (Mock)

def test_enumerate_tokens_returns_list():
    """enumerate_tokens returns a list."""
    tokens = enumerate_tokens()
    assert isinstance(tokens, list)


def test_enumerate_tokens_mock_has_token():
    """Mock mode returns at least one token."""
    tokens = enumerate_tokens()
    assert len(tokens) > 0


def test_enumerate_tokens_mock_token_structure():
    """Mock token has correct TokenInfo structure."""
    tokens = enumerate_tokens()
    token = tokens[0]

    assert isinstance(token, TokenInfo)
    assert isinstance(token.slot_id, int)
    assert isinstance(token.token_label, str)
    assert isinstance(token.token_serial, str)
    assert isinstance(token.manufacturer, str)


def test_enumerate_tokens_mock_token_values():
    """Mock token has expected values."""
    tokens = enumerate_tokens()
    token = tokens[0]

    assert "Mock" in token.token_label
    assert token.slot_id == 0
    assert token.manufacturer != ""


# Token Session Tests (Mock)

def test_open_token_returns_context_manager():
    """open_token returns a context manager."""
    cm = open_token(pin="123456")
    assert hasattr(cm, '__enter__')
    assert hasattr(cm, '__exit__')


def test_open_mock_token_context_manager():
    """Can use open_token as context manager."""
    with open_token(pin="123456") as session:
        assert session is not None
        assert isinstance(session, MockTokenSession)


def test_open_token_default_pin():
    """open_token accepts default test PIN."""
    with open_token(pin="123456") as session:
        assert session._authenticated


def test_open_token_wrong_pin_raises_error():
    """open_token with wrong PIN raises PINError."""
    with pytest.raises(PINError):
        with open_token(pin="wrong_pin") as session:
            pass


def test_open_token_closes_session():
    """Token session is closed after context manager exits."""
    with open_token(pin="123456") as session:
        session_id = id(session)

    assert session._closed


def test_open_token_accepts_piv_slot():
    """open_token accepts piv_slot parameter."""
    with open_token(pin="123456", piv_slot=PIVSlot.SLOT_9C) as session:
        assert session.piv_slot == PIVSlot.SLOT_9C


def test_open_token_default_piv_slot():
    """open_token defaults to SLOT_9A."""
    with open_token(pin="123456") as session:
        assert session.piv_slot in [PIVSlot.SLOT_9A, PIVSlot.AUTO]


# Mock Token Session Tests

def test_mock_token_session_create():
    """MockTokenSession.create() generates fresh keypairs."""
    session = MockTokenSession.create()

    assert session.x25519_public is not None
    assert len(session.x25519_public) > 0
    assert session.ed25519_public is not None
    assert len(session.ed25519_public) > 0


def test_mock_token_session_unique_keypairs():
    """Each MockTokenSession has unique keypairs."""
    session1 = MockTokenSession.create()
    session2 = MockTokenSession.create()

    assert session1.x25519_public != session2.x25519_public
    assert session1.ed25519_public != session2.ed25519_public


def test_mock_token_session_authenticate():
    """MockTokenSession.authenticate() with correct PIN succeeds."""
    session = MockTokenSession.create()
    session.authenticate("123456")
    assert session._authenticated


def test_mock_token_session_wrong_pin():
    """MockTokenSession.authenticate() with wrong PIN raises error."""
    session = MockTokenSession.create()

    with pytest.raises(PINError):
        session.authenticate("wrong")


def test_mock_token_session_sign():
    """MockTokenSession can sign messages."""
    session = MockTokenSession.create()
    session.authenticate("123456")

    message = b"test message"
    signature = session.sign(message)

    assert isinstance(signature, bytes)
    assert len(signature) == 64  # Ed25519 signature is 64 bytes


def test_mock_token_session_sign_requires_auth():
    """MockTokenSession.sign() requires authentication."""
    session = MockTokenSession.create()

    with pytest.raises(RuntimeError):
        session.sign(b"test")


def test_mock_token_session_ecdh():
    """MockTokenSession can perform ECDH."""
    session1 = MockTokenSession.create()
    session1.authenticate("123456")

    session2 = MockTokenSession.create()
    session2.authenticate("123456")

    # Session1 performs ECDH with session2's public key
    shared_secret = session1.ecdh(session2.x25519_public)

    assert isinstance(shared_secret, bytes)
    assert len(shared_secret) == 32  # X25519 shared secret is 32 bytes


def test_mock_token_session_ecdh_requires_auth():
    """MockTokenSession.ecdh() requires authentication."""
    session = MockTokenSession.create()
    other_session = MockTokenSession.create()

    with pytest.raises(RuntimeError):
        session.ecdh(other_session.x25519_public)


def test_mock_token_session_ecdh_symmetry():
    """ECDH with swapped keys produces same shared secret."""
    session1 = MockTokenSession.create()
    session1.authenticate("123456")

    session2 = MockTokenSession.create()
    session2.authenticate("123456")

    secret1 = session1.ecdh(session2.x25519_public)
    secret2 = session2.ecdh(session1.x25519_public)

    assert secret1 == secret2


def test_mock_token_session_close():
    """MockTokenSession.close() clears state."""
    session = MockTokenSession.create()
    session.authenticate("123456")

    session.close()

    assert session._closed
    assert not session._authenticated


# Member Credential Tests

def test_credential_from_token():
    """credential_from_token creates MemberCredential."""
    session = MockTokenSession.create()
    session.authenticate("123456")

    cred = credential_from_token(session, 'alice')

    assert cred is not None
    assert cred.member_id == 'alice'


def test_credential_from_token_has_public_keys():
    """MemberCredential includes public keys."""
    session = MockTokenSession.create()
    session.authenticate("123456")

    cred = credential_from_token(session, 'alice')

    assert cred.x25519_public == session.x25519_public
    assert cred.ed25519_public == session.ed25519_public


def test_credential_from_token_hardware_backed():
    """MemberCredential from token is hardware_backed."""
    session = MockTokenSession.create()
    session.authenticate("123456")

    cred = credential_from_token(session, 'alice')

    assert cred.hardware_backed is True


def test_credential_from_token_algorithm_fields():
    """MemberCredential includes algorithm fields."""
    session = MockTokenSession.create()
    session.authenticate("123456")

    cred = credential_from_token(session, 'alice')

    assert cred.signing_algorithm == "ed25519"
    assert cred.encryption_algorithm == "x25519"


def test_credential_from_token_multiple_members():
    """Can create multiple credentials from same token."""
    session = MockTokenSession.create()
    session.authenticate("123456")

    alice_cred = credential_from_token(session, 'alice')
    bob_cred = credential_from_token(session, 'bob')

    assert alice_cred.member_id == 'alice'
    assert bob_cred.member_id == 'bob'
    assert alice_cred.x25519_public == bob_cred.x25519_public


# Integration Tests (Mock)

def test_open_token_provides_authenticated_session():
    """Opened token session is authenticated."""
    with open_token(pin="123456") as session:
        # Should be able to sign without additional auth
        message = b"test"
        signature = session.sign(message)
        assert len(signature) == 64


def test_open_token_session_ecdh_works():
    """Can perform ECDH with opened token."""
    with open_token(pin="123456") as session1:
        other_session = MockTokenSession.create()
        other_session.authenticate("123456")

        shared_secret = session1.ecdh(other_session.x25519_public)
        assert len(shared_secret) == 32


def test_multiple_tokens_in_enumerate():
    """Can enumerate mock tokens (at least one)."""
    tokens = enumerate_tokens()

    assert len(tokens) >= 1
    for token in tokens:
        assert token.slot_id >= 0
        assert token.token_label
        assert token.token_serial


# PIVSlot Tests

def test_piv_slot_enum_values():
    """PIVSlot enum has expected values."""
    assert PIVSlot.AUTO.value == "auto"
    assert PIVSlot.SLOT_9A.value == "9A"
    assert PIVSlot.SLOT_9C.value == "9C"


def test_piv_slot_auto_accepted():
    """PIVSlot.AUTO is accepted by open_token."""
    with open_token(pin="123456", piv_slot=PIVSlot.AUTO) as session:
        assert session.piv_slot == PIVSlot.AUTO


# Real Hardware Tests (Optional, Marked)

@pytest.mark.hardware
def test_enumerate_real_tokens():
    """Enumerate real tokens on system (requires hardware).

    This test is skipped by default. Run with:
    pytest -m hardware
    """
    if 'COHORTCRYPTO_MOCK_HARDWARE' in os.environ:
        del os.environ['COHORTCRYPTO_MOCK_HARDWARE']

    try:
        tokens = enumerate_tokens()
        # If we get here, hardware detection worked
        assert isinstance(tokens, list)
    except Exception as e:
        # Hardware not available - expected in most environments
        pytest.skip(f"Hardware not available: {e}")


@pytest.mark.hardware
def test_open_real_token():
    """Open real token session (requires hardware).

    This test is skipped by default. Run with:
    pytest -m hardware
    """
    if 'COHORTCRYPTO_MOCK_HARDWARE' in os.environ:
        del os.environ['COHORTCRYPTO_MOCK_HARDWARE']

    try:
        with open_token(pin=None) as session:
            assert session is not None
    except Exception as e:
        # Hardware not available - expected in most environments
        pytest.skip(f"Hardware not available: {e}")
