from __future__ import annotations

import asyncio
from typing import Any

import httpx


class PalworldApiError(Exception):
    """Base class for public Palworld API client errors."""


class PalworldAuthError(PalworldApiError):
    """Raised when the Palworld API rejects authentication."""


class PalworldUnavailableError(PalworldApiError):
    """Raised when the Palworld API cannot be reached."""


class PalworldResponseError(PalworldApiError):
    """Raised when the Palworld API returns an unusable response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self._status_code = status_code

    @property
    def status_code(self) -> int | None:
        return self._status_code


class PalworldApiClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        normalized_base_url = base_url.rstrip("/")
        if httpx.URL(normalized_base_url).scheme not in ("http", "https"):
            raise ValueError("base_url must use HTTP or HTTPS")

        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=f"{normalized_base_url}/",
            auth=httpx.BasicAuth(username, password),
            timeout=timeout,
            transport=transport,
        )

    async def get_info(self) -> dict[str, Any]:
        return await self._get_object("info")

    async def get_players(self) -> list[dict[str, Any]]:
        payload, status_code = await self._get_json("players")
        if not isinstance(payload, dict):
            raise PalworldResponseError(
                "Palworld API returned an invalid response", status_code=status_code
            )

        players = payload.get("players")
        if not isinstance(players, list) or not all(
            isinstance(player, dict) for player in players
        ):
            raise PalworldResponseError(
                "Palworld API returned invalid players", status_code=status_code
            )
        return players

    async def get_settings(self) -> dict[str, Any]:
        return await self._get_object("settings")

    async def get_metrics(self) -> dict[str, Any]:
        return await self._get_object("metrics")

    async def shutdown(self, waittime: int, message: str) -> None:
        await self._post_status(
            "shutdown",
            {"waittime": waittime, "message": message},
        )

    async def close(self) -> None:
        if not self._client.is_closed:
            await self._client.aclose()

    async def _post_status(self, endpoint: str, payload: dict[str, Any]) -> None:
        try:
            response = await asyncio.wait_for(
                self._client.post(endpoint, json=payload), timeout=self._timeout
            )
        except (httpx.RequestError, asyncio.TimeoutError):
            raise PalworldUnavailableError("Palworld API is unavailable") from None

        if response.status_code == 401:
            raise PalworldAuthError("Palworld API authentication failed")
        if not response.is_success:
            raise PalworldResponseError(
                f"Palworld API returned HTTP {response.status_code}",
                status_code=response.status_code,
            )

    async def _get_object(self, endpoint: str) -> dict[str, Any]:
        payload, status_code = await self._get_json(endpoint)
        if not isinstance(payload, dict):
            raise PalworldResponseError(
                "Palworld API returned an invalid response", status_code=status_code
            )
        return payload

    async def _get_json(self, endpoint: str) -> tuple[Any, int]:
        try:
            response = await asyncio.wait_for(
                self._client.get(endpoint), timeout=self._timeout
            )
        except (httpx.RequestError, asyncio.TimeoutError):
            raise PalworldUnavailableError("Palworld API is unavailable") from None

        if response.status_code == 401:
            raise PalworldAuthError("Palworld API authentication failed")
        if not response.is_success:
            raise PalworldResponseError(
                f"Palworld API returned HTTP {response.status_code}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError:
            raise PalworldResponseError(
                "Palworld API returned invalid JSON", status_code=response.status_code
            ) from None
        return payload, response.status_code
