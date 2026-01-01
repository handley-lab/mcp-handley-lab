"""Word document enums for internal operations.

Simple IntEnum types for internal use. OOXML uses STRING values,
so these are mainly for validation and API consistency.
"""

from enum import IntEnum


class WdSection(IntEnum):
    """Section break types matching OOXML w:type values."""

    CONTINUOUS = 0
    NEW_COLUMN = 1
    NEW_PAGE = 2
    EVEN_PAGE = 3
    ODD_PAGE = 4
