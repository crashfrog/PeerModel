from contextlib import AbstractContextManager, AbstractAsyncContextManager
import js2py


"Main peermodel module."


libp2p = js2py.require('libp2p')
ipfs = js2py.require('helia')
orbitdb = js2py.require('@orbitdb/core')
netconfig = js2py.require("./config/libp2p.js")


class Index:
    "Index on this type"
    def __init__(self, indexed_type):
        pass


class Aggregate:
    "Store value as a relation"
    def __init__(self, related_type):
        pass


def peermodel(model=None):
    "PeerModel class decorator"
    def peermodel_args(*,
            stuff,
            more_stuff,
    ):
        "PeerModel arguments"
        def classbuilder(model):
            "Inspect the class and build a model"
            pass
        return classbuilder
    if not model:
        return peerevent_args
    return peerevent_args()(model)
    


def peerevent(model=None):
    "PeerModel event decorator"
    def peerevent_args(*,
        stuff,
        more_stuff,
    ):
        "PeerEvent arguments"
        def classbuilder(model):
            "Inspect the class and build an event"
            pass
        return classbuilder
    if not model:
        return peerevent_args
    return peerevent_args()(model)
    
def aggregated(model):
    "Declare this portion of the document is aggregated and held by reference"
    return model


def indexed(model):
    "Declare that the document is indexed by this field"
    return model
    

@peermodel
@aggregated
class PeerFile:
    "Special value for file references"
    
    hash: str
    
    


class Peer2PeerDatabase(AbstractAsyncContextManager, AbstractContextManager):
    pass