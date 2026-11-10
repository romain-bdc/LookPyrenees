"""Traitements purs (numpy) : NDSI, masques SCL, statistiques, rendu et choix de la date par defaut."""

from __future__ import annotations

import io
from collections.abc import Sequence

import numpy as np
from PIL import Image
from rasterio.enums import ColorInterp

CLOUD_CLASSES = (3, 8, 9, 10)  # ombre de nuage, nuage moyen/fort probabilite, cirrus
NDSI_THRESHOLD = 0.4
MIN_GREEN_REFLECTANCE = 0.1  # critere usuel : ecarte les pixels sombres (ombre) ou le NDSI est du bruit
MAX_DISPLAY_PX = 2000  # = resolution native (10 m sur 20 km) : plus de reduction


def ndsi(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """(B03 - B11) / (B03 + B11) ; NaN la ou la somme est nulle."""
    g = green.astype(np.float32)
    s = swir.astype(np.float32)
    den = g + s
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (g - s) / den
    out[den == 0] = np.nan
    return out


def valid_mask(scl: np.ndarray) -> np.ndarray:
    return scl != 0


def cloud_mask(scl: np.ndarray) -> np.ndarray:
    return np.isin(scl, CLOUD_CLASSES)


def snow_mask(
    nd: np.ndarray, scl: np.ndarray, threshold: float = NDSI_THRESHOLD, green: np.ndarray | None = None
) -> np.ndarray:
    """Neige = NDSI > seuil, hors nuage/ombre et hors nodata ; si `green` (reflectance B03) est fourni,
    on exige aussi B03 > MIN_GREEN_REFLECTANCE."""
    with np.errstate(invalid="ignore"):
        mask = (nd > threshold) & ~cloud_mask(scl) & valid_mask(scl)
    if green is not None:
        mask &= green > MIN_GREEN_REFLECTANCE
    return mask


def compute_stats(
    scl: np.ndarray, green: np.ndarray, swir: np.ndarray, threshold: float = NDSI_THRESHOLD
) -> dict[str, float]:
    """data_pct sur toute la fenetre ; cloud_pct et snow_pct sur les pixels valides uniquement."""
    valid = valid_mask(scl)
    n_total = scl.size
    n_valid = int(valid.sum())
    if n_total == 0 or n_valid == 0:
        return {"cloud_pct": 0.0, "snow_pct": 0.0, "data_pct": 0.0}
    cloud = int(cloud_mask(scl).sum())  # SCL 0 n'est pas dans CLOUD_CLASSES
    snow = int(snow_mask(ndsi(green, swir), scl, threshold, green).sum())
    return {
        "cloud_pct": round(100 * cloud / n_valid, 1),
        "snow_pct": round(100 * snow / n_valid, 1),
        "data_pct": round(100 * n_valid / n_total, 1),
    }


def render_color(rgb: np.ndarray) -> np.ndarray:
    """(3, H, W) uint8 -> (H, W, 4) RGBA ; transparent la ou les 3 bandes valent 0 (hors fauchee)."""
    img = np.moveaxis(rgb, 0, -1).astype(np.uint8)
    alpha = np.where(img.any(axis=-1), 255, 0).astype(np.uint8)
    return np.dstack([img, alpha])


def render_ndsi(
    nd: np.ndarray, scl: np.ndarray, threshold: float = NDSI_THRESHOLD, green: np.ndarray | None = None
) -> np.ndarray:
    """RGBA : transparent hors neige, degrade bleu clair -> bleu fonce de `threshold` a 1."""
    snow = snow_mask(nd, scl, threshold, green)
    t = np.clip((np.nan_to_num(nd, nan=0.0) - threshold) / (1 - threshold), 0, 1)
    low = np.array([170, 215, 255], dtype=np.float32)
    high = np.array([8, 48, 160], dtype=np.float32)
    rgb = low + (high - low) * t[..., None]
    alpha = np.where(snow, 255, 0).astype(np.uint8)
    return np.dstack([rgb.astype(np.uint8), alpha])


def resize_max(rgba: np.ndarray, max_px: int = MAX_DISPLAY_PX) -> np.ndarray:
    h, w = rgba.shape[:2]
    if max(h, w) <= max_px:
        return rgba
    k = max_px / max(h, w)
    im = Image.fromarray(rgba, "RGBA").resize((max(1, round(w * k)), max(1, round(h * k))), Image.Resampling.BILINEAR)
    return np.asarray(im)


def encode_geotiff(rgba: np.ndarray, bbox: tuple[float, float, float, float]) -> tuple[bytes, str]:
    """GeoTIFF RGBA 8 bits sans perte (EPSG:4326, emprise `bbox`), utilisable tel quel dans QGIS."""
    from rasterio.io import MemoryFile
    from rasterio.transform import from_bounds

    h, w = rgba.shape[:2]
    with MemoryFile() as mem:
        with mem.open(
            driver="GTiff", width=w, height=h, count=4, dtype="uint8", crs="EPSG:4326",
            transform=from_bounds(*bbox, w, h), compress="deflate", predictor=2, tiled=True,
        ) as dst:
            dst.write(np.moveaxis(rgba, -1, 0))
            dst.colorinterp = [ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha]
        return mem.read(), "image/tiff"


def encode(rgba: np.ndarray, fmt: str = "webp", bbox: tuple[float, float, float, float] | None = None) -> tuple[bytes, str]:
    if fmt == "tif":
        return encode_geotiff(rgba, bbox)
    buf = io.BytesIO()
    im = Image.fromarray(rgba, "RGBA")
    if fmt == "png":
        im.save(buf, "PNG", optimize=True)
        return buf.getvalue(), "image/png"
    im.save(buf, "WEBP", quality=92, method=4)
    return buf.getvalue(), "image/webp"


def dedupe_by_date(entries: Sequence[dict]) -> list[dict]:
    """Une entree par date (la plus grande data_pct), triees de la plus recente a la plus ancienne."""
    best: dict[str, dict] = {}
    for e in entries:
        cur = best.get(e["date"])
        if cur is None or e["data_pct"] > cur["data_pct"]:
            best[e["date"]] = e
    return [best[d] for d in sorted(best, reverse=True)]


def choose_default(entries: Sequence[dict], cloud_threshold: float = 20.0, min_data_pct: float = 50.0) -> str | None:
    """Date la plus recente avec cloud_pct < seuil et data_pct >= min ; sinon la moins nuageuse (data_pct
    suffisant en priorite) ; None si la liste est vide. `entries` doit etre triee du plus recent au plus ancien."""
    for e in entries:
        if e["cloud_pct"] < cloud_threshold and e["data_pct"] >= min_data_pct:
            return e["date"]
    covered = [e for e in entries if e["data_pct"] >= min_data_pct] or list(entries)
    if not covered:
        return None
    return min(covered, key=lambda e: (e["cloud_pct"], -e["data_pct"]))["date"]
