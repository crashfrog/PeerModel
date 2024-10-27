from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import partial
from typing import Dict, Union, Any

from pathlib import Path
from os import makedirs
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import json

class UnauthorizedAccess(Exception):
    pass

class IdentityManager(ABC):

    class Meta:

        _reg = dict()

    home = Path.home() / '.peermodel' / 'idconfig.json'

    @dataclass
    class Config:
        pass

    def __init_subclass__(cls):
        cls.Meta._reg[cls.__name__] = cls

    def __init__(self):
        self.config = self.Config()

    @classmethod
    @abstractmethod
    def getIdentity(self):
        pass
    
    @classmethod
    @abstractmethod
    def ready(self):
        return False
    
    @classmethod
    def load(cls, fp):
        config = json.load(fp)
        manager = cls.Meta._reg[config['identity_manager']]()
        manager.config = manager.Config(**config)
        return manager
    
    def dump(self):
        with open(self.home, 'w') as config:
            json.dump(self.config, config, default=vars, indent=2)



class Keysystem(ABC):

    @abstractmethod
    def encrypt(self, data: Union[str, bytes], encrypt_key) -> bytes:
        pass

    @abstractmethod
    def decrypt(self, keylist, data: bytes, encoding='UTF-8') -> Union[str, bytes]:
        pass
    
class ECDSAKeysystem(Keysystem):

    def encrypt(self, data: Union[str, bytes], key) -> bytes:
        return data

    def decrypt(self, keylist, data: bytes, encoding='UTF-8') -> Union[str, bytes]:
        # Instantiate an ECDSA keypair
        priv = Ed25519PrivateKey(IdentityManager.getIdentity()['Ed25519PrivateKey'])
        for key in keylist:
            # Attempt to decode keylist with my private key using ECDSA
            # If successful, result is a Fernet key that can decrypt data
            try:
                return Fernet(priv.exchange(key)).decrypt(data)
            except:
                pass
            raise UnauthorizedAccess("Unauthorized access; no key issued to your identity")


# Specific IdentityManager implementations