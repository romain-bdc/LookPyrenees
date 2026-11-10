"""Backends de cache d'objets (GCS en production, memoire/disque pour les tests et le dev)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Protocol

IMMUTABLE = "public, max-age=31536000, immutable"


class CacheBackend(Protocol):
    def get(self, key: str) -> bytes | None: ...

    def put(self, key: str, data: bytes, content_type: str, cache_control: str | None = None) -> None: ...


RENDER_VERSION = "v2"  # a incrementer quand le rendu change (v2 : pleine resolution, WebP q92, GeoTIFF)


def scene_key(item_id: str, layer: str, window_key: str, fmt: str = "webp") -> str:
    return f"scene/{RENDER_VERSION}/{item_id}/{layer}/{window_key}.{fmt}"


def stats_key(item_id: str, window_key: str) -> str:
    return f"stats/{item_id}/{window_key}.json"


class MemoryCache:
    def __init__(self) -> None:
        self._d: dict[str, tuple[bytes, str, str | None]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> bytes | None:
        with self._lock:
            v = self._d.get(key)
        return v[0] if v else None

    def put(self, key: str, data: bytes, content_type: str, cache_control: str | None = None) -> None:
        with self._lock:
            self._d[key] = (data, content_type, cache_control)

    def meta(self, key: str) -> tuple[str, str | None] | None:
        v = self._d.get(key)
        return (v[1], v[2]) if v else None

    def keys(self) -> list[str]:
        return sorted(self._d)


class DiskCache:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError(f"cle invalide: {key!r}")
        return p

    def get(self, key: str) -> bytes | None:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            return None

    def put(self, key: str, data: bytes, content_type: str, cache_control: str | None = None) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + f".{threading.get_ident()}.tmp")
        tmp.write_bytes(data)
        tmp.replace(p)


class GCSCache:
    """Bucket GCS (lecture publique, ecriture par le compte de service Cloud Run)."""

    def __init__(self, bucket_name: str, client=None) -> None:
        if client is None:
            from google.cloud import storage

            client = storage.Client()
        self._bucket = client.bucket(bucket_name)

    def get(self, key: str) -> bytes | None:
        from google.api_core.exceptions import NotFound

        try:
            return self._bucket.blob(key).download_as_bytes()
        except NotFound:
            return None

    def put(self, key: str, data: bytes, content_type: str, cache_control: str | None = None) -> None:
        blob = self._bucket.blob(key)
        if cache_control:
            blob.cache_control = cache_control
        blob.upload_from_string(data, content_type=content_type)
