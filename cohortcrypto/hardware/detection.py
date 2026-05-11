"""Hardware token detection (Phase 3B stub)."""

from typing import List
from ..exceptions import PKCSLibraryNotFoundError
from .mock import TokenInfo


def detect_tokens() -> List[TokenInfo]:
    """Detect all hardware tokens on system.

    This is a Phase 3B stub. Real implementation will:
    - Search for PKCS#11 libraries in standard system paths
    - Check COHORTCRYPTO_PKCS11_PATH environment variable
    - Use python-pkcs11 to enumerate tokens

    Returns:
        List of TokenInfo for each detected token

    Raises:
        PKCSLibraryNotFoundError: No PKCS#11 library found
    """
    raise PKCSLibraryNotFoundError(
        "Real hardware token detection not yet implemented. "
        "Set COHORTCRYPTO_MOCK_HARDWARE=1 for testing."
    )
