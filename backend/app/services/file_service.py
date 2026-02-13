"""Centralized file storage service — local disk (swappable to S3)."""

from __future__ import annotations

import os
from pathlib import Path

from backend.app.core.config import settings


class FileStorageService:
    """Store and retrieve files on the configured storage backend."""

    def __init__(self) -> None:
        self._root = Path(settings.FILE_STORAGE_PATH)
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, relative_path: str, data: bytes) -> str:
        """Persist *data* under *relative_path* and return the full path."""
        dest = self._root / relative_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    def read(self, relative_path: str) -> bytes:
        """Return the raw bytes for the given *relative_path*."""
        return (self._root / relative_path).read_bytes()

    def exists(self, relative_path: str) -> bool:
        return (self._root / relative_path).exists()

    def delete(self, relative_path: str) -> None:
        path = self._root / relative_path
        if path.exists():
            os.remove(path)

    def url(self, relative_path: str) -> str:
        """Return a download URL (or local path for the local backend)."""
        if settings.FILE_STORAGE_BACKEND == "local":
            return f"/files/{relative_path}"
        # Placeholder for S3 presigned URLs
        return f"/files/{relative_path}"
