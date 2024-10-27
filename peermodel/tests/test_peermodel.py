#!/usr/bin/env python

"""Tests for `peermodel` package."""

import pytest
from unittest import skip

import json

from hypothesis import given
from hypothesis.strategies import text

import peermodel
import peermodel.capabilities

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
def secdb(tmp_path, Fernet_key=Fernet.generate_key()):

    from peermodel.capabilities import IdentityManager

    class TestIdentityManager(IdentityManager):

        home = tmp_path / "id_tmp"

        @classmethod
        def ready(cls):
            return True
        
        @classmethod
        def getIdentity(cls):
            return "test_identity"
        
    class TestKeysystem(peermodel.capabilities.Keysystem):

        def encrypt(self, data, encrypt_key):
            return json.dumps(data)[::-1]

        def decrypt(self, keylist, data, encoding='UTF-8'):
            return json.loads(data[::-1])
        
    class TestRing(peermodel.Ring):

        @classmethod
        def lookupRing(cls, identity, db):
            return TestRing()

        @property
        def keysystem(self):
            return TestKeysystem()
        
        @property
        def guests(self):
            return iter([])
        
        @property
        def members(self):
            return iter([])
        
        def generateRecordKey(self):
            return Fernet_key
        
        @property
        def signature(self):
            return "test_sig"

    with peermodel.InMemoryCapabilitiesDatabase(identity_manager=TestIdentityManager) as db:
        db.ring = TestRing()
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



