"""Security tests for provenance — ensure no secrets leak in provenance data."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from openscire.provenance import ProvenanceTracker
from openscire.provider import ChatMessage, Chunk, ModelInfo, ModelProvider, ProviderConfig
from pydantic import SecretStr

from tests.conftest import reset_provenance  # noqa: F401


class _EchoProvider(ModelProvider):
    """Provider that echoes back the message content."""

    PROVIDER_NAME = "echo"

    def _do_stream_chat(  # noqa: ARG002
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, object]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        async def _gen() -> AsyncIterator[Chunk]:
            text = messages[0].content if messages else ""
            yield Chunk(delta_content=str(text))

        return _gen()

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="echo")]


@pytest.mark.usefixtures("reset_provenance")
class TestProvenanceSecurity:
    """Ensure sensitive data does not leak into provenance entries."""

    @pytest.mark.asyncio
    async def test_no_api_key_in_provenance_params(self) -> None:
        tracker = ProvenanceTracker.get_tracker(
            "test-sec-params",
            storage_backend="in_memory",
        )
        config = ProviderConfig(
            default_model="secure-model",
            api_key=SecretStr("sk-very-secret-key-12345"),
            provenance_tracker=tracker,
        )
        provider = _EchoProvider(config)

        [c async for c in provider.stream_chat([ChatMessage.user("hello")])]

        for entry in tracker.storage.list():
            params_str = str(entry.parameters_snapshot)
            assert "sk-very-secret-key-12345" not in params_str
            assert entry.model_id == "secure-model"

    @pytest.mark.asyncio
    async def test_no_sensitive_data_in_signed_entries(self) -> None:
        from nacl.bindings import crypto_sign_seed_keypair

        tracker = ProvenanceTracker.get_tracker(
            "test-sec-signed",
            storage_backend="in_memory",
        )
        seed = b"a" * 32
        public_key, secret_key = crypto_sign_seed_keypair(seed)
        tracker._signing_key = secret_key.hex()

        config = ProviderConfig(
            default_model="signed-model",
            api_key=SecretStr("my-secret-key"),
            provenance_tracker=tracker,
        )
        provider = _EchoProvider(config)

        [c async for c in provider.stream_chat([ChatMessage.user("secret test")])]

        for entry in tracker.storage.list():
            assert entry.cryptographic_signature is not None
            serialized = entry.model_dump_json()
            assert "my-secret-key" not in serialized
