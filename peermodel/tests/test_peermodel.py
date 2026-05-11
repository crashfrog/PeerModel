#!/usr/bin/env python

"""Tests for `peermodel` package."""

import pytest
from unittest import skip

import json

from hypothesis import given
from hypothesis.strategies import text

import peermodel
import peermodel.capabilities
import peermodel.primitives
from peermodel.delegation import SimpleCohort

from cryptography.fernet import Fernet

# @skip
# def test_pymonkey():
#     import pythonmonkey
#     assert pythonmonkey.require('crypto-js')


# def test_whether_pythonmonkey_even_works():
#     import pythonmonkey as pm
#     assert pm.require('helia/dist/src')
#     assert pm.require('@orbitdb/core')

# def test_whether_js2py_works():
#     import js2py as js
#     js.require('crypto-js')
#     js.require('helia')

# @skip
# def test_peer_to_peer_functions():
#     import pythonmonkey as js
#     import uuid
#     from pathlib import Path

#     crypt = js.require('crypto-js')
#     libp2p = js.require('libp2p')
#     ipfs = js.require('helia')
#     orbitdb = js.require('@orbitdb/core')
#     netconfig = js.require("./config/libp2p.js")

#     # libp2p = libp2p.createLibp2p(netconfig)
#     # ipfs = ipfs.createHelia(libp2p)

#     # randDir = Path('./') / uuid.uuid4() / "orbitdb"
#     # orbdb = orbitdb.createOrbitDB(ipfs, directory=str(randDir))
#     # db = orbdb.open('my-db', dict(AccessController=orbitdb.IPFSAccessController(dict(write=['*']))))

#     # assert db.address

#     # db.add("Hello world")

@pytest.fixture
def peer():
    return peermodel.App("test model")

@pytest.fixture
def memdb():
    with peermodel.InMemoryDocumentDatabase() as db:
        yield db


@pytest.fixture
def doc(peer):
    @peer.model
    class TestDocument:
        test: str = ""

    return TestDocument()

@pytest.fixture
def pickled_doc(memdb, doc):
    return doc._to_storage(memdb)

def test_record_id(doc):
    assert hasattr(doc, "_id")

def test_field(doc):
    assert hasattr(doc, "test")

def test_record_id_non_none(doc):
    assert doc._id

def test_doctype(doc):
    assert "TestDocument" in doc.__class__.__name__
    assert isinstance(doc, peermodel.DocumentObj)

def test_type_registry(doc):
    assert doc.__class__.__name__ in peermodel.DocumentObj.Meta._reg

def test_prepare_for_serialization(doc, pickled_doc):
    assert pickled_doc == ('TestDocument',
                          doc._id,
                          {"test": ""})

def test_mem_write(memdb, doc):
    assert memdb._persist_record(doc)

def test_mem_read(memdb, doc):
    with pytest.raises(KeyError):
        assert memdb._retrieve_record(type(doc), doc._id)

def test_mem_writeread(memdb, doc):
    memdb._persist_record(doc)
    assert memdb._retrieve_record(type(doc), doc._id) == doc


@pytest.fixture
def complexdoc(peer):
    @peer.model
    class InnerDocument:
        pass

    @peer.model
    class ComplexDocument:
        inner: InnerDocument
        testval: str = ""
        
    return ComplexDocument(inner=InnerDocument())

def test_has_storage(complexdoc):
    assert hasattr(complexdoc, "_to_storage")
    assert hasattr(complexdoc.inner, "_to_storage")
    assert not hasattr(complexdoc.testval, "_to_storage")

def test_prepare_for_serialization_inner(memdb, complexdoc):
    assert complexdoc.inner._to_storage(memdb) == ('InnerDocument', complexdoc.inner._id, {})

def test_prepare_for_serialization_complex(memdb, complexdoc):
    assert complexdoc._to_storage(memdb) == ('ComplexDocument',
                                             complexdoc._id,
                                             dict(inner=('InnerDocument',
                                                  complexdoc.inner._id,
                                                  {}),
                                                  testval=""))

def test_mem_write_complex(memdb, complexdoc):
    assert memdb._persist_record(complexdoc)
    # raise Exception(memdb)

def test_mem_writeread_complex(memdb, complexdoc):
    memdb._persist_record(complexdoc)
    assert memdb._retrieve_record(type(complexdoc), complexdoc._id) == complexdoc

@pytest.fixture
def aggdoc(peer):
    @peer.aggregated
    @peer.model
    class InnerAggregateDocument:
        pass

    @peer.model
    class AggregateDocument:
        inner: InnerAggregateDocument
        
    return AggregateDocument(inner=InnerAggregateDocument())

def test_mem_write_aggregated(memdb, aggdoc):
    assert memdb._persist_record(aggdoc)
    # raise Exception(memdb)

def test_mem_writeread_aggregated(memdb, aggdoc):
    memdb._persist_record(aggdoc)
    assert memdb._retrieve_record(type(aggdoc), aggdoc._id) == aggdoc


@pytest.fixture
def secdb(tmp_path):
    from peermodel.capabilities import SoftwareIdentityManager

    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = peermodel.primitives.generate_keypair()

    test_identity = {
        'identity_id': 'test_identity',
        'x25519_private': x25519_priv,
        'x25519_public': x25519_pub,
        'ed25519_private': ed25519_priv,
        'ed25519_public': ed25519_pub
    }

    class TestIdentityManager(SoftwareIdentityManager):
        home = tmp_path / "id_tmp"

        @classmethod
        def ready(cls):
            return True

        @classmethod
        def getIdentity(cls):
            return test_identity

    test_cohort = SimpleCohort(
        cohort_id='test_cohort',
        founder_identity=test_identity,
        members=[test_identity],
        guests=[],
        signing_key_der=ed25519_priv
    )

    with peermodel.InMemoryCapabilitiesDatabase(identity_manager=TestIdentityManager) as db:
        db.cohort = test_cohort
        yield db

def test_secure_write_is_secure(secdb, doc, pickled_doc):
    "Test should fail if the document content is recognizably in storage"
    secdb._persist_record(doc)
    assert pickled_doc[2] != secdb._records["TestDocument"][doc._id] and pickled_doc[2]

def test_secure_mem_write(secdb, doc):
    assert secdb._persist_record(doc)

def test_secure_mem_read(secdb, doc):
    with pytest.raises(KeyError):
        assert secdb._retrieve_record(type(doc), doc._id)

def test_secure_mem_writeread(secdb, doc):
    secdb._persist_record(doc)
    assert secdb._retrieve_record(type(doc), doc._id) == doc


def test_secure_mem_write_complex(secdb, complexdoc):
    assert secdb._persist_record(complexdoc)
    # raise Exception(memdb)

def test_secure_mem_writeread_complex(secdb, complexdoc):
    secdb._persist_record(complexdoc)
    assert secdb._retrieve_record(type(complexdoc), complexdoc._id) == complexdoc


def test_primitives_generate_keypair():
    """Test X25519/Ed25519 keypair generation."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = peermodel.primitives.generate_keypair()
    assert x25519_priv and len(x25519_priv) > 0
    assert x25519_pub and len(x25519_pub) > 0
    assert ed25519_priv and len(ed25519_priv) > 0
    assert ed25519_pub and len(ed25519_pub) > 0


def test_primitives_encrypt_decrypt_roundtrip():
    """Test encryption and decryption with X25519 ECDH."""
    sender_x25519_priv, sender_x25519_pub, _, _ = peermodel.primitives.generate_keypair()
    recipient_x25519_priv, recipient_x25519_pub, _, _ = peermodel.primitives.generate_keypair()

    plaintext = b"Hello, encrypted world!"

    ciphertext, nonce, tag, ephemeral_pub = peermodel.primitives.encrypt_to_recipient(
        plaintext, recipient_x25519_pub
    )

    decrypted = peermodel.primitives.decrypt_from_sender(
        ciphertext, nonce, tag, ephemeral_pub, recipient_x25519_priv
    )

    assert decrypted == plaintext


def test_primitives_sign_verify():
    """Test Ed25519 signing and verification."""
    _, _, ed25519_priv, ed25519_pub = peermodel.primitives.generate_keypair()

    message = b"Sign this message"
    signature = peermodel.primitives.sign_bytes(message, ed25519_priv)

    assert peermodel.primitives.verify_bytes(message, signature, ed25519_pub) is True


def test_primitives_verify_wrong_signature():
    """Test that verification fails with wrong signature."""
    _, _, ed25519_priv, ed25519_pub = peermodel.primitives.generate_keypair()

    message = b"Sign this message"
    wrong_signature = b"wrong signature bytes"

    assert peermodel.primitives.verify_bytes(message, wrong_signature, ed25519_pub) is False


def test_primitives_decrypt_with_wrong_key():
    """Test that decryption fails with wrong key."""
    from peermodel.exceptions import DecryptionError

    recipient1_x25519_priv, recipient1_x25519_pub, _, _ = peermodel.primitives.generate_keypair()
    recipient2_x25519_priv, _, _, _ = peermodel.primitives.generate_keypair()

    plaintext = b"Secret message"

    ciphertext, nonce, tag, ephemeral_pub = peermodel.primitives.encrypt_to_recipient(
        plaintext, recipient1_x25519_pub
    )

    with pytest.raises(DecryptionError):
        peermodel.primitives.decrypt_from_sender(
            ciphertext, nonce, tag, ephemeral_pub, recipient2_x25519_priv
        )


def test_keysystem_encrypt_decrypt():
    """Test SoftwareKeysystem encryption/decryption of Fernet keys."""
    x25519_priv1, x25519_pub1, ed25519_priv1, ed25519_pub1 = peermodel.primitives.generate_keypair()
    x25519_priv2, x25519_pub2, ed25519_priv2, ed25519_pub2 = peermodel.primitives.generate_keypair()

    keysystem1 = peermodel.capabilities.SoftwareKeysystem(
        x25519_priv1, x25519_pub1, ed25519_priv1, ed25519_pub1
    )
    keysystem2 = peermodel.capabilities.SoftwareKeysystem(
        x25519_priv2, x25519_pub2, ed25519_priv2, ed25519_pub2
    )

    fernet_key = Fernet.generate_key()
    plaintext = b"Hello keysystem"

    envelope = keysystem1.encrypt(fernet_key, x25519_pub2)
    encrypted_data = Fernet(fernet_key).encrypt(plaintext)

    decrypted = keysystem2.decrypt([envelope], encrypted_data)
    assert decrypted == plaintext.decode('utf-8')





def test_pretty_print_nested_record(aggdoc):
    assert "\n".join(aggdoc.pretty_print()) == f"""(AggregateDocument,
 {aggdoc._id},
   {{
   inner:
     (InnerAggregateDocument,
      {aggdoc.inner._id},
        {{
        }}
     )
   }}
)"""

@pytest.fixture
def perdb():
    return peermodel.PersistedCapabilitiesDatabase()



