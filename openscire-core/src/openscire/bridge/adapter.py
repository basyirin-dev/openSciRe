# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from openscire.bridge.rate_limiter import TokenBucketRateLimiter


class BridgeAdapter(ABC):
    requires_auth: bool = False

    @abstractmethod
    async def search(self, query: str, **kwargs: Any) -> list[Any]:  # noqa: ANN401
        ...

    @abstractmethod
    async def get(self, identifier: str, **kwargs: Any) -> Any:  # noqa: ANN401
        ...

    @abstractmethod
    async def metadata(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def rate_limit(self) -> TokenBucketRateLimiter:
        ...
