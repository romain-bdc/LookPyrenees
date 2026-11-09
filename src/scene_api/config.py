"""Configuration par variables d'environnement et description des sources STAC."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceConfig:
    """Differences entre fournisseurs STAC (url, noms d'assets, signature des href)."""

    name: str
    stac_url: str
    collection: str
    asset_visual: str
    asset_green: str
    asset_swir: str
    asset_scl: str
    sas_token_url: str | None = None


PLANETARY = SourceConfig(
    name="planetary",
    stac_url="https://planetarycomputer.microsoft.com/api/stac/v1",
    collection="sentinel-2-l2a",
    asset_visual="visual",
    asset_green="B03",
    asset_swir="B11",
    asset_scl="SCL",
    sas_token_url="https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a",
)

EARTH_SEARCH = SourceConfig(
    name="earth-search",
    stac_url="https://earth-search.aws.element84.com/v1",
    collection="sentinel-2-l2a",
    asset_visual="visual",
    asset_green="green",
    asset_swir="swir16",
    asset_scl="scl",
)

SOURCES = {"planetary": PLANETARY, "earth-search": EARTH_SEARCH}


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    source: SourceConfig = PLANETARY
    scene_bucket: str | None = None  # SCENE_BUCKET ; vide = cache disque local
    cache_dir: str = "/tmp/scene-cache"  # SCENE_CACHE_DIR (si pas de bucket)
    lookback_days: int = 60
    prefilter_cloud: float = 90.0  # on ecarte les scenes au-dela, sans lire un pixel
    cloud_threshold: float = 20.0
    min_data_pct: float = 50.0
    ndsi_threshold: float = 0.4
    max_workers: int = 8
    rate_limit_per_min: int = 60  # 0 = desactive
    shapefile: str = field(default="ressources/pyrenees.shp")
    bbox_margin_deg: float = 0.05
    dates_max_age: int = 3600

    @classmethod
    def from_env(cls) -> Settings:
        src = os.environ.get("STAC_SOURCE", "planetary")
        if src not in SOURCES:
            raise ValueError(f"STAC_SOURCE inconnu: {src!r} (attendu: {', '.join(SOURCES)})")
        return cls(
            source=SOURCES[src],
            scene_bucket=os.environ.get("SCENE_BUCKET") or None,
            cache_dir=os.environ.get("SCENE_CACHE_DIR", "/tmp/scene-cache"),
            lookback_days=_env_int("LOOKBACK_DAYS", 60),
            prefilter_cloud=_env_float("PREFILTER_CLOUD", 90.0),
            cloud_threshold=_env_float("CLOUD_THRESHOLD", 20.0),
            min_data_pct=_env_float("MIN_DATA_PCT", 50.0),
            ndsi_threshold=_env_float("NDSI_THRESHOLD", 0.4),
            max_workers=_env_int("MAX_WORKERS", 8),
            rate_limit_per_min=_env_int("RATE_LIMIT_PER_MIN", 60),
            shapefile=os.environ.get("PYRENEES_SHP", "ressources/pyrenees.shp"),
            bbox_margin_deg=_env_float("BBOX_MARGIN_DEG", 0.05),
            dates_max_age=_env_int("DATES_MAX_AGE", 3600),
        )
