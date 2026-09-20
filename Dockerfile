FROM docker.io/library/python:3.13-slim AS base

ENV PATH="/venv/bin:${PATH}" \
    UV_PROJECT_ENVIRONMENT="/venv" \
    PYTHONUNBUFFERED=1

FROM base AS build

COPY --from=ghcr.io/astral-sh/uv:0.9.21 /uv /uvx /usr/local/bin/

COPY ./pyproject.toml /pyproject.toml
COPY ./uv.lock /uv.lock

RUN uv sync --frozen --no-default-groups --no-install-project --link-mode=copy

COPY ./src /src

RUN uv pip install --no-deps .

FROM base

COPY --from=build /venv /venv

WORKDIR /app

CMD [ "python", "-OOm", "geo_watcher", "--config", "/config.toml" ]
