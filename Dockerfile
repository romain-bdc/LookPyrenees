FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/LookPyrenees/.venv/bin:$PATH" \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/LookPyrenees/output/.matplotlib \
    XDG_CACHE_HOME=/LookPyrenees/output/.cache

RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /LookPyrenees

# Install dependencies first to benefit from layer caching
COPY pyproject.toml uv.lock .python-version README.md LICENSE.txt ./
RUN uv sync --locked --no-install-project --no-dev

COPY src ./src
COPY ressources ./ressources
RUN uv sync --locked --no-dev

RUN useradd --system --create-home user_lp \
    && mkdir -p /LookPyrenees/data /LookPyrenees/output/.matplotlib /LookPyrenees/output/.cache \
    && chown -R user_lp:user_lp /LookPyrenees/data /LookPyrenees/output
USER user_lp

ENTRYPOINT ["LookPyrenees"]
CMD ["-b", "pyrenees_images"]
