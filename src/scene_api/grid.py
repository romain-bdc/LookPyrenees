"""Geometrie : bbox des Pyrenees, arrondi sur grille 5 km (UTM 31N) et fenetre de 20 km."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from functools import lru_cache
from math import cos, radians
from pathlib import Path

from pyproj import Transformer

UTM = "EPSG:32631"
GRID_M = 5000
HALF_M = 10000  # fenetre 20 km x 20 km
FULL_PX = 2000  # hauteur de la lecture pleine resolution (10 m)
STATS_PX = 200  # hauteur de la lecture reduite (100 m) pour /api/dates

# Emprise de ressources/pyrenees.shp (lon/lat), utilisee si le fichier est absent (image Docker).
FALLBACK_BBOX = (-1.9227540678328479, 42.138252531503774, 3.0986884473893737, 43.42893682185037)

_to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
_to_wgs = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)


def shapefile_bbox(path: str | Path) -> tuple[float, float, float, float]:
    """Lit l'emprise (minlon, minlat, maxlon, maxlat) dans l'en-tete d'un .shp ; FALLBACK_BBOX si illisible."""
    try:
        with open(path, "rb") as f:
            header = f.read(100)
        xmin, ymin, xmax, ymax = struct.unpack("<4d", header[36:68])
    except OSError, struct.error:
        return FALLBACK_BBOX
    return (xmin, ymin, xmax, ymax)


@lru_cache(maxsize=4)
def pyrenees_bbox(path: str, margin: float) -> tuple[float, float, float, float]:
    xmin, ymin, xmax, ymax = shapefile_bbox(path)
    return (xmin - margin, ymin - margin, xmax + margin, ymax + margin)


def in_bbox(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> bool:
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def snap(value: float, step: int = GRID_M) -> int:
    """Arrondi au multiple de `step` le plus proche (metres)."""
    return int(round(value / step)) * step


@dataclass(frozen=True)
class Window:
    cx: int  # centre arrondi, metres UTM 31N
    cy: int
    bbox: tuple[float, float, float, float]  # lon/lat (minlon, minlat, maxlon, maxlat)

    @property
    def key(self) -> str:
        return f"{self.cx}_{self.cy}"

    @property
    def center_lonlat(self) -> tuple[float, float]:
        lon, lat = _to_wgs.transform(self.cx, self.cy)
        return (lat, lon)

    def shape(self, height: int = FULL_PX) -> tuple[int, int]:
        """(hauteur, largeur) en pixels d'une image alignee lon/lat couvrant la bbox, a pixels ~carres."""
        minlon, minlat, maxlon, maxlat = self.bbox
        ratio = (maxlon - minlon) * cos(radians((minlat + maxlat) / 2)) / (maxlat - minlat)
        return (height, max(1, round(height * ratio)))

    @property
    def bbox_header(self) -> str:
        return ",".join(f"{v:.6f}" for v in self.bbox)


def window_for(lat: float, lon: float) -> Window:
    """Fenetre de 20 km centree sur le point arrondi a la grille de 5 km.

    La bbox renvoyee est l'emprise lon/lat du carre UTM ; l'image est produite alignee sur cette bbox
    (reprojection a la lecture) pour que ImageOverlay la superpose sans decalage.
    """
    x, y = _to_utm.transform(lon, lat)
    cx, cy = snap(x), snap(y)
    minlon, minlat, maxlon, maxlat = _to_wgs.transform_bounds(
        cx - HALF_M, cy - HALF_M, cx + HALF_M, cy + HALF_M, densify_pts=21
    )
    return Window(cx, cy, (minlon, minlat, maxlon, maxlat))
