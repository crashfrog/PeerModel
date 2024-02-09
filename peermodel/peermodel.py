from contextlib import AbstractContextManager, AbstractAsyncContextManager, wraps
from functools import wraps
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
    _url: str

    class Content:
        "Content file-like object"
        pass

    @property
    def content(self):
        "Return a file-like object"
        return self.Content(self)
    
    @content.setter
    def _write_file(self, bytestream, identity=None):
        "Write bytes if your identity permits it"
        pass


class Peer2PeerDatabase(AbstractAsyncContextManager, AbstractContextManager):
     class Site:
          
          def create(self):
              pass
          
          def invite(self):
              pass
          
          def review(self):
              pass
          
          def approve(self):
              pass
          
          def revoke(self):
              pass
          
          def regenerate(self):
              pass
          
     
     class Guests:
         
        def invite(self):
            pass

        def review(self):
            pass

        def approve(self):
            pass

        def revoke(self):
            pass

     
     class Peer:
         pass
     
     def __init__(self):
         self.site = self.Site()
         self.guests = self.Guests()
         self.peer = self.Peer()
     
     def initialize_identity(self):
         pass
     
     def list(self):
         pass
     
     def create(self):
         pass
     
     def retrieve(self):
         pass
     
     def update(self):
         pass
     
     def delete(self):
         pass
     
     def undelete(self):
         pass
     
     def tag(self):
         pass
     
     def untag(self):
         pass
     
     def publish(self):
         pass


def with_database(func=None):
    "Context decorator"
    if func:
        @wraps(func)
        def database_wrapper(*args, **kwargs):
            with Peer2PeerDatabase() as db:
                return func(db)
        return database_wrapper
    return with_database
