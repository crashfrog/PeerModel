"""Hardware module for peermodel.cohortcrypto compatibility layer.

Re-exports all hardware interfaces and functions from the root cohortcrypto.hardware module.
"""

from cohortcrypto.hardware import (
    enumerate_tokens,
    open_token,
    credential_from_token,
    generate_keys_on_token,
    TokenInfo,
    MockTokenSession,
    PIVSlot,
    KeyInfo,
    TokenSession,
)

__all__ = [
    'enumerate_tokens',
    'open_token',
    'credential_from_token',
    'generate_keys_on_token',
    'TokenInfo',
    'MockTokenSession',
    'PIVSlot',
    'KeyInfo',
    'TokenSession',
]
