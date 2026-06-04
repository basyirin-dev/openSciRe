import pytest
from openscire.bridge.adapter import BridgeAdapter
from openscire.bridge.rate_limiter import TokenBucketRateLimiter


class TestBridgeAdapter:
    @pytest.mark.asyncio
    async def test_abc_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BridgeAdapter()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_concrete_implementation(self) -> None:
        impl = _ConcreteBridge()
        assert isinstance(impl, BridgeAdapter)
        assert impl.requires_auth is False

    @pytest.mark.asyncio
    async def test_search(self) -> None:
        impl = _ConcreteBridge()
        results = await impl.search("test query")
        assert results == ["result_a", "result_b"]

    @pytest.mark.asyncio
    async def test_get(self) -> None:
        impl = _ConcreteBridge()
        result = await impl.get("test_id")
        assert result == {"id": "test_id"}

    @pytest.mark.asyncio
    async def test_metadata(self) -> None:
        impl = _ConcreteBridge()
        meta = await impl.metadata()
        assert meta["name"] == "ConcreteBridge"
        assert meta["version"] == "1.0.0"


class _ConcreteBridge(BridgeAdapter):
    async def search(self, query: str, **kwargs: object) -> list:  # noqa: ARG002
        return ["result_a", "result_b"]

    async def get(self, identifier: str, **kwargs: object) -> dict:  # noqa: ARG002
        return {"id": identifier}

    async def metadata(self) -> dict:
        return {"name": "ConcreteBridge", "version": "1.0.0"}

    def rate_limit(self) -> TokenBucketRateLimiter:
        return TokenBucketRateLimiter(rate=10.0, burst=5)
