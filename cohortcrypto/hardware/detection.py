"""Hardware token detection."""

import os
import platform
from pathlib import Path
from typing import List, Optional

from ..exceptions import PKCSLibraryNotFoundError
from .mock import TokenInfo

PKCS11_SEARCH_PATHS = {
    'Linux': [
        '/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so',
        '/usr/lib/opensc-pkcs11.so',
        '/usr/local/lib/opensc-pkcs11.so',
        '/usr/lib/x86_64-linux-gnu/libykcs11.so',
        '/usr/lib/libykcs11.so',
    ],
    'Darwin': [
        '/Library/OpenSC/lib/opensc-pkcs11.so',
        '/usr/local/lib/opensc-pkcs11.so',
        '/usr/local/lib/libykcs11.dylib',
    ],
    'Windows': [
        r'C:\Windows\System32\opensc-pkcs11.dll',
        r'C:\Program Files\OpenSC Project\OpenSC\pkcs11\opensc-pkcs11.dll',
        r'C:\Program Files\Yubico\Yubico PIV Tool\bin\libykcs11.dll',
    ],
}


def find_pkcs11_library() -> str:
    """Find PKCS#11 library on system.

    Checks:
    1. COHORTCRYPTO_PKCS11_PATH environment variable
    2. Platform-specific standard paths

    Returns:
        Path to PKCS#11 library

    Raises:
        PKCSLibraryNotFoundError: No library found
    """
    if env_path := os.environ.get('COHORTCRYPTO_PKCS11_PATH'):
        if Path(env_path).exists():
            return env_path

    system = platform.system()
    search_paths = PKCS11_SEARCH_PATHS.get(system, [])

    for path in search_paths:
        if Path(path).exists():
            return path

    raise PKCSLibraryNotFoundError(
        f"No PKCS#11 library found on {system}. "
        f"Install OpenSC or YubiKey Manager, or set COHORTCRYPTO_PKCS11_PATH. "
        f"Searched: {', '.join(search_paths)}"
    )


def detect_tokens() -> List[TokenInfo]:
    """Detect all hardware tokens on system.

    Returns:
        List of TokenInfo for each detected token

    Raises:
        PKCSLibraryNotFoundError: No PKCS#11 library found
    """
    pkcs11_lib_path = find_pkcs11_library()

    try:
        import pkcs11
    except ImportError:
        raise PKCSLibraryNotFoundError(
            "python-pkcs11 not installed. "
            "Install it with: pip install python-pkcs11"
        )

    try:
        lib = pkcs11.lib(pkcs11_lib_path)
        tokens = []

        for slot in lib.get_slots(token_present=True):
            token = slot.get_token()
            tokens.append(
                TokenInfo(
                    slot_id=slot.slot_id,
                    token_label=token.label.strip(),
                    token_serial=token.serial.strip(),
                    manufacturer=token.manufacturer_id.strip(),
                )
            )

        return tokens
    except Exception as e:
        raise PKCSLibraryNotFoundError(
            f"Failed to enumerate tokens from {pkcs11_lib_path}: {e}"
        )
