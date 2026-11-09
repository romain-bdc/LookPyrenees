"""Lecture reelle d'un petit COG local synthetique via RasterioReader (sans reseau) ; test reseau optionnel."""

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from scene_api.config import EARTH_SEARCH, PLANETARY
from scene_api.grid import window_for
from scene_api.stac import ItemRef, RasterioReader, StacSearcher, item_to_ref


def write_tif(path, window, value, bands=1, dtype="uint16"):
    # raster UTM 31N plus grand que la fenetre (10 km de marge), pixels de 100 m ; moitie ouest = nodata
    x0, y0 = window.cx - 15000, window.cy + 15000
    arr = np.full((bands, 300, 300), value, dtype)
    arr[:, :, :60] = 0
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=300,
        height=300,
        count=bands,
        dtype=dtype,
        crs="EPSG:32631",
        transform=from_origin(x0, y0, 100, 100),
        tiled=True,
        blockxsize=256,
        blockysize=256,
    ) as dst:
        dst.write(arr)


def test_reader_reprojects_to_window_grid(tmp_path):
    w = window_for(42.78, 1.32)
    p = tmp_path / "b03.tif"
    write_tif(p, w, 5000)
    r = RasterioReader(EARTH_SEARCH)  # pas de signature SAS
    out = r.read(str(p), w, (200, 199))
    assert out.shape == (1, 200, 199) and out.dtype == np.uint16
    assert (out == 5000).mean() > 0.85  # seul le bord ouest (nodata) manque
    assert (out[0, :, :5] == 0).all() and (out[0, :, -5:] == 5000).all()


def test_reader_nodata_outside_raster(tmp_path):
    w = window_for(42.78, 1.32)
    p = tmp_path / "far.tif"
    write_tif(p, w, 5000)
    far = window_for(42.78, 1.32 + 0.5)
    out = RasterioReader(EARTH_SEARCH).read(str(p), far, (50, 50))
    assert (out == 0).all()


def test_sign_appends_token():
    class T:
        def get(self):
            return "sv=abc"

    r = RasterioReader(PLANETARY, tokens=T())
    assert r.sign("https://x/y.tif") == "https://x/y.tif?sv=abc"
    assert r.sign("https://x/y.tif?a=1") == "https://x/y.tif?a=1&sv=abc"


def test_item_to_ref_asset_names():
    class A:
        def __init__(self, h, rb=None):
            self.href, self.extra_fields = h, ({"raster:bands": rb} if rb else {})

    class It:
        id = "S2X"
        from datetime import datetime, timezone

        datetime = datetime(2026, 10, 28, 10, 30, tzinfo=timezone.utc)
        properties = {"eo:cloud_cover": 12.0}
        assets = {"visual": A("v"), "B03": A("g", [{"scale": 0.0001, "offset": -0.1}]), "B11": A("s"), "SCL": A("c")}

    ref = item_to_ref(It, PLANETARY)
    assert ref.date == "2026-10-28" and ref.hrefs["scl"] == "c" and ref.scales["green"] == (0.0001, -0.1)
    assert item_to_ref(It, EARTH_SEARCH) is None  # noms d'assets differents


@pytest.mark.network
def test_live_planetary_search():
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    items = StacSearcher(PLANETARY).search((1.2, 42.7, 1.5, 42.9), now - timedelta(days=30), now)
    assert items and isinstance(items[0], ItemRef)
