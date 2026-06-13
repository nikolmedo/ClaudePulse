"""HTTP client for the Claude.ai usage API.

Infrastructure layer — depends only on aiohttp, never on Home Assistant.
The caller injects the aiohttp session, so this client works the same in
HA, in tests, or in a standalone script.
"""
from __future__ import annotations

import logging

import aiohttp

from .const import (
    CLAUDE_BASE_URL,
    CLAUDE_HEADERS,
    ENDPOINT_ACCOUNT_USAGE,
    ENDPOINT_ORG_USAGE,
    ENDPOINT_USAGE,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=12)


class ClaudeApiError(Exception):
    """Base error: the usage data could not be fetched."""


class ClaudeAuthError(ClaudeApiError):
    """The session key was rejected (HTTP 401/403)."""


class ClaudeApiClient:
    """Thin async client for the (undocumented) claude.ai usage endpoints."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        session_key: str,
        org_id: str = "",
    ) -> None:
        self._session = session
        self._session_key = session_key
        self._org_id = org_id

    @property
    def _headers(self) -> dict:
        return {**CLAUDE_HEADERS, "Cookie": f"sessionKey={self._session_key}"}

    def _endpoints(self) -> list[str]:
        """Candidate endpoints in fallback order. First HTTP 200 wins."""
        endpoints: list[str] = []
        if self._org_id:
            endpoints.append(
                CLAUDE_BASE_URL + ENDPOINT_ORG_USAGE.format(org_id=self._org_id)
            )
        endpoints.append(CLAUDE_BASE_URL + ENDPOINT_USAGE)
        endpoints.append(CLAUDE_BASE_URL + ENDPOINT_ACCOUNT_USAGE)
        return endpoints

    async def async_get_usage(self) -> dict:
        """Fetch the raw usage payload.

        Raises:
            ClaudeAuthError: On HTTP 401/403 from any endpoint.
            ClaudeApiError: When every endpoint fails.
        """
        last_error = ""
        for url in self._endpoints():
            try:
                async with self._session.get(
                    url, headers=self._headers, timeout=REQUEST_TIMEOUT
                ) as resp:
                    if resp.status in (401, 403):
                        raise ClaudeAuthError(
                            f"Claude.ai authentication failed (HTTP {resp.status})."
                        )
                    if resp.status == 200:
                        return await resp.json(content_type=None)
                    last_error = f"HTTP {resp.status} from {url}"
            except ClaudeAuthError:
                raise
            except Exception as err:  # noqa: BLE001
                last_error = str(err)
                _LOGGER.debug("Endpoint %s failed: %s", url, err)

        raise ClaudeApiError(
            f"All Claude.ai endpoints failed. Last error: {last_error}"
        )

    async def async_validate(self) -> None:
        """Verify credentials with a single live request.

        Raises ClaudeAuthError or ClaudeApiError on failure.
        """
        url = self._endpoints()[0]
        try:
            async with self._session.get(
                url, headers=self._headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status in (401, 403):
                    raise ClaudeAuthError(
                        f"Claude.ai authentication failed (HTTP {resp.status})."
                    )
                if resp.status != 200:
                    raise ClaudeApiError(f"HTTP {resp.status} from {url}")
        except (ClaudeAuthError, ClaudeApiError):
            raise
        except Exception as err:  # noqa: BLE001
            raise ClaudeApiError(str(err)) from err
