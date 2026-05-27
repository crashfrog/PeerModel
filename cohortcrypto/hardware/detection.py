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


def find_all_pkcs11_libraries() -> List[str]:
    """Find all available PKCS#11 libraries on system.

    Checks:
    1. COHORTCRYPTO_PKCS11_PATH environment variable (colon-separated paths)
       - Env var paths are checked with os.path.exists to validate
    2. Platform-specific standard paths
       - System paths are verified to exist before returning

    Returns:
        List of paths to available PKCS#11 libraries (deduplicated)

    Handles:
    - Permission errors when checking paths
    - Missing libraries (returns empty list)
    - Path deduplication
    """
    found_libraries = []
    seen_paths = set()

    # Check environment variable first - user-specified paths are checked with os.path.exists
    # (not Path.exists() so they work correctly even when Path is mocked)
    if env_paths_str := os.environ.get('COHORTCRYPTO_PKCS11_PATH'):
        # Split by colon on Unix-like systems
        env_paths = env_paths_str.split(':')
        for path_str in env_paths:
            if path_str and path_str not in seen_paths:
                try:
                    if os.path.exists(path_str):
                        found_libraries.append(path_str)
                        seen_paths.add(path_str)
                except (PermissionError, OSError):
                    # Gracefully skip inaccessible paths
                    pass

    # Check platform-specific standard paths (using Path as it can be mocked for testing)
    system = platform.system()
    search_paths = PKCS11_SEARCH_PATHS.get(system, [])

    for path_str in search_paths:
        if path_str not in seen_paths:
            try:
                path_obj = Path(path_str)
                if path_obj.exists():
                    found_libraries.append(path_str)
                    seen_paths.add(path_str)
            except (PermissionError, OSError):
                # Gracefully skip inaccessible paths
                pass

    return found_libraries


def find_pkcs11_library() -> str:
    """Find PKCS#11 library on system.

    Checks:
    1. COHORTCRYPTO_PKCS11_PATH environment variable
    2. Platform-specific standard paths

    Returns:
        Path to PKCS#11 library (first found)

    Raises:
        PKCSLibraryNotFoundError: No library found
    """
    libraries = find_all_pkcs11_libraries()

    if libraries:
        return libraries[0]

    system = platform.system()
    search_paths = PKCS11_SEARCH_PATHS.get(system, [])

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
