from abc import ABC, abstractmethod
from typing import Iterator
from contextlib import AbstractContextManager, AbstractAsyncContextManager, wraps
from functools import wraps
from collections import defaultdict
from collections.abc import MutableMapping
from dataclasses import dataclass, InitVar, field, fields, KW_ONLY
import uuid
import json

from peermodel.capabilities import IdentityManager, UnauthorizedAccess
from peermodel.delegation import Ring, Guest
from peermodel.iplddict import NamespacedIPLDDictionary

from cryptography.fernet import Fernet

"Main peermodel module."


# libp2p = js2py.require('libp2p')
# ipfs = js2py.require('helia')
# orbitdb = js2py.require('@orbitdb/core')
# netconfig = js2py.require("./config/libp2p.js")


class Index:
    "Index on this type"

    indexes = []

    def __init__(self, indexed_type):
        self.indexes.append(self)


class Aggregate:

    tables = []

    "Store value as a related record, aggregated records can be looked up on their own"
    def __init__(self, related_type):
        self.tables.append(self)

@dataclass
class DocumentObj:
    "Mixin class for model objects that provides for serialization and reference"

    _id:KW_ONLY = field(default_factory=lambda: str(uuid.uuid4()))

    class Meta:

        _reg = dict()

        # def __new__(cls, *args, **kwargs):
        #     cls.Meta._reg[cls.__name__] = cls
        #     return super().__new__(*args, **kwargs)

    def __post_init__(self, _id=None):
        if not _id:
            _id = str(uuid.uuid4())
        self._id = _id

    def __init_subclass__(cls):
        cls.Meta._reg[cls.__name__] = cls

    # def __set_name__(self, owner, name):
    #     super().__set_name__(self, owner, name)


    # def __init__(self, _id=None, *args, **kwargs):
    #     if not _id:
    #         self._id = str(uuid.uuid4())
    #     else:
    #         self._id = _id
    #     super().__init__(*args, **kwargs)
    
    def __eq__(self, other):
        return all([self.__class__ == other.__class__,
                hasattr(other, "__dict__") and self.__dict__ == other.__dict__,
                hasattr(other, "_id") and self._id == other._id,
                ])
    
    def __repr__(self):
        fields = ", ".join((f"{name}={value}" for name, value in self.__dict__.items() if name != "_id"))
        return f"{self.__class__.__name__} {self._id[-8:]} ({fields})"
    
    def __str__(self):
        return repr(self)
    
    def _to_storage(self, db):
        record = dict()
        #return self.__class__.__name__, {name:(db._create_reference(value._to_storage()) if (hasattr(value, "_is_aggregate") and value.is_aggregate) else value) for name, value in self.__dict__.items()}
        for field in fields(self):
            name = field.name
            value = getattr(self, name)
            if name == "_id":
                continue
            if hasattr(value, "_is_aggregate") and value._is_aggregate:
                record[name] = db._create_reference(value)
            elif hasattr(value, "_to_storage"):
                record[name] = value._to_storage(db)
            else:
                record[name] = value
        return self.__class__.__name__, self._id, record
    
    def pretty_print(self, indent=0):
        yield f"{' '*indent}({self.__class__.__name__},"
        yield f" {' '*indent}{self._id},"
        yield f" {' '*(indent+2)}{{"
        for field in fields(self):
            yield f" {' '*(indent+2)}{field.name}:"
            if hasattr(val := getattr(self, field.name), 'pretty_print'):
                yield from val.pretty_print(indent=indent+5)
        yield f" {' '*(indent+2)}}}"
        yield f"{' '*indent})"


    @classmethod
    def _from_storage(cls, db, id, rec):
        new_rec = dict()
        for name, value in rec.items():
            if val := db._is_reference(value):
                new_rec[name] = db._retrieve_record(*val)
            else:
                try:
                    typename, id, subrecord = value
                    new_rec[name] = DocumentObj.Meta._reg[typename]._from_storage(db, id, subrecord)
                except (TypeError, ValueError, KeyError):
                    new_rec[name] = value
        try:
            obj = cls(**new_rec)
        except:
            raise Exception(db, rec)
        obj._id = id
        return obj


class AbstractTypedDocumentDatabase(AbstractContextManager):

    #Class configuration and delegates

     
    def __init__(self, app_name=None):
        self.app_name = app_name

    @abstractmethod
    def _persist_record(self, record) -> bool:
        return False

    @abstractmethod
    def _retrieve_record(self, record_type, record_id) -> DocumentObj:
        return None

    def _is_reference(self, value):
        "If value is how the database's persistence mechanism stores a reference, then return the type and id, else false"
        try:
            _, typename, id, *_ = value
            return DocumentObj.Meta._reg[typename], id
        except (TypeError, ValueError, KeyError):
            return False
    
    def _create_reference(self, record):
        "If value is aggregable, return a reference to it"
        self._persist_record(record)
        return "Ref", type(record).__name__, record._id
    
    # Contextmanager api

    @abstractmethod
    def __enter__(self):
        pass

    @abstractmethod
    def __exit__(self, *args, **kwargs):
        pass

    # CLI api

    def list(self):
        pass

    def build_index(self):
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

class InMemoryDocumentDatabase(AbstractTypedDocumentDatabase):
    "Basic API implementation. No access control, no persistence"

    def __enter__(self):
        self._records = defaultdict(dict)
        return self

    def __exit__(self, *args, **kwargs):
        self._records = defaultdict(dict)


    def _persist_record(self, record):
        name, id, to_store = record._to_storage(self)
        self._records[name][id] = to_store
        return True

    def _retrieve_record(self, record_type, record_id):
        return record_type._from_storage(self, record_id, self._records[record_type.__name__][record_id])
    
    def __repr__(self):
        return str(self._records)



class InMemoryCapabilitiesDatabase(InMemoryDocumentDatabase):
    "Encrypted records implementation"

    Ring = Ring
    IdentityManager = IdentityManager

    def __init__(self, identity_manager, encoding='UTF-8', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.identity = identity_manager.getIdentity()
        self.ring = self.Ring.lookupRing(self.identity, self)
        self.encoding = encoding

    def _persist_record(self, record):
        name, id, to_store = record._to_storage(self)
        record_readkey = self.ring.generateRecordKey()
        self._records[name][id] = [ 
            self.ring.signature,
            [self.ring.keysystem.encrypt(record_readkey.encode(self.encoding), reader) for reader in self.ring.readers], 
            Fernet(record_readkey).encrypt(json.dumps(to_store).encode(self.encoding))
        ]
        return True

    def _retrieve_record(self, record_type, record_id):
        signature, keylist, encrypted_record = self._records[record_type.__name__][record_id]
        try:
            record = self.ring.keysystem.decrypt(keylist, encrypted_record, encoding=self.encoding)
        except UnauthorizedAccess as e:
            e.encryptor_signature = signature
            raise e

        return record_type._from_storage(self, record_id, record)


class PersistedDatabase(InMemoryDocumentDatabase):
    "Persists records using IPFS / IPLD"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._records = NamespacedIPLDDictionary(self.app_name)
        
    def __enter__(self):
        return self # Do nothing

    def __exit__(self, *args, **kwargs):
        pass # Do nothing

class PersistedCapabilitiesDatabase(PersistedDatabase, InMemoryCapabilitiesDatabase):
    pass

class App:

    def __init__(self, name, identitymanager=IdentityManager, dbtypeclass=PersistedCapabilitiesDatabase):
        self.app_name = name

        # Create the PeerFile special type

        @self.model
        @self.aggregated
        class PeerFile:
            "Special value for file references"
            
            _url: str
            hash: str = ""

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

        self.PeerFile = PeerFile


    # @dataclass_transform()
    def model(self, model):
        "PeerModel class decorator"

        return dataclass(slots=True)(type(model.__name__, 
                    (dataclass(kw_only=True)(model), DocumentObj), 
                    {}))
        

    # @dataclass_transform()
    def event(self, model=None):
        "PeerModel event decorator"
        pass
        
    def aggregated(self, model):
        "Declare this portion of the document is aggregated and held by reference"
        model._is_aggregate = True
        Aggregate(model)
        return model


    def indexed(self, model):
        "Declare that the document is indexed by this field"
        model._is_indexed = True
        Index(model)
        return model


def with_database(func=None, dbtypeclass=PersistedCapabilitiesDatabase):
    "Context decorator"
    if func:
        @wraps(func)
        def database_wrapper(*args, **kwargs):
            with dbtypeclass() as db:
                return func(db)
        return database_wrapper
    return with_database
