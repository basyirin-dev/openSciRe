# SPDX-License-Identifier: Apache-2.0

"""Abstract base class for external reference manager bridges."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import httpx
from pydantic import BaseModel, Field, SecretStr

from openscire.references.models import ReferenceCollection, ReferenceItem


class ReferenceBridgeConfig(BaseModel):
    """Configuration for a single reference manager bridge connection.

    Attributes:
        client_id: OAuth2 client identifier.
        client_secret: OAuth2 client secret (encrypted at rest).
        api_key: Personal API key (Zotero primary auth path).
        base_url: Base URL for the API (default per bridge).
        timeout: HTTP request timeout in seconds.
        max_retries: Maximum retries for transient failures.
    """

    client_id: str = ""
    client_secret: SecretStr | None = None
    api_key: SecretStr | None = None
    base_url: str = ""
    timeout: int = Field(default=30, gt=0)
    max_retries: int = Field(default=3, ge=0)


class ReferenceBridge(ABC):
    """Async bridge to an external reference manager (Zotero, Mendeley, etc.).

    Subclasses implement authentication, collection/item retrieval, attachment
    download, and incremental sync for a specific reference manager API.
    """

    AUTH_HEADER: str = ""
    API_VERSION_HEADER: str = ""

    def __init__(self, config: ReferenceBridgeConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout),
            follow_redirects=True,
        )

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the reference manager.

        For API-key-based auth, validates the key with a test request.
        For OAuth2, completes the authorization code flow.

        Returns:
            True if authentication succeeded.
        """
        ...

    @abstractmethod
    async def list_collections(self) -> list[ReferenceCollection]:
        """List all top-level collections/folders.

        Returns:
            Flat list of ReferenceCollection objects.
        """
        ...

    @abstractmethod
    async def list_items(
        self, collection_id: str, limit: int = 100
    ) -> list[ReferenceItem]:
        """List reference items in a collection.

        Args:
            collection_id: Collection/folder identifier.
            limit: Maximum items to return.

        Returns:
            List of ReferenceItem objects.
        """
        ...

    @abstractmethod
    async def get_item(self, item_id: str) -> ReferenceItem:
        """Fetch full metadata for a single item.

        Args:
            item_id: Source-specific item identifier.

        Returns:
            ReferenceItem with full metadata.
        """
        ...

    @abstractmethod
    async def download_attachment(
        self, item_id: str, attachment_id: str
    ) -> bytes:
        """Download an attachment file (usually a PDF).

        Args:
            item_id: Parent item identifier.
            attachment_id: Attachment/file identifier.

        Returns:
            Raw bytes of the attachment.
        """
        ...

    @abstractmethod
    async def sync(
        self, last_sync: datetime | None = None
    ) -> list[ReferenceItem]:
        """Fetch items changed since last sync.

        Args:
            last_sync: Timestamp of last successful sync. If None, fetches all items.

        Returns:
            List of new/changed ReferenceItem objects.
        """
        ...

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
