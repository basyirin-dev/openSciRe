# SPDX-License-Identifier: Apache-2.0

"""Generic serializer for scientific domain models (JSON, YAML)."""

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError

from openscire.serialization.exceptions import (
    SchemaVersionMismatchError,
    SerializationError,
    UnknownFormatError,
)
from openscire.serialization.schemas import (
    CURRENT_SERIALIZATION_VERSION,
    SerializationEnvelope,
)

SUPPORTED_FORMATS = frozenset({"json", "yaml", "msgpack"})


class Serializer:
    """Serialize and deserialize Pydantic models to/from JSON, YAML, and msgpack."""

    @staticmethod
    def dumps(
        model: Any,  # noqa: ANN401
        format: str = "json",
    ) -> str | bytes:
        """Serialize a model to a string or bytes.

        Args:
            model: A Pydantic BaseModel or dict-like object.
            format: Output format ('json', 'yaml', 'msgpack').

        Returns:
            Serialized representation as str (json/yaml) or bytes (msgpack).

        Raises:
            UnknownFormatError: If the format is not supported.
        """
        if format not in SUPPORTED_FORMATS:
            msg = f"Unsupported format: {format}. Choose from {sorted(SUPPORTED_FORMATS)}"
            raise UnknownFormatError(msg, source="serialization")

        data = model.model_dump(mode="json") if hasattr(model, "model_dump") else dict(model)
        model_name = type(model).__name__

        envelope = SerializationEnvelope(
            model_name=model_name,
            data=data,
        )
        envelope_dict = envelope.model_dump(mode="json")

        if format == "json":
            return json.dumps(envelope_dict, indent=2, default=str)
        if format == "yaml":
            return yaml.safe_dump(envelope_dict, default_flow_style=False, sort_keys=False)  # type: ignore[no-any-return]
        return _msgpack_pack(envelope_dict)

    @staticmethod
    def loads(
        data: str | bytes,
        model_class: type[Any],  # noqa: ANN401
        format: str = "json",
    ) -> Any:  # noqa: ANN401
        """Deserialize a string or bytes back into a Pydantic model.

        Args:
            data: Serialized data (str for json/yaml, bytes for msgpack).
            model_class: The Pydantic model class to instantiate.
            format: Source format ('json', 'yaml', 'msgpack').

        Returns:
            An instance of model_class populated from the data.

        Raises:
            UnknownFormatError: If the format is not supported.
            SerializationError: If parsing or validation fails.
            SchemaVersionMismatchError: If the schema version is incompatible.
        """
        if format not in SUPPORTED_FORMATS:
            msg = f"Unsupported format: {format}. Choose from {sorted(SUPPORTED_FORMATS)}"
            raise UnknownFormatError(msg, source="serialization")

        try:
            raw: dict[str, object]
            if format == "json":
                raw = json.loads(str(data))
            elif format == "yaml":
                raw = yaml.safe_load(str(data))
            else:
                assert isinstance(data, bytes), "msgpack data must be bytes"
                raw = _msgpack_unpack(data)
        except (json.JSONDecodeError, yaml.YAMLError, ValueError) as exc:
            msg = f"Failed to parse {format} data: {exc}"
            raise SerializationError(msg, source="serialization") from exc

        try:
            envelope = SerializationEnvelope.model_validate(raw)
        except PydanticValidationError as exc:
            msg = f"Invalid envelope data: {exc}"
            raise SerializationError(msg, source="serialization") from exc

        _validate_envelope(envelope, model_class)

        try:
            return model_class.model_validate(envelope.data)
        except PydanticValidationError as exc:
            msg = f"Model validation failed: {exc}"
            raise SerializationError(msg, source="serialization") from exc

    @staticmethod
    def dump(
        model: Any,  # noqa: ANN401
        path: str | Path,
        format: str | None = None,
    ) -> None:
        """Serialize a model and write it to a file.

        Args:
            model: A Pydantic BaseModel or dict-like object.
            path: File path to write to.
            format: Output format (detected from extension if None).

        Raises:
            UnknownFormatError: If the format cannot be detected or is unsupported.
        """
        path = Path(path)
        fmt = format or _detect_format(path)
        serialized = Serializer.dumps(model, format=fmt)
        mode = "wb" if fmt == "msgpack" else "w"
        kwargs: dict[str, Any] = {"encoding": "utf-8"} if fmt != "msgpack" else {}
        with path.open(mode, **kwargs) as f:
            f.write(serialized)

    @staticmethod
    def load(
        path: str | Path,
        model_class: type[Any],  # noqa: ANN401
        format: str | None = None,
    ) -> Any:  # noqa: ANN401
        """Read and deserialize a model from a file.

        Args:
            path: File path to read from.
            model_class: The Pydantic model class to instantiate.
            format: Source format (detected from extension if None).

        Returns:
            An instance of model_class.

        Raises:
            UnknownFormatError: If the format cannot be detected or is unsupported.
            SerializationError: If parsing or validation fails.
            SchemaVersionMismatchError: If the schema version is incompatible.
        """
        path = Path(path)
        fmt = format or _detect_format(path)
        mode = "rb" if fmt == "msgpack" else "r"
        kwargs: dict[str, Any] = {"encoding": "utf-8"} if fmt != "msgpack" else {}
        with path.open(mode, **kwargs) as f:
            raw = f.read()
        return Serializer.loads(raw, model_class, format=fmt)


def _validate_envelope(
    envelope: SerializationEnvelope,
    model_class: type[Any],
) -> None:
    parsed = int(envelope.serialization_version)
    current = int(CURRENT_SERIALIZATION_VERSION)
    if parsed > current:
        msg = (
            f"Data serialization version {parsed} is newer than "
            f"current version {current}. Upgrade openscire-core to read this file."
        )
        raise SchemaVersionMismatchError(msg, source="serialization")

    expected = model_class.__name__
    if envelope.model_name != expected:
        msg = f"Model name mismatch: data contains '{envelope.model_name}', expected '{expected}'"
        raise SchemaVersionMismatchError(msg, source="serialization")


def _detect_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".json"}:
        return "json"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    if suffix in {".msgpack", ".mpk"}:
        return "msgpack"
    msg = f"Cannot detect format from file extension: {path.suffix}"
    raise UnknownFormatError(msg, source="serialization")


def _msgpack_pack(data: dict[str, object]) -> bytes:
    try:
        import msgpack
    except ImportError:
        msg = "msgpack is not installed. Install with: pip install 'openscire-core[perf]'"
        raise SerializationError(msg, source="serialization") from None
    return msgpack.packb(data)  # type: ignore[no-any-return]


def _msgpack_unpack(data: bytes) -> dict[str, object]:
    try:
        import msgpack
    except ImportError:
        msg = "msgpack is not installed. Install with: pip install 'openscire-core[perf]'"
        raise SerializationError(msg, source="serialization") from None
    result = msgpack.unpackb(data)
    if not isinstance(result, dict):
        msg = f"Expected dict from msgpack, got {type(result).__name__}"
        raise SerializationError(msg, source="serialization")
    return result
