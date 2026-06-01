# SPDX-License-Identifier: Apache-2.0

"""Serialization-specific exception types."""

from openscire.constants import ErrorCode
from openscire.exceptions import openSciReError


class SerializationError(openSciReError):
    """Raised when serialization or deserialization fails."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
    ) -> None:
        super().__init__(
            error_code=ErrorCode.ERR_BASE,
            message=message,
            source=source,
        )


class SchemaVersionMismatchError(SerializationError):
    """Raised when the data's schema version does not match the current version."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
    ) -> None:
        super().__init__(message=message, source=source)


class UnknownFormatError(SerializationError):
    """Raised when a serialization format is not recognised or supported."""

    def __init__(
        self,
        message: str = "",
        source: str = "",
    ) -> None:
        super().__init__(message=message, source=source)
