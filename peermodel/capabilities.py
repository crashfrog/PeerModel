from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import partial
from typing import Dict, Union, Any

from pathlib import Path
from os import makedirs
import json
import base64

from peermodel.exceptions import UnauthorizedAccess, KeyGenerationError
from peermodel import primitives

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


class SoftwareKeysystem(Keysystem):
    """Keysystem using software X25519 key agreement and Ed25519 signing."""

    def __init__(self, x25519_private_der, x25519_public_der, ed25519_private_der, ed25519_public_der):
        """Initialize keysystem with DER-encoded keypairs.

        Args:
            x25519_private_der: X25519 private key (DER-encoded)
            x25519_public_der: X25519 public key (DER-encoded)
            ed25519_private_der: Ed25519 private key (DER-encoded)
            ed25519_public_der: Ed25519 public key (DER-encoded)
        """
        self.x25519_private_der = x25519_private_der
        self.x25519_public_der = x25519_public_der
        self.ed25519_private_der = ed25519_private_der
        self.ed25519_public_der = ed25519_public_der

    def encrypt(self, data: Union[str, bytes], recipient_public_key_der) -> bytes:
        """Encrypt data to recipient's X25519 public key using ephemeral ECDH.

        Args:
            data: Plaintext to encrypt (str or bytes)
            recipient_public_key_der: Recipient's X25519 public key (DER-encoded)

        Returns:
            bytes: Encrypted envelope containing [ciphertext, nonce, tag, ephemeral_public_key]
        """
        if isinstance(data, str):
            data = data.encode('utf-8')

        ciphertext, nonce, tag, ephemeral_public = primitives.encrypt_to_recipient(
            data, recipient_public_key_der
        )

        return [ciphertext, nonce, tag, ephemeral_public]

    def decrypt(self, keylist, data: bytes, encoding='UTF-8') -> Union[str, bytes]:
        """Decrypt data by trying each encrypted key in keylist.

        Args:
            keylist: List of [ciphertext, nonce, tag, ephemeral_public_key] envelopes
            data: Encrypted record data (Fernet token)
            encoding: Text encoding for string results

        Returns:
            Union[str, bytes]: Decrypted plaintext

        Raises:
            UnauthorizedAccess: If no key in keylist can decrypt the data
        """
        from cryptography.fernet import Fernet as FernetCipher
        for envelope in keylist:
            try:
                ciphertext, nonce, tag, ephemeral_public = envelope
                fernet_key_bytes = primitives.decrypt_from_sender(
                    ciphertext, nonce, tag, ephemeral_public, self.x25519_private_der
                )
                f = FernetCipher(fernet_key_bytes)
                plaintext = f.decrypt(data)
                if encoding:
                    return plaintext.decode(encoding)
                return plaintext
            except Exception:
                continue

        raise UnauthorizedAccess(
            "Unauthorized access; no key issued to your identity",
            encryptor_signature=None
        )


class SoftwareIdentityManager(IdentityManager):
    """Identity manager that stores keypairs in local JSON configuration."""

    @dataclass
    class Config:
        identity_id: str = ""
        x25519_private: str = ""
        x25519_public: str = ""
        ed25519_private: str = ""
        ed25519_public: str = ""

    def __init__(self, identity_id=None):
        super().__init__()
        self.identity_id = identity_id

    @classmethod
    def generateIdentity(cls, identity_id):
        """Generate a new identity and save configuration.

        Args:
            identity_id: Unique identifier for this identity

        Returns:
            SoftwareIdentityManager: New identity manager instance
        """
        manager = cls(identity_id)

        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = primitives.generate_keypair()

        manager.config = cls.Config(
            identity_id=identity_id,
            x25519_private=base64.b64encode(x25519_priv).decode('ascii'),
            x25519_public=base64.b64encode(x25519_pub).decode('ascii'),
            ed25519_private=base64.b64encode(ed25519_priv).decode('ascii'),
            ed25519_public=base64.b64encode(ed25519_pub).decode('ascii')
        )

        makedirs(IdentityManager.home.parent, exist_ok=True)
        manager.dump()

        return manager

    @classmethod
    def getIdentity(cls):
        """Load identity from configuration file.

        Returns:
            dict: Identity information with keypairs
        """
        if not IdentityManager.home.exists():
            raise KeyGenerationError("Identity not initialized. Run 'prmdl init' first.")

        with open(IdentityManager.home, 'r') as f:
            config = json.load(f)

        return {
            'identity_id': config['identity_id'],
            'x25519_private': base64.b64decode(config['x25519_private']),
            'x25519_public': base64.b64decode(config['x25519_public']),
            'ed25519_private': base64.b64decode(config['ed25519_private']),
            'ed25519_public': base64.b64decode(config['ed25519_public'])
        }

    @classmethod
    def ready(cls):
        """Check if identity is initialized."""
        return IdentityManager.home.exists()

    def dump(self):
        """Save configuration to file."""
        config_dict = {
            'identity_manager': self.__class__.__name__,
            **vars(self.config)
        }
        makedirs(IdentityManager.home.parent, exist_ok=True)
        with open(IdentityManager.home, 'w') as f:
            json.dump(config_dict, f, indent=2)


class HardwareKeysystem(Keysystem):
    """Hardware-backed keysystem using PKCS#11 tokens."""

    def __init__(self, session):
        """Initialize with open token session.

        Args:
            session: TokenSession from cohortcrypto.hardware.open_token
                    Must have _x25519_private attribute (mock or real hardware)
        """
        self.session = session
        # For decryption, we need the X25519 private key
        # In mock mode: session._x25519_private
        # In real hardware: would use token's on-token ECDH operations
        if hasattr(session, '_x25519_private'):
            self.x25519_private_der = session._x25519_private
        else:
            # Real hardware tokens don't expose private keys
            # Would need to implement on-token ECDH via PKCS#11
            self.x25519_private_der = None

    def encrypt(self, data: Union[str, bytes], recipient_public_key_der) -> bytes:
        """Encrypt data to recipient's public key using software ECDH.

        Note: Encryption always uses software (ephemeral keypair for ECDH).
        Hardware token is not used for encryption operations.

        Args:
            data: Plaintext to encrypt (str or bytes)
            recipient_public_key_der: Recipient's X25519 public key (DER-encoded)

        Returns:
            bytes: Encrypted envelope containing [ciphertext, nonce, tag, ephemeral_public_key]
        """
        if isinstance(data, str):
            data = data.encode('utf-8')

        ciphertext, nonce, tag, ephemeral_public = primitives.encrypt_to_recipient(
            data, recipient_public_key_der
        )

        return [ciphertext, nonce, tag, ephemeral_public]

    def decrypt(self, keylist, data: bytes, encoding='UTF-8') -> Union[str, bytes]:
        """Decrypt data using hardware token's private key.

        Args:
            keylist: List of [ciphertext, nonce, tag, ephemeral_public_key] envelopes
            data: Encrypted record data (Fernet token)
            encoding: Text encoding for string results

        Returns:
            Union[str, bytes]: Decrypted plaintext

        Raises:
            UnauthorizedAccess: If no key in keylist can decrypt the data
        """
        from cryptography.fernet import Fernet as FernetCipher

        if not self.x25519_private_der:
            raise UnauthorizedAccess(
                "Hardware token does not expose private key; cannot decrypt",
                encryptor_signature=None
            )

        for envelope in keylist:
            try:
                ciphertext, nonce, tag, ephemeral_public = envelope
                fernet_key_bytes = primitives.decrypt_from_sender(
                    ciphertext, nonce, tag, ephemeral_public, self.x25519_private_der
                )
                f = FernetCipher(fernet_key_bytes)
                plaintext = f.decrypt(data)
                if encoding:
                    return plaintext.decode(encoding)
                return plaintext
            except Exception:
                continue

        raise UnauthorizedAccess(
            "Unauthorized access; no key issued to your identity",
            encryptor_signature=None
        )


class HardwareIdentityManager(IdentityManager):
    """Identity manager backed by hardware token (PIV card, YubiKey, etc.)."""

    @dataclass
    class Config:
        token_label: str = ""
        token_serial: str = ""
        slot_id: int = 0
        piv_slot: str = "AUTO"

    def __init__(self, session=None):
        super().__init__()
        self.session = session

    @classmethod
    def ready(cls):
        """Check if hardware token is available."""
        try:
            import cohortcrypto.hardware as hw
            tokens = hw.enumerate_tokens()
            return len(tokens) > 0
        except Exception:
            return False

    @classmethod
    def from_token(cls, session):
        """Create identity manager from open token session.

        Args:
            session: Open TokenSession from cohortcrypto.hardware.open_token

        Returns:
            HardwareIdentityManager: New identity manager with session
        """
        manager = cls(session)
        manager.config = cls.Config(
            token_label=session.token_label,
            token_serial=session.token_serial,
            slot_id=session.slot_id,
            piv_slot=session.piv_slot.value if hasattr(session.piv_slot, 'value') else str(session.piv_slot)
        )
        return manager

    def getIdentity(self) -> dict:
        """Get identity from hardware token.

        Returns:
            dict: Identity information with public keys from token
        """
        if not self.session:
            raise KeyGenerationError("No token session available")

        return {
            'token_label': self.session.token_label,
            'token_serial': self.session.token_serial,
            'slot_id': self.session.slot_id,
            'piv_slot': self.session.piv_slot,
            'x25519_public': self.session.x25519_public,
            'ed25519_public': self.session.ed25519_public,
            'signing_algorithm': self.session.signing_algorithm,
            'encryption_algorithm': self.session.encryption_algorithm,
            'hardware_backed': True
        }

    def dump(self):
        """Save hardware identity configuration to file.

        Persists only metadata (token label, serial, slot).
        Never stores private keys (impossible with real hardware anyway).
        """
        config_dict = {
            'identity_manager': self.__class__.__name__,
            **vars(self.config)
        }
        makedirs(IdentityManager.home.parent, exist_ok=True)
        with open(IdentityManager.home, 'w') as f:
            json.dump(config_dict, f, indent=2)


# Specific IdentityManager implementations