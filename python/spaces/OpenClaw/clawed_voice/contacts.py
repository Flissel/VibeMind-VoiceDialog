"""
Contact name resolution for WhatsApp messaging.

Maps friendly names to E.164 phone numbers.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Singleton contacts dict
_contacts: Optional[Dict[str, str]] = None


def load_contacts(contacts_file: Optional[Path] = None) -> Dict[str, str]:
    """
    Load contacts from JSON file.

    Args:
        contacts_file: Path to contacts.json (defaults to ../contacts.json)

    Returns:
        Dictionary mapping names to phone numbers
    """
    global _contacts

    if _contacts is not None:
        return _contacts

    if contacts_file is None:
        # Default: project root / contacts.json
        contacts_file = Path(__file__).parent.parent / "contacts.json"

    if not contacts_file.exists():
        logger.warning(f"Contacts file not found: {contacts_file}")
        _contacts = {}
        return _contacts

    try:
        with open(contacts_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Filter out comments (keys starting with _)
        _contacts = {
            k: v for k, v in data.items()
            if not k.startswith("_") and isinstance(v, str)
        }

        logger.info(f"Loaded {len(_contacts)} contacts from {contacts_file}")
        return _contacts

    except Exception as e:
        logger.error(f"Failed to load contacts: {e}")
        _contacts = {}
        return _contacts


def resolve_contact(name_or_number: str) -> str:
    """
    Resolve contact name to phone number.

    Args:
        name_or_number: Contact name or E.164 phone number

    Returns:
        E.164 phone number (original if already a number, resolved if a name)

    Examples:
        >>> resolve_contact("mama")
        "+491234567890"
        >>> resolve_contact("+491234567890")
        "+491234567890"
    """
    # Already a phone number (starts with +)
    if name_or_number.startswith("+"):
        return name_or_number

    # Load contacts if needed
    contacts = load_contacts()

    # Try case-insensitive lookup
    name_lower = name_or_number.lower()
    for contact_name, phone in contacts.items():
        if contact_name.lower() == name_lower:
            logger.debug(f"Resolved '{name_or_number}' -> '{phone}'")
            return phone

    # Not found - return original (might fail later, but that's okay)
    logger.warning(f"Contact '{name_or_number}' not found in contacts.json")
    return name_or_number


def reload_contacts():
    """Force reload contacts from file."""
    global _contacts
    _contacts = None
    return load_contacts()


__all__ = ["load_contacts", "resolve_contact", "reload_contacts"]
