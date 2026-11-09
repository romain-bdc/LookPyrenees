"""Application ASGI : `uvicorn scene_api.main:app`."""

from __future__ import annotations

import logging
import math
import re
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from .cache import CacheBackend, DiskCache, GCSCache
from .config import Settings
from .grid import in_bbox, pyrenees_bbox
from .ratelimit import RateLimiter
from .service import NoSceneError, SceneService
from .stac import RasterioReader, StacSearcher

log = logging.getLogger(__name__)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_point(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> None:
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise HTTPException(400, "lat/lon invalides")
    if not in_bbox(lat, lon, bbox):
        raise HTTPException(400, "Lieu hors des Pyrenees")


def validate_date(date: str, lookback_days: int = 60, today: datetime | None = None) -> str:
    """YYYY-MM-DD, pas dans le futur, pas plus ancien que la fenetre de recherche (+ marge)."""
    today = (today or datetime.now(UTC)).date()
    try:
        if not _DATE_RE.match(date):
            raise ValueError
        d = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "date invalide (YYYY-MM-DD attendu)") from None
    if d > today:
        raise HTTPException(400, "date dans le futur")
    if d < today - timedelta(days=lookback_days + 5):
        raise HTTPException(400, f"date trop ancienne (max {lookback_days} jours)")
    return date


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def make_cache(settings: Settings) -> CacheBackend:
    return GCSCache(settings.scene_bucket) if settings.scene_bucket else DiskCache(settings.cache_dir)


def create_app(settings: Settings | None = None, service: SceneService | None = None) -> FastAPI:
    """`service` injectable pour les tests ; sinon construit paresseusement depuis l'environnement."""
    settings = settings or Settings.from_env()
    app = FastAPI(title="scene-api", docs_url=None, redoc_url=None)
    bbox = pyrenees_bbox(settings.shapefile, settings.bbox_margin_deg)
    limiter = RateLimiter(settings.rate_limit_per_min)
    holder = {"svc": service}

    def svc() -> SceneService:
        if holder["svc"] is None:
            reader = RasterioReader(settings.source)
            holder["svc"] = SceneService(settings, make_cache(settings), StacSearcher(settings.source), reader)
        return holder["svc"]

    def rate_limit(request: Request) -> None:
        wait = limiter.check(client_ip(request))
        if wait is not None:
            raise HTTPException(429, "Trop de requetes", headers={"Retry-After": str(int(wait) + 1)})

    @app.exception_handler(RequestValidationError)
    async def _bad_request(_: Request, exc: RequestValidationError):
        return JSONResponse({"detail": "parametre invalide", "errors": [e["loc"][-1] for e in exc.errors()]}, 400)

    @app.get("/api/health")  # pas /healthz : chemin reserve par le frontal de Cloud Run
    def health():
        return {"status": "ok"}

    @app.get("/api/dates")
    def dates(
        request: Request,
        lat: float = Query(),
        lon: float = Query(),
        limit: int | None = Query(None, ge=1, le=100),
    ):
        validate_point(lat, lon, bbox)
        rate_limit(request)
        out = svc().dates(lat, lon, limit=limit)
        return JSONResponse(out, headers={"Cache-Control": f"public, max-age={settings.dates_max_age}"})

    @app.get("/api/scene")
    def scene(
        request: Request,
        lat: float = Query(),
        lon: float = Query(),
        date: str = Query(),
        layer: Literal["color", "ndsi"] = Query(),
        format: Literal["webp", "png"] = Query("webp"),
    ):
        validate_point(lat, lon, bbox)
        validate_date(date, settings.lookback_days)
        rate_limit(request)
        try:
            data, ctype, window = svc().scene(lat, lon, date, layer, format)
        except NoSceneError as e:
            raise HTTPException(404, str(e)) from None
        return Response(
            data,
            media_type=ctype,
            headers={
                "X-Bbox": window.bbox_header,
                "Cache-Control": "public, max-age=31536000, immutable",
                "Access-Control-Expose-Headers": "X-Bbox",
            },
        )

    return app


app = create_app()
