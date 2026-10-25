from __future__ import annotations

import asyncio

import httpx
import pytest

from hovertranslate.translation.provider import TranslationProvider


@pytest.mark.asyncio
async def test_translate_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "مرحبا"
        assert request.url.params["langpair"] == "ar|ru"

        return httpx.Response(
            200,
            json={
                "responseStatus": 200,
                "responseData": {
                    "translatedText": "Привет",
                },
            },
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        provider = TranslationProvider(client=client)
        outcome = await provider.translate(
            text="مرحبا",
            lang_pair="ar-ru",
            generation=1,
        )

    assert outcome.status == "ok"
    assert outcome.result == "Привет"


@pytest.mark.asyncio
async def test_translate_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        provider = TranslationProvider(
            timeout_s=0.1,
            client=client,
        )
        outcome = await provider.translate(
            text="مرحبا",
            lang_pair="ar-ru",
            generation=1,
        )

    assert outcome.status == "timeout"
    assert outcome.result is None