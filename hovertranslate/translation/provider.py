from __future__ import annotations

import asyncio
import html
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from hovertranslate.core.errors import ProviderError
from hovertranslate.translation.circuit_breaker import CircuitBreaker


ProviderName = Literal["mymemory"]
OutcomeStatus = Literal[
    "ok",
    "timeout",
    "network_down",
    "provider_error",
    "cancelled",
    "ambiguous_input",
]


@dataclass(slots=True)
class TranslationOutcome:
    result: str | None
    status: OutcomeStatus
    elapsed_ms: int


class TranslationProvider:
    """Async MyMemory provider. Close owned clients with aclose()."""

    ENDPOINT = "https://api.mymemory.translated.net/get"
    PROVIDER_NAME: ProviderName = "mymemory"

    def __init__(
        self,
        timeout_s: float = 4.0,
        circuit_breaker: CircuitBreaker | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive.")
        self._timeout_s = float(timeout_s)
        self._circuit_breaker = circuit_breaker or CircuitBreaker()
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout_s),
                headers={"User-Agent": "HoverTranslate/0.1"},
                follow_redirects=True,
            )
        return self._client

    async def aclose(self) -> None:
        if self._owns_client and self._client is not None:
            client, self._client = self._client, None
            await client.aclose()

    async def translate(
        self,
        text: str,
        lang_pair: str,
        generation: int,
    ) -> TranslationOutcome:
        started = time.perf_counter()

        if not text or not text.strip():
            return TranslationOutcome(None, "ambiguous_input", self._elapsed_ms(started))

        if not self._circuit_breaker.allow_request():
            return TranslationOutcome(None, "provider_error", self._elapsed_ms(started))

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(2),
                # Keep retry delay short; request_timeout_s is per HTTP attempt.
                wait=wait_exponential(multiplier=0.25, min=0.25, max=0.5),
                retry=retry_if_exception_type(
                    (httpx.TimeoutException, httpx.NetworkError, ProviderError)
                ),
                reraise=True,
            ):
                with attempt:
                    result = await self._translate_once(
                        text=text,
                        lang_pair=lang_pair,
                        generation=generation,
                        started=started,
                    )

            self._circuit_breaker.record_success()
            return result

        except asyncio.CancelledError:
            # Preserve cancellation semantics for callers.
            raise
        except httpx.TimeoutException:
            self._circuit_breaker.record_failure()
            return TranslationOutcome(None, "timeout", self._elapsed_ms(started))
        except httpx.NetworkError:
            self._circuit_breaker.record_failure()
            return TranslationOutcome(None, "network_down", self._elapsed_ms(started))
        except ProviderError:
            self._circuit_breaker.record_failure()
            return TranslationOutcome(None, "provider_error", self._elapsed_ms(started))
        except Exception:
            self._circuit_breaker.record_failure()
            return TranslationOutcome(None, "provider_error", self._elapsed_ms(started))

    async def _translate_once(
        self,
        text: str,
        lang_pair: str,
        generation: int,
        started: float,
    ) -> TranslationOutcome:
        if generation < 0:
            return TranslationOutcome(None, "cancelled", self._elapsed_ms(started))

        source_lang, target_lang = self._split_lang_pair(lang_pair)
        client = await self._get_client()
        response = await client.get(
            self.ENDPOINT,
            params={"q": text, "langpair": f"{source_lang}|{target_lang}"},
        )

        if response.status_code != 200:
            raise ProviderError(f"HTTP status {response.status_code}.")

        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise ProviderError("Provider returned invalid JSON.") from exc

        if payload.get("responseStatus") != 200:
            raise ProviderError(f"Provider status {payload.get('responseStatus')}.")

        response_data = payload.get("responseData") or {}
        translated_raw = response_data.get("translatedText", "")
        translated = html.unescape(str(translated_raw)).strip()
        if not translated:
            raise ProviderError("Empty provider response.")

        return TranslationOutcome(translated, "ok", self._elapsed_ms(started))

    @staticmethod
    def _split_lang_pair(lang_pair: str) -> tuple[str, str]:
        parts = lang_pair.replace("_", "-").split("-")
        if len(parts) != 2 or not all(parts):
            raise ProviderError("Invalid lang_pair format.")
        return parts[0].lower(), parts[1].lower()

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return round((time.perf_counter() - started) * 1000)
