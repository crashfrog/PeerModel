from peermodel.capabilities import IdentityManager, Keysystem
from typing import Union, Iterator
from abc import ABC, abstractmethod
from collections import defaultdict
from itertools import chain

"""
A ring model of delegation where the ring is the group of people who have access to a peermodel database.

A ring is a group of people who have access to a peermodel database. Each ring has a unique name, and each person in the ring has a unique identity. The ring is the group of people who have access to the database, and the identity is the unique identifier for each person in the ring.

A peermodel database includes a default 'public' ring to which every user of the database belongs.

A ring member can extend 'guest' access to other users. Guest access allows the guest to read the database, but not to write to it.

A ring member can invite a guest to join the ring. A majority of ring members must approve the invitation before the guest is added to the ring.

"""

class Ring(ABC):

    KeyExchange = defaultdict(lambda: defaultdict(Keysystem))
    
    # CLI api

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

    # public API
    @classmethod
    @abstractmethod
    def lookupRing(cls, identity, db):
        return 

    @property
    @abstractmethod
    def keysystem(self) -> Keysystem:
        pass

    @property
    @abstractmethod
    def guests(self) -> Iterator[Keysystem]:
        pass

    @property
    @abstractmethod
    def members(self) -> Iterator[Keysystem]:
        pass

    @property
    def readers(self) -> Iterator[Keysystem]:
        return chain(self.members, self.guests)
    
    @abstractmethod
    def generateRecordKey(self):
        pass

    @property
    @abstractmethod
    def signature(self):
        pass
    
    

class Guest(ABC):
    

    def invite(self):
        pass


    def review(self):
        pass


    def approve(self):
        pass


    def revoke(self):
        pass
