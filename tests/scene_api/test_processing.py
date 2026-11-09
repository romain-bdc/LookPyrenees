import numpy as np
import pytest

from scene_api import processing as p


def test_ndsi_values_and_zero_denominator():
    g = np.array([[0.8, 0.0, 0.2]], dtype=np.float32)
    s = np.array([[0.2, 0.0, 0.8]], dtype=np.float32)
    nd = p.ndsi(g, s)
    assert nd[0, 0] == pytest.approx(0.6)
    assert np.isnan(nd[0, 1])
    assert nd[0, 2] == pytest.approx(-0.6)


def test_snow_mask_excludes_clouds_shadow_and_nodata():
    scl = np.array([[4, 3, 8, 9, 10, 0, 11]], dtype=np.uint8)
    nd = np.full(scl.shape, 0.9, dtype=np.float32)
    assert p.snow_mask(nd, scl).tolist() == [[True, False, False, False, False, False, True]]


def test_snow_mask_threshold_and_nan():
    scl = np.full((1, 3), 4, dtype=np.uint8)
    nd = np.array([[0.39, 0.41, np.nan]], dtype=np.float32)
    assert p.snow_mask(nd, scl).tolist() == [[False, True, False]]


def test_stats_on_valid_pixels_only():
    # 10 pixels : 5 nodata, 5 valides dont 1 nuage, 2 neige, 2 sol sans neige
    scl = np.array([0] * 5 + [9, 4, 4, 5, 5], dtype=np.uint8)
    g = np.array([0] * 5 + [0.9, 0.9, 0.9, 0.2, 0.2], dtype=np.float32)
    s = np.array([0] * 5 + [0.1, 0.1, 0.1, 0.2, 0.2], dtype=np.float32)
    st = p.compute_stats(scl, g, s)
    assert st == {"cloud_pct": 20.0, "snow_pct": 40.0, "data_pct": 50.0}


def test_stats_all_nodata():
    z = np.zeros((4, 4), dtype=np.uint8)
    assert p.compute_stats(z, z.astype(np.float32), z.astype(np.float32))["data_pct"] == 0.0


def test_render_ndsi_transparent_outside_snow():
    scl = np.array([[4, 4, 9]], dtype=np.uint8)
    nd = np.array([[0.1, 1.0, 1.0]], dtype=np.float32)
    img = p.render_ndsi(nd, scl)
    assert img.shape == (1, 3, 4)
    assert img[..., 3].tolist() == [[0, 255, 0]]


def test_render_color_alpha_from_nodata():
    rgb = np.zeros((3, 1, 2), dtype=np.uint8)
    rgb[:, 0, 1] = (10, 20, 30)
    img = p.render_color(rgb)
    assert img[0, 0].tolist() == [0, 0, 0, 0]
    assert img[0, 1].tolist() == [10, 20, 30, 255]


def test_resize_and_encode_roundtrip():
    rgba = np.full((2000, 1800, 4), 255, dtype=np.uint8)
    small = p.resize_max(rgba)
    assert small.shape[:2] == (1600, 1440)
    data, ctype = p.encode(small[:50, :50].copy(), "webp")
    assert ctype == "image/webp" and data[:4] == b"RIFF"
    data, ctype = p.encode(small[:50, :50].copy(), "png")
    assert ctype == "image/png" and data[:4] == b"\x89PNG"


def e(date, cloud, data, item="x"):
    return {"date": date, "item": item, "cloud_pct": cloud, "snow_pct": 0, "data_pct": data}


def test_default_most_recent_under_threshold_and_covered():
    entries = [e("2026-10-28", 40, 99), e("2026-10-25", 5, 30), e("2026-10-20", 10, 90), e("2026-10-10", 1, 99)]
    assert p.choose_default(entries) == "2026-10-20"


def test_default_fallback_least_cloudy_with_enough_data():
    entries = [e("2026-10-28", 60, 99), e("2026-10-25", 30, 99), e("2026-10-20", 5, 20)]
    assert p.choose_default(entries) == "2026-10-25"


def test_default_fallback_when_no_coverage_and_empty():
    assert p.choose_default([e("2026-10-28", 60, 10), e("2026-10-25", 30, 20)]) == "2026-10-25"
    assert p.choose_default([]) is None


def test_dedupe_keeps_best_coverage_per_date_sorted_desc():
    out = p.dedupe_by_date([e("2026-10-20", 1, 40, "a"), e("2026-10-28", 1, 50), e("2026-10-20", 1, 80, "b")])
    assert [(x["date"], x["item"]) for x in out] == [("2026-10-28", "x"), ("2026-10-20", "b")]


def test_snow_mask_ignores_dark_pixels_with_noisy_ndsi():
    # B11 ramene a 0 sur un pixel sombre : NDSI = 1 sans etre de la neige
    green = np.array([0.02, 0.5], dtype="f4")
    swir = np.array([0.0, 0.05], dtype="f4")
    scl = np.array([4, 4], dtype="u1")
    nd = p.ndsi(green, swir)
    assert p.snow_mask(nd, scl).tolist() == [True, True]
    assert p.snow_mask(nd, scl, green=green).tolist() == [False, True]
