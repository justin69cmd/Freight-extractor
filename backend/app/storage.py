"""Object storage abstraction (PDFs, table crops, generated xlsx).

Backend-agnostic: local filesystem for dev, S3/MinIO for prod. Selected by
`settings.storage_backend` so callers never branch on the backend.
"""
from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from app.config import settings


class Storage:
    """Minimal blob store. Returns a `storage_uri` that `open_path` can resolve."""

    def __init__(self) -> None:
        self.backend = settings.storage_backend
        self.root = Path(settings.storage_root)
        if self.backend == "local":
            self.root.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, data: bytes, *, suffix: str = "", prefix: str = "") -> tuple[str, str]:
        """Persist bytes. Returns (storage_uri, sha256)."""
        sha = hashlib.sha256(data).hexdigest()
        name = f"{prefix}{uuid.uuid4().hex}{suffix}"
        if self.backend == "local":
            path = self.root / name
            path.write_bytes(data)
            return f"file://{path.resolve()}", sha
        raise NotImplementedError(f"storage backend {self.backend!r} not wired yet (Phase 10)")

    def open_path(self, storage_uri: str) -> Path:
        """Resolve a storage_uri to a local Path (downloads first for S3 in Phase 10)."""
        if storage_uri.startswith("file://"):
            return Path(storage_uri[len("file://"):])
        raise NotImplementedError(f"cannot resolve {storage_uri!r} on backend {self.backend!r}")

    def save_file(self, src: Path, *, suffix: str = "") -> str:
        if self.backend == "local":
            dest = self.root / f"{uuid.uuid4().hex}{suffix}"
            shutil.copy2(src, dest)
            return f"file://{dest.resolve()}"
        raise NotImplementedError


storage = Storage()
