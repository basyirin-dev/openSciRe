import tempfile

import pytest
from openscire.bridge.cache import CacheLayer, CacheTTL


class TestCacheLayer:
    @pytest.fixture
    def cache(self) -> CacheLayer:
        tmp = tempfile.mktemp(suffix=".db")
        return CacheLayer(db_path=tmp)

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache: CacheLayer) -> None:
        key = "test:key:1"
        value = {"doi": "10.1234/abc", "title": "Test Paper"}
        await cache.set(key, value, ttl=60)
        result = await cache.get(key)
        assert result == value

    @pytest.mark.asyncio
    async def test_ttl_expiry(self, cache: CacheLayer) -> None:
        key = "test:key:2"
        await cache.set(key, "expiring", ttl=0)
        result = await cache.get(key)
        assert result is None

    @pytest.mark.asyncio
    async def test_miss(self, cache: CacheLayer) -> None:
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_clear(self, cache: CacheLayer) -> None:
        await cache.set("k1", "v1")
        await cache.set("k2", "v2")
        await cache.clear()
        assert await cache.get("k1") is None
        assert await cache.get("k2") is None

    @pytest.mark.asyncio
    async def test_type_preservation(self, cache: CacheLayer) -> None:
        data = {"list": [1, 2, 3], "nested": {"a": 1}, "bool": True, "num": 42}
        await cache.set("type_test", data)
        result = await cache.get("type_test")
        assert result == data

    @pytest.mark.asyncio
    async def test_cache_ttl_model_defaults(self) -> None:
        ttl = CacheTTL()
        assert ttl.search == 300
        assert ttl.get == 3600
        assert ttl.metadata == 86400
