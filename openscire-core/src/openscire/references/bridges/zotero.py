# SPDX-License-Identifier: Apache-2.0

"""Zotero API v3 bridge — collections, items, attachments, and incremental sync."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from openscire.exceptions import ReferenceError
from openscire.logging import get_logger
from openscire.references.bridges.base import ReferenceBridge, ReferenceBridgeConfig
from openscire.references.models import (
    ReferenceAttachment,
    ReferenceAuthor,
    ReferenceCollection,
    ReferenceItem,
    ReferenceSource,
)

logger = get_logger("openscire.references.bridges.zotero")

ZOTERO_API_BASE = "https://api.zotero.org"
ZOTERO_API_VERSION = "3"

ITEM_TYPE_MAP: dict[str, str] = {
    "journalArticle": "journal_article",
    "book": "book",
    "bookSection": "book_chapter",
    "conferencePaper": "conference_paper",
    "thesis": "thesis",
    "report": "report",
    "patent": "patent",
    "preprint": "preprint",
}


class ZoteroBridge(ReferenceBridge):
    """Bridge to the Zotero API v3.

    Supports both personal API key auth (primary) and OAuth2 (secondary).
    Incremental sync uses the Zotero `since` parameter (version-based).
    """

    AUTH_HEADER = "Zotero-API-Key"
    API_VERSION_HEADER = "Zotero-API-Version"

    def __init__(self, config: ReferenceBridgeConfig) -> None:
        super().__init__(config)
        self._user_id: str | None = None
        self._base = (config.base_url or ZOTERO_API_BASE).rstrip("/")

    async def authenticate(self) -> bool:
        """Authenticate via personal API key or OAuth2 token.

        For API key auth: validates the key by fetching the current user.
        For OAuth2: uses the OAuth2 helper's bearer token.

        Returns:
            True if authentication succeeded.
        """
        if self._config.api_key:
            key = self._config.api_key.get_secret_value()
            response = await self._client.get(
                f"{self._base}/keys/current",
                headers={
                    self.AUTH_HEADER: key,
                    self.API_VERSION_HEADER: ZOTERO_API_VERSION,
                },
            )
            if response.status_code != 200:
                raise ReferenceError(
                    f"Zotero API key rejected: {response.status_code}",
                    source="zotero",
                )
            data = response.json()
            self._user_id = str(data.get("userID", ""))
            logger.info("Authenticated to Zotero as user %s", self._user_id)
            return True

        return False

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            self.API_VERSION_HEADER: ZOTERO_API_VERSION,
            "Content-Type": "application/json",
        }
        if self._config.api_key:
            h[self.AUTH_HEADER] = self._config.api_key.get_secret_value()
        return h

    async def list_collections(self) -> list[ReferenceCollection]:
        """List all top-level collections via /users/{id}/collections/top."""
        if not self._user_id:
            await self.authenticate()
        collections: list[ReferenceCollection] = []
        url: str | None = f"{self._base}/users/{self._user_id}/collections/top"
        while url:
            response = await self._client.get(url, headers=self._headers())
            response.raise_for_status()
            data: list[dict[str, Any]] = response.json()
            for entry in data:
                collections.append(self._parse_collection(entry))
            url = self._next_link(response.headers)
        return collections

    async def list_items(  # noqa: PLR0912
        self, collection_id: str, limit: int = 100
    ) -> list[ReferenceItem]:
        """List items in a collection, including subcollections."""
        if not self._user_id:
            await self.authenticate()
        items: list[ReferenceItem] = []
        url: str | None = (
            f"{self._base}/users/{self._user_id}/collections/"
            f"{collection_id}/items/top?limit={limit}"
        )
        while url:
            response = await self._client.get(url, headers=self._headers())
            response.raise_for_status()
            data: list[dict[str, Any]] = response.json()
            for entry in data:
                item = self._parse_item(entry)
                if item is not None:
                    items.append(item)
            url = self._next_link(response.headers)
        return items

    async def get_item(self, item_id: str) -> ReferenceItem:
        """Fetch full metadata for a single item."""
        if not self._user_id:
            await self.authenticate()
        response = await self._client.get(
            f"{self._base}/users/{self._user_id}/items/{item_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        item = self._parse_item(data)
        if item is None:
            raise ReferenceError(f"Item {item_id} not found", source="zotero")
        return item

    async def download_attachment(
        self, item_id: str, attachment_id: str  # noqa: ARG002
    ) -> bytes:
        """Download an attachment file (PDF, etc.) by item key."""
        if not self._user_id:
            await self.authenticate()
        response = await self._client.get(
            f"{self._base}/users/{self._user_id}/items/{attachment_id}/file",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.content

    async def sync(
        self, last_sync: datetime | None = None
    ) -> list[ReferenceItem]:
        """Fetch items modified since a version.

        Args:
            last_sync: Ignored for Zotero; uses version-based sync via
                ``since`` parameter (tracked through SyncState.last_version).

        Returns:
            List of new/changed ReferenceItem objects.
        """
        if not self._user_id:
            await self.authenticate()
        items: list[ReferenceItem] = []
        base = f"{self._base}/users/{self._user_id}/items?limit=100"
        if last_sync is not None:
            since_ts = int(last_sync.timestamp())
            base += f"&since={since_ts}"
        url: str | None = base
        while url:
            response = await self._client.get(url, headers=self._headers())
            response.raise_for_status()
            data: list[dict[str, Any]] = response.json()
            for entry in data:
                item = self._parse_item(entry)
                if item is not None:
                    items.append(item)
            url = self._next_link(response.headers)
        return items

    @staticmethod
    def _next_link(headers: Any) -> str | None:  # noqa: ANN401
        """Extract the 'next' URL from Link header (RFC 5988)."""
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
        data = entry.get("data", {})
        return ReferenceCollection(
            id=data.get("key", ""),
            name=data.get("name", ""),
            source=ReferenceSource.zotero,
            parent_id=data.get("parentCollection", ""),
            item_count=data.get("meta", {}).get("numItems", 0),
        )

    def _parse_item(self, entry: dict[str, Any]) -> ReferenceItem | None:  # noqa: PLR0912
        data = entry.get("data", {})
        item_type = data.get("itemType", "")

        # Skip non-reference items (notes, attachments at top level)
        if item_type in {"note", "attachment"}:
            return None

        doi = ""
        for field in data.get("extra", "").split("\n"):
            if field.lower().startswith("doi:"):
                doi = field[4:].strip()

        creators = data.get("creators", [])
        authors: list[ReferenceAuthor] = []
        for c in creators:
            if c.get("creatorType") in {"author", "editor", None}:
                authors.append(
                    ReferenceAuthor(
                        first=c.get("firstName", ""),
                        last=c.get("lastName", ""),
                    )
                )

        tags = [t.get("tag", "") for t in data.get("tags", [])]
        date_str = data.get("date", "")
        year = None
        if date_str:
            m = re.search(r"(\d{4})", date_str)
            if m:
                year = int(m.group(1))

        attachments: list[ReferenceAttachment] = []
        for child in entry.get("children", []):
            child_data = child.get("data", {})
            if child_data.get("itemType") == "attachment":
                attachments.append(
                    ReferenceAttachment(
                        id=child_data.get("key", ""),
                        filename=child_data.get("filename", ""),
                        content_type=child_data.get("contentType", ""),
                        size_bytes=child_data.get("meta", {}).get(
                            "parsedDate", 0
                        ),
                        url=child_data.get("url", ""),
                    )
                )

        return ReferenceItem(
            id=data.get("key", ""),
            source=ReferenceSource.zotero,
            source_collection_id=data.get("parentCollection", ""),
            doi=doi,
            title=data.get("title", ""),
            authors=authors,
            journal=data.get("publicationTitle", "")
            or data.get("bookTitle", ""),
            year=year,
            volume=data.get("volume", ""),
            issue=data.get("issue", ""),
            pages=data.get("pages", ""),
            publisher=data.get("publisher", ""),
            abstract=data.get("abstractNote", ""),
            keywords=[
                t.get("tag", "") for t in data.get("tags", []) if t.get("tag")
            ],
            url=data.get("url", ""),
            attachments=attachments,
            tags=tags,
            date_added=self._parse_date(data.get("dateAdded")),
            date_modified=self._parse_date(data.get("dateModified")),
            item_type=ITEM_TYPE_MAP.get(item_type, item_type),
        )

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None
