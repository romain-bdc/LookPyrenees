"""Validation des parametres, endpoints et service avec source/lecteur factices (aucun reseau)."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient

from scene_api.cache import IMMUTABLE, DiskCache, MemoryCache
from scene_api.config import Settings
from scene_api.main import create_app, validate_date
from scene_api.ratelimit import RateLimiter
from scene_api.service import SceneService
from scene_api.stac import ItemRef, SasTokenCache

NOW = datetime.now(UTC)


def day(n):
    return (NOW - timedelta(days=n)).date().isoformat()


class FakeSearcher:
    def __init__(self, items):
        self.items = items
        self.calls = 0

    def search(self, bbox, start, end):
        self.calls += 1
        return [i for i in self.items if start.date().isoformat() <= i.date <= end.date().isoformat()]


class FakeReader:
    """SCL: moitie nodata ; vert/swir -> neige partout ; TCI gris."""

    def __init__(self):
        self.calls = []

    def read(self, href, window, shape, *, nearest=False):
        self.calls.append(href)
        h, w = shape
        if href.endswith("scl"):
            a = np.full((1, h, w), 4, np.uint8)
            if "bad" in href:
                a[:] = 9
            a[:, :, : w // 2] = 0 if "half" in href else a[:, :, : w // 2]
            return a
        if href.endswith("green"):
            return np.full((1, h, w), 8000, np.uint16)
        if href.endswith("swir"):
            return np.full((1, h, w), 1000, np.uint16)
        return np.full((3, h, w), 120, np.uint8)


def item(id_, date, cc=5.0, tag=""):
    return ItemRef(id_, date, cc, {k: f"{tag}{id_}/{k}" for k in ("visual", "green", "swir", "scl")})


@pytest.fixture
def env():
    cache = MemoryCache()
    searcher = FakeSearcher([item("A", day(3), tag=""), item("B-bad", day(1)), item("C-high", day(5), cc=95.0)])
    reader = FakeReader()
    settings = Settings(rate_limit_per_min=0, shapefile="ressources/pyrenees.shp")
    svc = SceneService(settings, cache, searcher, reader)
    return TestClient(create_app(settings, svc)), cache, searcher, reader


def test_health(env):
    assert env[0].get("/api/health").json() == {"status": "ok"}


def test_dates_default_and_prefilter(env):
    client, cache, _, _ = env
    r = client.get("/api/dates", params={"lat": 42.78, "lon": 1.32})
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=3600"
    j = r.json()
    assert [d["item"] for d in j["dates"]] == ["B-bad", "A"]  # C-high ecartee (95 % de nuages)
    assert j["default"] == day(3)  # B-bad: 100 % de nuages dans la fenetre
    assert j["dates"][0]["cloud_pct"] == 100.0 and j["dates"][1]["snow_pct"] == 100.0
    assert j["center"] == [42.78, 1.32] and len(j["bbox"]) == 4
    assert any(k.startswith("stats/A/") for k in cache.keys())


def test_stats_are_cached(env):
    client, _, _, reader = env
    client.get("/api/dates", params={"lat": 42.78, "lon": 1.32})
    n = len(reader.calls)
    client.get("/api/dates", params={"lat": 42.79, "lon": 1.33})  # meme fenetre
    assert len(reader.calls) == n


@pytest.mark.parametrize("layer", ["color", "ndsi"])
@pytest.mark.parametrize(("fmt", "ctype"), [("webp", "image/webp"), ("png", "image/png"), ("tif", "image/tiff")])
def test_scene_ok_and_cached(env, layer, fmt, ctype):
    client, cache, _, reader = env
    p = {"lat": 42.78, "lon": 1.32, "date": day(3), "layer": layer, "format": fmt}
    r = client.get("/api/scene", params=p)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == ctype
    assert r.headers["cache-control"] == IMMUTABLE
    assert len(r.headers["x-bbox"].split(",")) == 4
    key = f"scene/v2/A/{layer}/365000_4740000.{fmt}"
    assert key in cache.keys() and cache.meta(key) == (ctype, IMMUTABLE)
    n = len(reader.calls)
    assert client.get("/api/scene", params=p).content == r.content
    assert len(reader.calls) == n  # pas de relecture des COG


def test_scene_404_no_item(env):
    client = env[0]
    r = client.get("/api/scene", params={"lat": 42.78, "lon": 1.32, "date": day(10), "layer": "color"})
    assert r.status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"lat": 48.85, "lon": 2.35},  # Paris, hors Pyrenees
        {"lat": "abc", "lon": 1.3},
        {"lat": 42.78},
        {"lat": 142.78, "lon": 1.3},
    ],
)
def test_dates_400(env, params):
    assert env[0].get("/api/dates", params=params).status_code == 400


@pytest.mark.parametrize(
    "extra",
    [
        {"date": "2026-13-45", "layer": "color"},
        {"date": "hier", "layer": "color"},
        {"date": (NOW + timedelta(days=3)).date().isoformat(), "layer": "color"},
        {"date": "2020-01-01", "layer": "color"},
        {"date": day(3), "layer": "rgb"},
        {"date": day(3), "layer": "color", "format": "gif"},
        {"layer": "color"},
    ],
)
def test_scene_400(env, extra):
    r = env[0].get("/api/scene", params={"lat": 42.78, "lon": 1.32, **extra})
    assert r.status_code == 400


def test_validate_date_ok():
    assert validate_date(day(2)) == day(2)


def test_rate_limit_429():
    settings = Settings(rate_limit_per_min=2, shapefile="ressources/pyrenees.shp")
    svc = SceneService(settings, MemoryCache(), FakeSearcher([]), FakeReader())
    client = TestClient(create_app(settings, svc))
    codes = [client.get("/api/dates", params={"lat": 42.78, "lon": 1.32}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert client.get("/api/health").status_code == 200


def test_rate_limiter_window():
    t = [0.0]
    rl = RateLimiter(2, clock=lambda: t[0])
    assert rl.check("a") is None and rl.check("a") is None
    assert rl.check("a") is not None and rl.check("b") is None
    t[0] = 61
    assert rl.check("a") is None


def test_disk_cache_roundtrip_and_traversal(tmp_path):
    c = DiskCache(tmp_path)
    assert c.get("scene/x/color/1_2.webp") is None
    c.put("scene/x/color/1_2.webp", b"abc", "image/webp")
    assert c.get("scene/x/color/1_2.webp") == b"abc"
    with pytest.raises(ValueError):
        c.get("../evil")


def test_sas_token_cached_until_expiry():
    calls = []
    now = datetime.now(UTC)

    def fetch():
        calls.append(1)
        exp = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {"token": f"sv=1&n={len(calls)}", "msft:expiry": exp}

    t = SasTokenCache("http://x", fetch=fetch)
    assert t.get() == t.get() == "sv=1&n=1" and len(calls) == 1
    t.margin = 7200  # expire "bientot"
    assert t.get() == "sv=1&n=2"


def test_dates_limit_processes_only_most_recent_items(env):
    client, cache, _, _ = env
    r = client.get("/api/dates", params={"lat": 42.78, "lon": 1.32, "limit": 1})
    j = r.json()
    assert r.status_code == 200 and j["complete"] is False
    assert [d["item"] for d in j["dates"]] == ["B-bad"]  # le plus recent seulement
    assert not any(k.startswith("stats/A/") for k in cache.keys())
    full = client.get("/api/dates", params={"lat": 42.78, "lon": 1.32}).json()
    assert full["complete"] is True and [d["item"] for d in full["dates"]] == ["B-bad", "A"]
    assert client.get("/api/dates", params={"lat": 42.78, "lon": 1.32, "limit": 0}).status_code == 400
