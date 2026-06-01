# SPDX-License-Identifier: Apache-2.0

"""Tests for the MCP Integration (Task 2.7)."""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from openscire.exceptions import ModelProviderError
from openscire.provider import (
    ChatMessage,
    Chunk,
    MCPProvider,
    MCPServerConfig,
    ModelInfo,
    ModelProvider,
    ProviderConfig,
)


class _MockChatProvider(ModelProvider):
    """Minimal chat provider for MCPProvider tests."""

    PROVIDER_NAME = "mock_chat"

    def __init__(self, model: str = "test-model") -> None:
        super().__init__(ProviderConfig(default_model=model))

    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        yield Chunk(delta_content="chat response")

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id="test-model", name="test-model", provider="mock_chat")]

    def supports_tool_use(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return False


@pytest.fixture
def messages() -> list[ChatMessage]:
    return [ChatMessage.user("Hello")]


@pytest.fixture
def chat_provider() -> _MockChatProvider:
    return _MockChatProvider()


@pytest.fixture
def mcp_server_config() -> MCPServerConfig:
    return MCPServerConfig(
        name="test-server",
        command=["python", "-m", "some_mcp_server"],
    )


class TestMCPServerConfig:
    def test_defaults(self) -> None:
        cfg = MCPServerConfig(name="test", command=["echo"])
        assert cfg.name == "test"
        assert cfg.enabled is True
        assert cfg.env == {}

    def test_disabled_server(self) -> None:
        cfg = MCPServerConfig(name="test", command=["echo"], enabled=False)
        assert cfg.enabled is False


class TestMCPToolSchemaConversion:
    def test_to_openai_schema(self) -> None:
        from mcp.types import Tool
        from openscire.provider.mcp import _mcp_tool_to_openai_schema

        tool = Tool(
            name="read_file",
            description="Read a file from disk",
            inputSchema={"type": "object", "properties": {"path": {"type": "string"}}},
        )
        schema = _mcp_tool_to_openai_schema("fs", tool)
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "fs__read_file"
        assert "parameters" in schema["function"]

    def test_split_prefixed_name(self) -> None:
        from openscire.provider.mcp import _split_prefixed_name

        server, tool = _split_prefixed_name("fs__read_file")
        assert server == "fs"
        assert tool == "read_file"

    def test_split_prefixed_name_no_separator(self) -> None:
        from openscire.provider.mcp import _split_prefixed_name

        server, tool = _split_prefixed_name("bare_tool")
        assert server == ""
        assert tool == "bare_tool"


class TestMCPProviderInit:
    def test_requires_chat_provider(self, mcp_server_config: MCPServerConfig) -> None:
        p = MCPProvider(
            chat_provider=_MockChatProvider(),
            mcp_servers=[mcp_server_config],
        )
        assert p.PROVIDER_NAME == "mcp"
        assert p.supports_tool_use() is True

    def test_empty_mcp_servers_allowed(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(chat_provider=chat_provider)
        assert p._mcp_servers == []

    def test_disabled_servers_skipped(self, chat_provider: _MockChatProvider) -> None:
        enabled = MCPServerConfig(name="a", command=["echo"], enabled=True)
        disabled = MCPServerConfig(name="b", command=["echo"], enabled=False)
        p = MCPProvider(chat_provider=chat_provider, mcp_servers=[enabled, disabled])
        assert len(p._mcp_servers) == 1
        assert p._mcp_servers[0].name == "a"


class TestMCPProviderStreamChat:
    @pytest.mark.anyio
    async def test_delegates_to_chat_provider(
        self, chat_provider: _MockChatProvider, messages: list[ChatMessage]
    ) -> None:
        p = MCPProvider(chat_provider=chat_provider)
        chunks = [c async for c in p.stream_chat(messages)]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert texts == ["chat response"]

    @pytest.mark.anyio
    async def test_passes_tools_through(
        self, chat_provider: _MockChatProvider, messages: list[ChatMessage]
    ) -> None:
        p = MCPProvider(chat_provider=chat_provider)
        user_tools = [{"type": "function", "function": {"name": "my_tool"}}]
        chunks = [c async for c in p.stream_chat(messages, tools=user_tools)]
        texts = [c.delta_content for c in chunks if c.delta_content]
        assert texts == ["chat response"]


class TestMCPProviderDelegation:
    @pytest.mark.anyio
    async def test_list_models(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(chat_provider=chat_provider)
        models = await p.list_models()
        assert len(models) == 1
        assert models[0].id == "test-model"

    @pytest.mark.anyio
    async def test_get_token_count(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(chat_provider=chat_provider)
        count = await p.get_token_count("hello world")
        assert count == max(1, len("hello world") // 4)

    @pytest.mark.anyio
    async def test_get_context_window(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(chat_provider=chat_provider)
        window = await p.get_context_window()
        assert window == 4096

    def test_supports_vision(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(chat_provider=chat_provider)
        assert p.supports_vision() is False

    def test_supports_streaming(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(chat_provider=chat_provider)
        assert p.supports_streaming() is True

    @pytest.mark.anyio
    async def test_get_model_card(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(chat_provider=chat_provider)
        card = await p.get_model_card()
        assert card.provider == "mock_chat"
        assert any("MCP tools" in lim for lim in card.limitations)


class TestMCPToolDiscovery:
    @pytest.mark.anyio
    async def test_discover_tools(self, chat_provider: _MockChatProvider) -> None:
        from mcp.types import Tool

        p = MCPProvider(
            chat_provider=chat_provider,
            mcp_servers=[MCPServerConfig(name="fs", command=["echo"])],
        )
        mock_tool = Tool(
            name="read",
            description="read files",
            inputSchema={"type": "object"},
        )
        session = p._get_session("fs")
        session.list_tools = AsyncMock(return_value=[mock_tool])

        schemas = await p.list_mcp_tools()
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "fs__read"

    @pytest.mark.anyio
    async def test_tool_cache(self, chat_provider: _MockChatProvider) -> None:
        from mcp.types import Tool

        p = MCPProvider(
            chat_provider=chat_provider,
            mcp_servers=[MCPServerConfig(name="srv", command=["echo"])],
        )
        mock_tool = Tool(name="t1", description="", inputSchema={"type": "object"})
        session = p._get_session("srv")
        session.list_tools = AsyncMock(return_value=[mock_tool])

        await p.list_mcp_tools()
        await p.list_mcp_tools()
        session.list_tools.assert_awaited_once()

    @pytest.mark.anyio
    async def test_merges_into_stream_chat(
        self, chat_provider: _MockChatProvider, messages: list[ChatMessage]
    ) -> None:
        from mcp.types import Tool

        p = MCPProvider(
            chat_provider=chat_provider,
            mcp_servers=[MCPServerConfig(name="srv", command=["echo"])],
        )
        mock_tool = Tool(name="t1", description="", inputSchema={"type": "object"})
        session = p._get_session("srv")
        session.list_tools = AsyncMock(return_value=[mock_tool])

        chunks = [c async for c in p.stream_chat(messages)]
        assert any(c.delta_content for c in chunks)


class TestMCPToolExecution:
    @pytest.mark.anyio
    async def test_execute_tool(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(
            chat_provider=chat_provider,
            mcp_servers=[MCPServerConfig(name="srv", command=["echo"])],
        )
        session = p._get_session("srv")
        session.call_tool = AsyncMock(return_value="tool result")

        result = await p.execute_mcp_tool("srv__my_tool", {"arg": "val"})
        assert result == "tool result"
        session.call_tool.assert_awaited_once_with("my_tool", {"arg": "val"})

    @pytest.mark.anyio
    async def test_execute_tool_unknown_server(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(chat_provider=chat_provider)
        with pytest.raises(ModelProviderError, match="not configured"):
            await p.execute_mcp_tool("unknown__tool", {})


class TestMCPResources:
    @pytest.mark.anyio
    async def test_list_resources(self, chat_provider: _MockChatProvider) -> None:
        from mcp.types import Resource

        p = MCPProvider(
            chat_provider=chat_provider,
            mcp_servers=[MCPServerConfig(name="srv", command=["echo"])],
        )
        mock_resource = Resource(
            uri="file:///test.txt",
            name="test.txt",
            description="A test file",
            mimeType="text/plain",
        )
        session = p._get_session("srv")
        session.list_resources = AsyncMock(return_value=[mock_resource])

        resources = await p.list_mcp_resources()
        assert len(resources) == 1
        assert resources[0]["uri"] == "file:///test.txt"
        assert resources[0]["server"] == "srv"

    @pytest.mark.anyio
    async def test_read_resource(self, chat_provider: _MockChatProvider) -> None:
        from mcp.types import Resource

        p = MCPProvider(
            chat_provider=chat_provider,
            mcp_servers=[MCPServerConfig(name="srv", command=["echo"])],
        )
        mock_resource = Resource(uri="file:///test.txt", name="test.txt")
        session = p._get_session("srv")
        session.list_resources = AsyncMock(return_value=[mock_resource])
        session.read_resource = AsyncMock(return_value="file contents")

        content = await p.read_mcp_resource("file:///test.txt")
        assert content == "file contents"

    @pytest.mark.anyio
    async def test_read_resource_not_found(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(
            chat_provider=chat_provider,
            mcp_servers=[MCPServerConfig(name="srv", command=["echo"])],
        )
        session = p._get_session("srv")
        session.list_resources = AsyncMock(return_value=[])

        with pytest.raises(ModelProviderError, match="not found"):
            await p.read_mcp_resource("file:///missing.txt")


class TestMCPHealth:
    @pytest.mark.anyio
    async def test_healthy_without_mcp_servers(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(chat_provider=chat_provider)
        status = await p.health()
        assert status.ok is True

    @pytest.mark.anyio
    async def test_healthy_with_mcp_servers(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(
            chat_provider=chat_provider,
            mcp_servers=[MCPServerConfig(name="srv", command=["echo"])],
        )
        session = p._get_session("srv")
        session.list_tools = AsyncMock(return_value=[])

        status = await p.health()
        assert status.ok is True

    @pytest.mark.anyio
    async def test_unhealthy_when_mcp_server_down(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(
            chat_provider=chat_provider,
            mcp_servers=[MCPServerConfig(name="srv", command=["echo"])],
        )
        session = p._get_session("srv")
        session.list_tools = AsyncMock(side_effect=ConnectionError("refused"))

        status = await p.health()
        assert status.ok is False
        assert "unreachable" in status.error


class TestMCPClose:
    @pytest.mark.anyio
    async def test_close_cleans_up_sessions(self, chat_provider: _MockChatProvider) -> None:
        p = MCPProvider(
            chat_provider=chat_provider,
            mcp_servers=[MCPServerConfig(name="srv", command=["echo"])],
        )
        session = p._get_session("srv")
        session.close = AsyncMock()

        await p.close()
        session.close.assert_awaited_once()
        assert p._sessions == {}
