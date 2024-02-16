from abc import ABC, abstractmethod

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


class Peer(ABC):
    pass