"""Acces aux donnees : recherche STAC, signature SAS (Planetary Computer) et lecture fenetree des COG."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

import numpy as np

from .config import SourceConfig
from .grid import Window

log = logging.getLogger(__name__)

DEFAULT_SCALE = (1e-4, 0.0)  # (echelle, decalage) DN -> reflectance


@dataclass(frozen=True)
class ItemRef:
    """Un item Sentinel-2 L2A reduit a ce dont on a besoin (href non signes)."""

    id: str
    date: str  # YYYY-MM-DD (UTC)
    cloud_cover: float | None
    hrefs: dict[str, str]  # visual, green, swir, scl
    scales: dict[str, tuple[float, float]] = field(default_factory=dict)  # green, swir -> (scale, offset)


class Searcher(Protocol):
    def search(self, bbox: tuple[float, float, float, float], start: datetime, end: datetime) -> list[ItemRef]: ...


class Reader(Protocol):
    def read(self, href: str, window: Window, shape: tuple[int, int], *, nearest: bool = False) -> np.ndarray:
        """Lit `href` reprojete sur la grille lon/lat de `window.bbox`, forme (bandes, H, W). 0 hors donnees."""


class SasTokenCache:
    """Jeton SAS Planetary Computer, reutilise jusqu'a (presque) son expiration."""

    def __init__(self, url: str, margin_s: int = 120, fetch=None) -> None:
        self.url = url
        self.margin = margin_s
        self._fetch = fetch or self._http_fetch
        self._token: str | None = None
        self._expires = 0.0
        self._lock = threading.Lock()

    def _http_fetch(self) -> dict:
        import requests

        r = requests.get(self.url, timeout=10)
        r.raise_for_status()
        return r.json()

    def get(self) -> str:
        with self._lock:
            if self._token is None or time.time() > self._expires - self.margin:
                data = self._fetch()
                self._token = data["token"]
                exp = data.get("msft:expiry")
                try:
                    self._expires = datetime.fromisoformat(exp.replace("Z", "+00:00")).timestamp()
                except AttributeError, ValueError:
                    self._expires = time.time() + 600
            return self._token


class StacSearcher:
    def __init__(self, source: SourceConfig) -> None:
        self.source = source
        self._client = None
        self._lock = threading.Lock()

    def _get_client(self):
        with self._lock:
            if self._client is None:
                from pystac_client import Client

                self._client = Client.open(self.source.stac_url)
            return self._client

    def search(self, bbox, start: datetime, end: datetime) -> list[ItemRef]:
        s = self.source
        res = self._get_client().search(
            collections=[s.collection],
            bbox=list(bbox),
            datetime=f"{start.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}/{end.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}",
            max_items=300,
        )
        refs = []
        for it in res.items():
            ref = item_to_ref(it, s)
            if ref:
                refs.append(ref)
        return refs


def _scale_of(asset) -> tuple[float, float]:
    bands = (asset.extra_fields or {}).get("raster:bands") or []
    if bands:
        return (float(bands[0].get("scale", DEFAULT_SCALE[0])), float(bands[0].get("offset", DEFAULT_SCALE[1])))
    return DEFAULT_SCALE


def item_to_ref(item, source: SourceConfig) -> ItemRef | None:
    a = item.assets
    names = {
        "visual": source.asset_visual,
        "green": source.asset_green,
        "swir": source.asset_swir,
        "scl": source.asset_scl,
    }
    if any(n not in a for n in names.values()) or item.datetime is None:
        return None
    return ItemRef(
        id=item.id,
        date=item.datetime.astimezone(UTC).date().isoformat(),
        cloud_cover=item.properties.get("eo:cloud_cover"),
        hrefs={k: a[n].href for k, n in names.items()},
        scales={"green": _scale_of(a[source.asset_green]), "swir": _scale_of(a[source.asset_swir])},
    )


class RasterioReader:
    """Lecture par requetes Range, reprojetee sur la grille lon/lat de la fenetre (WarpedVRT)."""

    def __init__(self, source: SourceConfig, tokens: SasTokenCache | None = None) -> None:
        self.source = source
        self.tokens = tokens or (SasTokenCache(source.sas_token_url) if source.sas_token_url else None)

    def sign(self, href: str) -> str:
        if self.tokens is None:
            return href
        return f"{href}{'&' if '?' in href else '?'}{self.tokens.get()}"

    def read(self, href, window, shape, *, nearest=False):
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.transform import from_bounds
        from rasterio.vrt import WarpedVRT

        h, w = shape
        west, south, east, north = window.bbox
        transform = from_bounds(west, south, east, north, w, h)
        resampling = Resampling.nearest if nearest else Resampling.bilinear
        env = {
            "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
            "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff",
            "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
            "GDAL_HTTP_MULTIPLEX": "YES",
            "VSI_CACHE": "TRUE",
        }
        with (
            rasterio.Env(**env),
            rasterio.open(self.sign(href)) as src,
            WarpedVRT(
                src,
                crs="EPSG:4326",
                transform=transform,
                width=w,
                height=h,
                resampling=resampling,
                src_nodata=0,
                nodata=0,
            ) as vrt,
        ):
            return vrt.read()
