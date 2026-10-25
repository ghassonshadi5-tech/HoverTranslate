from __future__ import annotations

from pathlib import Path

from hovertranslate.cache.cache_service import CacheService


def test_cache_put_get(tmp_path: Path) -> None:
    with CacheService(db_path=tmp_path / "cache.db") as cache:
        cache.put(
            text="مرحبا",
            direction="ar-ru",
            provider="mymemory",
            lang_pair="ar-ru",
            result="Привет",
        )

        result = cache.get(
            text="مرحبا",
            direction="ar-ru",
            provider="mymemory",
            lang_pair="ar-ru",
        )

        assert result == "Привет"


def test_cache_miss_for_different_provider(tmp_path: Path) -> None:
    with CacheService(db_path=tmp_path / "cache.db") as cache:
        cache.put(
            text="مرحبا",
            direction="ar-ru",
            provider="mymemory",
            lang_pair="ar-ru",
            result="Привет",
        )

        result = cache.get(
            text="مرحبا",
            direction="ar-ru",
            provider="other",
            lang_pair="ar-ru",
        )

        assert result is None


def test_cache_expiry(tmp_path: Path) -> None:
    with CacheService(
        db_path=tmp_path / "cache.db",
        ttl_seconds=-1,
    ) as cache:
        cache.put(
            text="كتاب",
            direction="ar-ru",
            provider="mymemory",
            lang_pair="ar-ru",
            result="Книга",
        )

        result = cache.get(
            text="كتاب",
            direction="ar-ru",
            provider="mymemory",
            lang_pair="ar-ru",
        )

        assert result is None