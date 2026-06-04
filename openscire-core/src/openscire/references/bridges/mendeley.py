# SPDX-License-Identifier: Apache-2.0

"""Mendeley API v1 bridge — folders, documents, files, and incremental sync."""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any

from openscire.exceptions import ReferenceError
from openscire.logging import get_logger
from openscire.references.bridges._oauth import OAuth2Config, OAuth2Helper
from openscire.references.bridges.base import ReferenceBridge, ReferenceBridgeConfig
from openscire.references.models import (
    ReferenceAttachment,
    ReferenceAuthor,
    ReferenceCollection,
    ReferenceItem,
    ReferenceSource,
)

logger = get_logger("openscire.references.bridges.mendeley")

MENDELEY_API_BASE = "https://api.mendeley.com"
MENDELEY_AUTHORIZE_URL = "https://api.mendeley.com/oauth/authorize"
MENDELEY_TOKEN_URL = "https://api.mendeley.com/oauth/token"


class MendeleyBridge(ReferenceBridge):
    """Bridge to the Mendeley API v1.

    Authentication is OAuth2-only (client credentials + authorization code flow).
    Incremental sync uses the ``modified_since`` parameter.
    """

    AUTH_HEADER = "Authorization"

    def __init__(self, config: ReferenceBridgeConfig) -> None:
        super().__init__(config)
        self._base = (config.base_url or MENDELEY_API_BASE).rstrip("/")
        self._oauth: OAuth2Helper | None = None

    async def authenticate(self) -> bool:
        """Authenticate via OAuth2.

        Requires ``client_id`` and ``client_secret`` in the bridge config.
        Delegates to the shared OAuth2 helper for the authorization code flow.

        Returns:
            True if authentication succeeded.
        """
        if not self._config.client_id or not self._config.client_secret:
            raise ReferenceError(
                "Mendeley requires OAuth2 credentials (client_id + client_secret)",
                source="mendeley",
            )

        oauth_config = OAuth2Config(
            client_id=self._config.client_id,
            client_secret=self._config.client_secret.get_secret_value(),
            authorize_url=MENDELEY_AUTHORIZE_URL,
            token_url=MENDELEY_TOKEN_URL,
            scopes=["all"],
        )
        self._oauth = OAuth2Helper(
            config=oauth_config,
            bridge_id="mendeley",
            http_client=self._client,
        )
        return await self._oauth.authenticate()

    async def _ensure_auth(self) -> str:
        """Return a valid Bearer token, authenticating first if needed."""
        if self._oauth is None:
            await self.authenticate()
        if self._oauth is None:
            raise ReferenceError("Mendeley authentication failed", source="mendeley")
        return await self._oauth.get_access_token()

    def _headers(self, token: str) -> dict[str, str]:
        return {
            self.AUTH_HEADER: f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def list_collections(self) -> list[ReferenceCollection]:
        """List all folders (Mendeley calls them 'folders')."""
        token = await self._ensure_auth()
        collections: list[ReferenceCollection] = []
        url: str | None = f"{self._base}/folders"
        while url:
            response = await self._client.get(url, headers=self._headers(token))
            response.raise_for_status()
            data: list[dict[str, Any]] = response.json()
            for entry in data:
                collections.append(self._parse_collection(entry))
            url = self._next_link(response.headers)
        return collections

    async def list_items(
        self, collection_id: str, limit: int = 100
    ) -> list[ReferenceItem]:
        """List documents in a folder."""
        token = await self._ensure_auth()
        items: list[ReferenceItem] = []
        url: str | None = (
            f"{self._base}/folders/{collection_id}/documents?limit={limit}"
        )
        while url:
            response = await self._client.get(url, headers=self._headers(token))
            response.raise_for_status()
            data: list[dict[str, Any]] = response.json()
            for entry in data:
                item = await self._enrich_item(entry, token)
                if item is not None:
                    items.append(item)
            url = self._next_link(response.headers)
        return items

    async def get_item(self, item_id: str) -> ReferenceItem:
        """Fetch full metadata for a single document."""
        token = await self._ensure_auth()
        response = await self._client.get(
            f"{self._base}/documents/{item_id}",
            headers=self._headers(token),
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        item = self._parse_item(data)
        if item is None:
            raise ReferenceError(
                f"Document {item_id} not found", source="mendeley"
            )
        return item

    async def _enrich_item(
        self, entry: dict[str, Any], token: str
    ) -> ReferenceItem | None:
        """Fetch full document details (Mendeley list returns only partial data)."""
        item_id = entry.get("id", "")
        if not item_id:
            return None
        response = await self._client.get(
            f"{self._base}/documents/{item_id}",
            headers=self._headers(token),
        )
        if response.status_code != 200:
            logger.warning("Failed to fetch document %s: %s", item_id, response.status_code)
            return self._parse_item(entry)
        data: dict[str, Any] = response.json()
        return self._parse_item(data)

    async def download_attachment(
        self, item_id: str, attachment_id: str  # noqa: ARG002
    ) -> bytes:
        """Download a file by file ID."""
        token = await self._ensure_auth()
        response = await self._client.get(
            f"{self._base}/files/{attachment_id}",
            headers=self._headers(token),
        )
        response.raise_for_status()
        return response.content

    async def sync(
        self, last_sync: datetime | None = None
    ) -> list[ReferenceItem]:
        """Fetch documents modified since a timestamp.

        Args:
            last_sync: ISO-8601 timestamp. If None, fetches all documents.

        Returns:
            List of new/changed ReferenceItem objects.
        """
        token = await self._ensure_auth()
        items: list[ReferenceItem] = []
        base = f"{self._base}/documents?limit=100"
        if last_sync is not None:
            modified = last_sync.strftime("%Y-%m-%dT%H:%M:%SZ")
            base += f"&modified_since={modified}"
        url: str | None = base
        while url:
            response = await self._client.get(url, headers=self._headers(token))
            response.raise_for_status()
            data: list[dict[str, Any]] = response.json()
            for entry in data:
                item = await self._enrich_item(entry, token)
                if item is not None:
                    items.append(item)
            url = self._next_link(response.headers)
        return items

    @staticmethod
    def _next_link(headers: Any) -> str | None:  # noqa: ANN401
        """Extract the next URL from Mendeley's Link header."""
        link_str = headers.get("Link", "")
        if not link_str:
            return None
        for part in link_str.split(","):
            part = part.strip()
            if 'rel="next"' in part:
                start = part.index("<") + 1
                end = part.index(">")
                return part[start:end]  # type: ignore[no-any-return]
        return None

    @staticmethod
    def _parse_collection(entry: dict[str, Any]) -> ReferenceCollection:
        return ReferenceCollection(
            id=entry.get("id", ""),
            name=entry.get("name", ""),
            source=ReferenceSource.mendeley,
            parent_id=entry.get("parent_id", ""),
            item_count=entry.get("document_count", 0),
        )

    @staticmethod
    def _parse_item(entry: dict[str, Any]) -> ReferenceItem | None:  # noqa: PLR0912
        item_id = entry.get("id", "")
        if not item_id:
            return None

        authors: list[ReferenceAuthor] = []
        for c in entry.get("authors", []):
            first = c.get("first_name", "") or c.get("given", "")
            last = c.get("last_name", "") or c.get("family", "")
            authors.append(ReferenceAuthor(first=first, last=last))

        year = None
        year_str = entry.get("year", "")
        if year_str:
            with contextlib.suppress(ValueError, TypeError):
                year = int(year_str)

        identifiers = entry.get("identifiers", {})
        doi = identifiers.get("doi", "")

        files: list[ReferenceAttachment] = []
        for f in entry.get("files", []):
            files.append(
                ReferenceAttachment(
                    id=f.get("id", ""),
                    filename=f.get("name", ""),
                    content_type=f.get("mime_type", ""),
                    size_bytes=f.get("size_bytes", 0),
                    url=f.get("download_url", ""),
                )
            )

        tags = [t.strip() for t in entry.get("tags", [])]
        keywords = entry.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]

        return ReferenceItem(
            id=item_id,
            source=ReferenceSource.mendeley,
            doi=doi,
            title=entry.get("title", ""),
            authors=authors,
            journal=entry.get("journal", "")
            or entry.get("container-title", ""),
            year=year,
            volume=entry.get("volume", ""),
            issue=entry.get("issue", ""),
            pages=entry.get("pages", ""),
            publisher=entry.get("publisher", ""),
            abstract=entry.get("abstract", ""),
            keywords=keywords,
            url=entry.get("url", ""),
            attachments=files,
            tags=tags,
            date_added=MendeleyBridge._parse_date(entry.get("created")),
            date_modified=MendeleyBridge._parse_date(entry.get("modified")),
            item_type=entry.get("type", ""),
        )

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
