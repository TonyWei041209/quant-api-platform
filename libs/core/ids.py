"""ID generation utilities."""
from __future__ import annotations

import uuid


def new_id() -> uuid.UUID:
    return uuid.uuid4()


def parse_id(value: str) -> uuid.UUID:
    return uuid.UUID(value)
