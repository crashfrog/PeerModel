#!/usr/bin/env python

"""Tests for `peermodel` package."""

import pytest
from unittest import skip

import peermodel

@skip
def test_whether_js_2_py_even_works():
    import js2py
    import uuid
    from pathlib import Path

    libp2p = js2py.require('libp2p')
    ipfs = js2py.require('helia')
    orbitdb = js2py.require('@orbitdb/core')
    netconfig = js2py.require("./config/libp2p.js")

    libp2p = libp2p.createLibp2p(netconfig)
    ipfs = ipfs.createHelia(libp2p)

    randDir = Path('./') / uuid.uuid4() / "orbitdb"
    orbdb = orbitdb.createOrbitDB(ipfs, directory=str(randDir))
    db = orbdb.open('my-db', dict(AccessController=orbitdb.IPFSAccessController(dict(write=['*']))))

    assert db.address

    db.add("Hello world")


@pytest.fixture
def memdb():
    with peermodel.InMemoryDocumentDatabase() as db:
        return db
    
@pytest.fixture
def doc():
    @peermodel.peermodel
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

def test_prepare_for_serialization(memdb, doc, pickled_doc):
    assert pickled_doc == ('TestDocument',
                          doc._id,
                          {"test":""})

    
def test_mem_write(memdb, doc):
    assert memdb._persist_record(doc)

def test_mem_read(memdb, doc):
    with pytest.raises(KeyError):
        assert memdb._retrieve_record(type(doc), doc._id)

def test_mem_writeread(memdb, doc):
    memdb._persist_record(doc)
    assert memdb._retrieve_record(type(doc), doc._id) == doc


@pytest.fixture
def complexdoc():
    @peermodel.peermodel
    class InnerDocument:
        pass

    @peermodel.peermodel
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
def aggdoc():
    @peermodel.aggregated
    @peermodel.peermodel
    class InnerAggregateDocument:
        pass

    @peermodel.peermodel
    class AggregateDocument:
        inner: InnerAggregateDocument
        
    return AggregateDocument(inner=InnerAggregateDocument())

def test_mem_write_aggregated(memdb, aggdoc):
    assert memdb._persist_record(aggdoc)
    # raise Exception(memdb)

def test_mem_writeread_aggregated(memdb, aggdoc):
    memdb._persist_record(aggdoc)
    assert memdb._retrieve_record(type(aggdoc), aggdoc._id) == aggdoc

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

def test_peer_subclassing_works_the_way_I_expect(perdb):
    assert type(perdb.peer) == peermodel.PersistedCapabilitiesDatabase.Peer

