"""Accept-Language detection middleware."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_SUPPORTED = {"en", "ar"}
_DEFAULT = "en"


class LanguageMiddleware(BaseHTTPMiddleware):
    """Parse ``Accept-Language`` and expose ``request.state.language``.

    Only ``en`` and ``ar`` are supported.  The resolved language is echoed
    back via the ``Content-Language`` response header.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        accept = request.headers.get("Accept-Language", "")
        language = _parse_preferred(accept)
        request.state.language = language

        response = await call_next(request)
        response.headers["Content-Language"] = language
        return response


def _parse_preferred(header: str) -> str:
    """Return the best supported language from an Accept-Language header."""
    for part in header.split(","):
        tag = part.split(";")[0].strip().lower()
        # Match full tag or primary subtag (e.g. "ar-SA" → "ar")
        if tag in _SUPPORTED:
            return tag
        primary = tag.split("-")[0]
        if primary in _SUPPORTED:
            return primary
    return _DEFAULT
