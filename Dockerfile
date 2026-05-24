FROM node:22-slim AS ui-build

WORKDIR /ui

RUN corepack enable

COPY ui/package.json ui/pnpm-lock.yaml ui/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY ui ./
RUN pnpm build


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

ARG VERSION="0.1.0"
ENV FOXHOLE_VERSION=${VERSION}

LABEL org.opencontainers.image.title="Foxhole" \
      org.opencontainers.image.description="Homelab diagnostic agent" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/JacobThree/Foxhole"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl nmap \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY agent ./agent
COPY schemas ./schemas
COPY tools ./tools
COPY workers ./workers
COPY --from=ui-build /ui/out ./ui/out

RUN pip install .

RUN useradd --create-home --shell /usr/sbin/nologin foxhole
USER foxhole

EXPOSE 8000

CMD ["uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
