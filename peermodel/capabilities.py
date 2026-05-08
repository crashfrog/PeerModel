from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import partial
from typing import Dict, Union, Any

from pathlib import Path
from os import makedirs
from cryptography.fernet import Fernet

import json

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


        

class Site(ABC):
    

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
    

class Guests(ABC):
    

    def invite(self):
        pass


    def review(self):
        pass


    def approve(self):
        pass


    def revoke(self):
        pass
