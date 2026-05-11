"""PIV card slot detection and management."""

from enum import Enum
from typing import Dict, Optional

from ..exceptions import PIVSlotError

try:
    from . import PIVSlot
except ImportError:
    class PIVSlot(Enum):
        """PIV card slot identifiers."""
        AUTO = "auto"
        SLOT_9A = "9A"
        SLOT_9C = "9C"
        SLOT_9D = "9D"
        SLOT_9E = "9E"

PIV_SLOT_PURPOSE = {
    PIVSlot.SLOT_9A: "PIV Authentication (encryption)",
    PIVSlot.SLOT_9C: "Digital Signature (signing)",
    PIVSlot.SLOT_9D: "Key Management",
    PIVSlot.SLOT_9E: "Card Authentication",
}

PIV_SLOT_OBJECT_ID = {
    PIVSlot.SLOT_9A: 0x9A01,
    PIVSlot.SLOT_9C: 0x9C03,
    PIVSlot.SLOT_9D: 0x9D03,
    PIVSlot.SLOT_9E: 0x9E04,
}


def detect_piv_slots(pkcs11_session) -> Dict[PIVSlot, dict]:
    """Detect available PIV slots on token.

    Searches for certificates and keys in standard PIV slots.

    Args:
        pkcs11_session: Open PKCS#11 session

    Returns:
        Dict mapping PIVSlot to key information (empty if no objects found)

    Raises:
        PIVSlotError: If unable to query token
    """
    available_slots = {}

    try:
        for piv_slot, obj_id in PIV_SLOT_OBJECT_ID.items():
            try:
                template = [
                    (0x00000080, obj_id),  # CKA_ID
                ]
                objs = pkcs11_session.find_objects(template)

                if objs:
                    available_slots[piv_slot] = {
                        'has_key': True,
                        'objects': objs,
                        'purpose': PIV_SLOT_PURPOSE.get(piv_slot, 'Unknown'),
                    }
            except Exception:
                pass

        return available_slots
    except Exception as e:
        raise PIVSlotError(f"Failed to detect PIV slots: {e}")


def select_best_piv_slot(available_slots: Dict[PIVSlot, dict]) -> PIVSlot:
    """Select best PIV slot for operations.

    Preference order:
    1. 9C (Digital Signature) for signing
    2. 9A (PIV Authentication) for encryption
    3. 9D (Key Management) as fallback
    4. 9E (Card Authentication) as last resort

    Args:
        available_slots: Dict from detect_piv_slots

    Returns:
        Best PIVSlot to use

    Raises:
        PIVSlotError: No suitable slot found
    """
    preferred_order = [
        PIVSlot.SLOT_9C,
        PIVSlot.SLOT_9A,
        PIVSlot.SLOT_9D,
        PIVSlot.SLOT_9E,
    ]

    for slot in preferred_order:
        if slot in available_slots:
            return slot

    raise PIVSlotError(
        "No suitable PIV slot found. Available: "
        + ", ".join(str(s.value) for s in available_slots.keys())
        if available_slots
        else "No PIV slots available"
    )


def get_piv_algorithm(piv_slot: PIVSlot) -> tuple[str, str]:
    """Get preferred algorithms for PIV slot.

    Args:
        piv_slot: The PIV slot to query

    Returns:
        Tuple of (signing_algorithm, encryption_algorithm)
    """
    if piv_slot == PIVSlot.SLOT_9C:
        return ("ed25519", "x25519")
    elif piv_slot == PIVSlot.SLOT_9A:
        return ("ed25519", "x25519")
    else:
        return ("ed25519", "x25519")
