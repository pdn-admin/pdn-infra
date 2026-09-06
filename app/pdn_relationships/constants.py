from enum import Enum


class RelationshipType(Enum):
    """Supported relationship types for the advisor."""
    PARTNER = "partner"       # בן/בת זוג
    FRIEND = "friend"         # חבר/ה
    COLLEAGUE = "colleague"   # עמית/ה לעבודה


PDN_CODES = [
    "a3", "a7", "a11",
    "e1", "e5", "e9",
    "p2", "p6", "p10",
    "t4", "t8", "t12",
]
