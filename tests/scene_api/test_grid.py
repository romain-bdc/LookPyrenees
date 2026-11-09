import pytest

from scene_api import grid


@pytest.mark.parametrize(
    ("v", "expected"),
    [(0, 0), (2499, 0), (2500, 0), (2501, 5000), (-2501, -5000), (367300, 365000), (4742600, 4745000)],
)
def test_snap(v, expected):
    assert grid.snap(v) == expected


def test_nearby_points_share_window():
    a = grid.window_for(42.78, 1.32)
    b = grid.window_for(42.785, 1.325)
    assert a == b and a.key == "365000_4740000"


def test_point_stays_in_window_with_margin():
    lat, lon = 42.7, 1.33
    w = grid.window_for(lat, lon)
    minlon, minlat, maxlon, maxlat = w.bbox
    assert minlon < lon < maxlon and minlat < lat < maxlat
    # marge >= 7,5 km au nord/sud (1 deg lat ~ 111 km)
    assert (lat - minlat) * 111 >= 7.4 and (maxlat - lat) * 111 >= 7.4


def test_window_size_about_20km():
    w = grid.window_for(42.78, 1.32)
    assert (w.bbox[3] - w.bbox[1]) * 111.2 == pytest.approx(
        20, rel=0.05
    )  # emprise englobante du carre UTM (leger angle)
    h, wd = w.shape()
    assert h == 2000 and 1900 < wd < 2100


def test_bbox_header_format():
    assert len(grid.window_for(42.78, 1.32).bbox_header.split(",")) == 4


def test_shapefile_bbox_from_repo_and_fallback(tmp_path):
    assert grid.shapefile_bbox("ressources/pyrenees.shp") == pytest.approx(grid.FALLBACK_BBOX)
    assert grid.shapefile_bbox(tmp_path / "absent.shp") == grid.FALLBACK_BBOX


def test_in_bbox_margin():
    bb = grid.pyrenees_bbox("ressources/pyrenees.shp", 0.05)
    assert grid.in_bbox(42.8, 0.7, bb)
    assert not grid.in_bbox(48.85, 2.35, bb)  # Paris
