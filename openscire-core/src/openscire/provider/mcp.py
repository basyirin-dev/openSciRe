# SPDX-License-Identifier: Apache-2.0

"""MCP (Model Context Protocol) integration for openSciRe.

The ``MCPProvider`` wraps a ``ModelProvider`` (the *chat provider*) and
enriches it with tool-calling capabilities from one or more MCP servers.
MCP tools are auto-discovered, merged into the ``tools`` list passed to the
chat provider, and routed for execution when the model requests them.
"""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from openscire.constants import ErrorCode
from openscire.exceptions import ModelProviderError
from openscire.provider.base import HealthStatus, ModelProvider, ProviderConfig
from openscire.provider.models import (
    ChatMessage,
    Chunk,
    ModelCard,
    ModelInfo,
)

_MCP_IMPORT_ERROR: str | None = None

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp import types as mcp_types
    from mcp.client.stdio import stdio_client as mcp_stdio_client

    _HAS_MCP = True
except ImportError as exc:
    _HAS_MCP = False
    _MCP_IMPORT_ERROR = str(exc)


_MCP_TOOL_PREFIX_SEPARATOR = "__"


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server connection.

    Attributes:
        name: User-assigned label for this server. Used as a prefix on tool
            names to avoid collisions between servers (``{name}__{tool}``).
        command: Shell command to spawn the server process (stdio transport).
            Example: ``["npx", "-y", "@modelcontextprotocol/server-filesystem"]``.
        env: Extra environment variables to pass to the subprocess.
        enabled: Whether to connect to this server on startup.
    """

    name: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


def _ensure_mcp_sdk() -> None:
    if not _HAS_MCP:
        raise ImportError(
            "The MCP Python SDK is required to use MCPProvider. "
            "Install it with: pip install 'openscire-core[mcp]'"
            f" (underlying error: {_MCP_IMPORT_ERROR})"
        )


def _mcp_tool_to_openai_schema(
    server_name: str,
    tool: mcp_types.Tool,
) -> dict[str, Any]:
    """Convert an MCP ``Tool`` to an OpenAI-compatible tool schema.

    The tool name is prefixed with ``{server_name}__`` to avoid collisions.
    """
    return {
        "type": "function",
        "function": {
            "name": f"{server_name}{_MCP_TOOL_PREFIX_SEPARATOR}{tool.name}",
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


def _split_prefixed_name(full_name: str) -> tuple[str, str]:
    """Split ``{server_name}__{tool_name}`` into ``(server_name, tool_name)``."""
    sep = _MCP_TOOL_PREFIX_SEPARATOR
    if sep in full_name:
        server, _, tool = full_name.partition(sep)
        return server, tool
    return "", full_name


def _extract_text_from_result(result: mcp_types.CallToolResult) -> str:
    """Extract text content from an MCP ``CallToolResult``."""
    parts: list[str] = []
    for item in result.content:
        if isinstance(item, mcp_types.TextContent):
            parts.append(item.text)
    return "\n".join(parts)


class _MCPSession:
    """Manages a single MCP server connection with lazy initialisation."""

    def __init__(self, config: MCPServerConfig) -> None:
        self._config = config
        self._session: ClientSession | None = None
        self._exit_stack = contextlib.AsyncExitStack()

    async def _ensure_connected(self) -> ClientSession:
        if self._session is not None:
            return self._session

        server_params = StdioServerParameters(
            command=self._config.command[0],
            args=self._config.command[1:],
            env={**os.environ, **self._config.env} if self._config.env else None,
        )
        streams = await self._exit_stack.enter_async_context(mcp_stdio_client(server_params))
        read, write = streams
        session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._session = session
        return session

    async def list_tools(self) -> list[mcp_types.Tool]:
        session = await self._ensure_connected()
        result = await session.list_tools()
        return list(result.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        session = await self._ensure_connected()
        result = await session.call_tool(name, arguments)
        if result.isError:
            raise ModelProviderError(
                message=f"MCP tool '{name}' returned an error: {_extract_text_from_result(result)}",
                source="provider.mcp",
                error_code=ErrorCode.MODEL_UNSUPPORTED_CAPABILITY,
            )
        return _extract_text_from_result(result)

    async def list_resources(self) -> list[mcp_types.Resource]:
        session = await self._ensure_connected()
        result = await session.list_resources()
        return list(result.resources)

    async def read_resource(self, uri: str) -> str:
        session = await self._ensure_connected()
        contents = await session.read_resource(uri)  # type: ignore[arg-type]
        parts: list[str] = []
        for content in contents.contents:
            if hasattr(content, "text"):
                parts.append(content.text)
        return "\n".join(parts)

    async def close(self) -> None:
        await self._exit_stack.aclose()
        self._session = None


class MCPProvider(ModelProvider):
    """``ModelProvider`` that wraps a chat provider and injects MCP tool support.

    Tool calls returned by the underlying model are routed to the appropriate
    MCP server for execution.

    Args:
        chat_provider: The underlying ``ModelProvider`` for chat completions.
        mcp_servers: List of MCP server configurations.
        config: Optional base ``ProviderConfig`` for the MCP layer itself.
    """

    PROVIDER_NAME = "mcp"

    def __init__(
        self,
        chat_provider: ModelProvider,
        mcp_servers: list[MCPServerConfig] | None = None,
        config: ProviderConfig | None = None,
    ) -> None:
        _ensure_mcp_sdk()
        super().__init__(config)
        self._chat_provider = chat_provider
        self._mcp_servers = [s for s in (mcp_servers or []) if s.enabled]
        self._sessions: dict[str, _MCPSession] = {}
        self._tool_cache: list[dict[str, Any]] | None = None

    async def _do_stream_chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        provenance_parent_id: str | None = None,
    ) -> AsyncIterator[Chunk]:
        """Stream a chat completion with MCP tools auto-injected."""
        mcp_tools = await self._get_mcp_tool_schemas()
        all_tools: list[dict[str, Any]] = []
        if tools:
            all_tools.extend(tools)
        all_tools.extend(mcp_tools)

        async for chunk in self._chat_provider.stream_chat(
            messages,
            tools=all_tools or None,
            temperature=temperature,
            max_tokens=max_tokens,
            provenance_parent_id=provenance_parent_id,
        ):
            yield chunk

    async def list_models(self) -> list[ModelInfo]:
        return await self._chat_provider.list_models()

    def supports_tool_use(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return self._chat_provider.supports_vision()

    def supports_streaming(self) -> bool:
        return self._chat_provider.supports_streaming()

    async def get_token_count(self, text: str) -> int:
        return await self._chat_provider.get_token_count(text)

    async def get_context_window(self) -> int:
        return await self._chat_provider.get_context_window()

    async def get_model_card(self) -> ModelCard:
        card = await self._chat_provider.get_model_card()
        card.limitations.append("MCP tools are third-party code; verify tool outputs before use")
        return card

    async def health(self) -> HealthStatus:
        start = time.monotonic()
        chat_ok = False
        try:
            chat_status = await self._chat_provider.health()
            chat_ok = chat_status.ok
        except Exception:
            pass

        for config in self._mcp_servers:
            try:
                session = self._get_session(config.name)
                await session.list_tools()
            except Exception:
                elapsed = (time.monotonic() - start) * 1000
                return HealthStatus(
                    ok=False,
                    latency_ms=elapsed,
                    error=f"MCP server '{config.name}' unreachable",
                )

        if not chat_ok:
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(
                ok=False,
                latency_ms=elapsed,
                error="Underlying chat provider unhealthy",
            )

        elapsed = (time.monotonic() - start) * 1000
        return HealthStatus(ok=True, latency_ms=elapsed)

    async def list_mcp_tools(self) -> list[dict[str, Any]]:
        """Discover tools from all configured MCP servers.

        Returns a list of OpenAI-compatible tool schemas with prefixed names.
        Results are cached per session to avoid redundant server queries.
        """
        return await self._get_mcp_tool_schemas()

    async def execute_mcp_tool(
        self,
        full_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """Execute an MCP tool by its prefixed ``{server}__{tool}`` name.

        Returns the text result string.
        """
        server_name, tool_name = _split_prefixed_name(full_name)
        session = self._get_session(server_name)
        return await session.call_tool(tool_name, arguments)

    async def list_mcp_resources(self) -> list[dict[str, Any]]:
        """List resources available from all configured MCP servers."""
        result: list[dict[str, Any]] = []
        for config in self._mcp_servers:
            session = self._get_session(config.name)
            try:
                resources = await session.list_resources()
            except Exception:
                continue
            for resource in resources:
                result.append(
                    {
                        "server": config.name,
                        "uri": str(resource.uri),
                        "name": resource.name or "",
                        "description": resource.description or "",
                        "mimeType": resource.mimeType or "",
                    }
                )
        return result

    async def read_mcp_resource(self, uri: str) -> str:
        """Read a resource from an MCP server by URI."""
        for config in self._mcp_servers:
            s = self._get_session(config.name)
            try:
                resources = await s.list_resources()
                if any(str(r.uri) == uri for r in resources):
                    return await s.read_resource(uri)
            except Exception:
                continue
        raise ModelProviderError(
            message=f"Resource '{uri}' not found on any MCP server",
            source="provider.mcp",
            error_code=ErrorCode.MODEL_UNSUPPORTED_CAPABILITY,
        )

    async def close(self) -> None:
        """Close all MCP server connections."""
        for session in self._sessions.values():
            await session.close()
        self._sessions.clear()
        self._tool_cache = None

    async def _get_mcp_tool_schemas(self) -> list[dict[str, Any]]:
        if self._tool_cache is not None:
            return self._tool_cache

        schemas: list[dict[str, Any]] = []
        for config in self._mcp_servers:
            session = self._get_session(config.name)
            try:
                tools = await session.list_tools()
            except Exception:
                continue
            for tool in tools:
                schemas.append(_mcp_tool_to_openai_schema(config.name, tool))

        self._tool_cache = schemas
        return schemas

    def _get_session(self, server_name: str) -> _MCPSession:
        if server_name not in self._sessions:
            configs = [c for c in self._mcp_servers if c.name == server_name]
            if not configs:
                raise ModelProviderError(
                    message=f"MCP server '{server_name}' not configured",
                    source="provider.mcp",
                    error_code=ErrorCode.MODEL_CONNECTION_FAILURE,
                )
            self._sessions[server_name] = _MCPSession(configs[0])
        return self._sessions[server_name]
