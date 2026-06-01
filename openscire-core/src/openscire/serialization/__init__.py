# SPDX-License-Identifier: Apache-2.0

"""Serialization layer for openSciRe.

Supports versioned envelopes, multiple output formats, schema migration,
and forward/backward compatibility for all domain models.
"""

from openscire.serialization.exceptions import (
    SchemaVersionMismatchError,
    SerializationError,
    UnknownFormatError,
)
from openscire.serialization.schemas import (
    CURRENT_SERIALIZATION_VERSION,
    SerializationEnvelope,
)
from openscire.serialization.serializer import SUPPORTED_FORMATS, Serializer

__all__ = [
    "Serializer",
    "SerializationEnvelope",
    "SerializationError",
    "SchemaVersionMismatchError",
    "UnknownFormatError",
    "CURRENT_SERIALIZATION_VERSION",
    "SUPPORTED_FORMATS",
]
