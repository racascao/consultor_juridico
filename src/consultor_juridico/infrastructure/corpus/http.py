"""Aquisição HTTP oficial com validadores condicionais."""

import httpx

from consultor_juridico.application.corpus.ports import AcquisitionResponse


class HttpxSourceAcquirer:
    def __init__(self, client: httpx.Client, *, user_agent: str) -> None:
        self._client = client
        self._user_agent = user_agent

    def acquire(
        self, url: str, *, etag: str | None, last_modified: str | None
    ) -> AcquisitionResponse:
        headers = {"Accept-Encoding": "identity", "User-Agent": self._user_agent}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        response = self._client.get(url, headers=headers, follow_redirects=True)
        if response.status_code == 304:
            return AcquisitionResponse(
                304,
                None,
                response.headers.get("content-type"),
                response.headers.get("etag"),
                response.headers.get("last-modified"),
            )
        response.raise_for_status()
        content_type = response.headers.get("content-type")
        if content_type and "text/html" not in content_type.lower():
            raise ValueError(f"Content-Type inesperado: {content_type}")
        return AcquisitionResponse(
            response.status_code,
            response.content,
            content_type,
            response.headers.get("etag"),
            response.headers.get("last-modified"),
        )
