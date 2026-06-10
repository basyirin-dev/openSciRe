# openSciRe — Serialization

Purpose: Unified serialization layer supporting JSON, YAML, and MessagePack formats with a versioned
`SerializationEnvelope` for schema migration and cross-version compatibility.

Status: Stable

Public API:

- `Serializer` — Generic serializer with Pydantic model de/serialization, format dispatch, and error
  handling
- `SerializationEnvelope` — Versioned wrapper carrying `data`, `schema_version`, `format`,
  `created_at`, and `provenance_id`
- `SerializationError` — Raised when serialization or deserialization fails
- `SchemaVersionMismatchError` — Raised when envelope schema version is incompatible
- `UnknownFormatError` — Raised when requested format is not in `SUPPORTED_FORMATS`
- `CURRENT_SERIALIZATION_VERSION` — Current envelope schema version (integer, bumped on breaking
  changes)
- `SUPPORTED_FORMATS` — Set of supported format strings: `{"json", "yaml", "msgpack"}`
