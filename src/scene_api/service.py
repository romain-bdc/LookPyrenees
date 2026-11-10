"""Orchestration : recherche, statistiques par item/fenetre, rendu des couches, avec cache."""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import numpy as np

from . import processing as proc
from .cache import IMMUTABLE, CacheBackend, scene_key, stats_key
from .config import Settings
from .grid import FULL_PX, STATS_PX, Window, window_for
from .stac import ItemRef, Reader, Searcher

log = logging.getLogger(__name__)


class NoSceneError(Exception):
    """Aucune scene exploitable pour la fenetre / la date demandee."""


def reflectance(dn: np.ndarray, scale_offset: tuple[float, float]) -> np.ndarray:
    scale, offset = scale_offset
    out = dn.astype(np.float32) * scale + offset
    return np.where(dn == 0, 0.0, np.clip(out, 0.0, None)).astype(np.float32)


class SceneService:
    def __init__(self, settings: Settings, cache: CacheBackend, searcher: Searcher, reader: Reader) -> None:
        self.s = settings
        self.cache = cache
        self.searcher = searcher
        self.reader = reader
        self._pool = ThreadPoolExecutor(max_workers=settings.max_workers)

    # -- lecture des bandes ------------------------------------------------------------------
    def _bands(self, item: ItemRef, window: Window, height: int):
        shape = window.shape(height)
        scl = self.reader.read(item.hrefs["scl"], window, shape, nearest=True)[0]
        with ThreadPoolExecutor(max_workers=2) as ex:
            fg = ex.submit(self.reader.read, item.hrefs["green"], window, shape)
            fs = ex.submit(self.reader.read, item.hrefs["swir"], window, shape)
            g, s = fg.result()[0], fs.result()[0]
        scales = {"green": (1e-4, 0.0), "swir": (1e-4, 0.0), **item.scales}
        return scl, reflectance(g, scales["green"]), reflectance(s, scales["swir"])

    # -- statistiques ------------------------------------------------------------------------
    def item_stats(self, item: ItemRef, window: Window) -> dict:
        key = stats_key(item.id, window.key)
        raw = self.cache.get(key)
        if raw is not None:
            return json.loads(raw)
        scl, g, s = self._bands(item, window, STATS_PX)
        stats = proc.compute_stats(scl, g, s, self.s.ndsi_threshold)
        self.cache.put(key, json.dumps(stats).encode(), "application/json")
        return stats

    def _entries(self, items: list[ItemRef], window: Window) -> list[dict]:
        def one(it: ItemRef):
            try:
                return {"date": it.date, "item": it.id, **self.item_stats(it, window)}
            except Exception:
                log.exception("stats impossibles pour %s", it.id)
                return None

        entries = [e for e in self._pool.map(one, items) if e and e["data_pct"] > 0]
        return proc.dedupe_by_date(entries)

    def _search(self, window: Window, start: datetime, end: datetime) -> list[ItemRef]:
        items = self.searcher.search(window.bbox, start, end)
        return [i for i in items if i.cloud_cover is None or i.cloud_cover <= self.s.prefilter_cloud]

    # -- API ---------------------------------------------------------------------------------
    def dates(self, lat: float, lon: float, now: datetime | None = None, limit: int | None = None) -> dict:
        """`limit` : ne traite que les `limit` items les plus recents (reponse rapide ; `complete` vaut alors False
        s'il en reste). Les stats sont mises en cache par item, un appel complet ensuite ne les recalcule pas."""
        now = now or datetime.now(UTC)
        window = window_for(lat, lon)
        items = sorted(
            self._search(window, now - timedelta(days=self.s.lookback_days), now), key=lambda i: i.date, reverse=True
        )
        complete = limit is None or len(items) <= limit
        entries = self._entries(items if complete else items[:limit], window)
        return {
            "complete": complete,
            "center": [lat, lon],
            "bbox": list(window.bbox),
            "default": proc.choose_default(entries, self.s.cloud_threshold, self.s.min_data_pct),
            "dates": entries,
        }

    def scene(self, lat: float, lon: float, date: str, layer: str, fmt: str = "webp") -> tuple[bytes, str, Window]:
        window = window_for(lat, lon)
        day = datetime.fromisoformat(date).replace(tzinfo=UTC)
        items = self._search(window, day, day + timedelta(days=1) - timedelta(seconds=1))
        items = [i for i in items if i.date == date]
        entries = self._entries(items, window)
        if not entries:
            raise NoSceneError(f"aucune scene le {date}")
        item = next(i for i in items if i.id == entries[0]["item"])

        key = scene_key(item.id, layer, window.key, fmt)
        ctype = {"png": "image/png", "tif": "image/tiff"}.get(fmt, "image/webp")
        cached = self.cache.get(key)
        if cached is not None:
            return cached, ctype, window
        data, ctype = self.render(item, window, layer, fmt)
        self.cache.put(key, data, ctype, IMMUTABLE)
        return data, ctype, window

    def render(self, item: ItemRef, window: Window, layer: str, fmt: str) -> tuple[bytes, str]:
        if layer == "color":
            rgba = proc.render_color(self.reader.read(item.hrefs["visual"], window, window.shape(FULL_PX)))
        else:
            scl, g, s = self._bands(item, window, FULL_PX)
            rgba = proc.render_ndsi(proc.ndsi(g, s), scl, self.s.ndsi_threshold, g)
        return proc.encode(proc.resize_max(rgba), fmt, window.bbox)
