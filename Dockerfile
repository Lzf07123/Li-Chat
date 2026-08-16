ARG BASE_IMAGE_REGISTRY=
ARG PYPI_INDEX_URL=https://mirrors.ustc.edu.cn/pypi/simple
ARG APT_MIRROR=http://mirrors.ustc.edu.cn/debian
FROM ${BASE_IMAGE_REGISTRY}python:3.12-slim

ARG PYPI_INDEX_URL=https://mirrors.ustc.edu.cn/pypi/simple
ARG APT_MIRROR=http://mirrors.ustc.edu.cn/debian

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    UV_DEFAULT_INDEX=${PYPI_INDEX_URL} \
    UV_NO_PROGRESS=1

# 统一容器时区为 Asia/Shanghai（日志与本地时间一致）
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    sed -i "s|http://deb.debian.org/debian|${APT_MIRROR}|g" \
        /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 用镜像源装 uv；pip 缓存挂载到 BuildKit cache，重构建不重复下载
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-compile -i "${PYPI_INDEX_URL}" uv

RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY pyproject.toml uv.lock ./
# uv 缓存挂载到 BuildKit cache：pyproject/uv.lock 未变时该层秒级复用，
# 变更后也只下载新增/变化的 wheel，不再整包重下
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY app ./app
COPY static ./static
COPY .env.example ./

# 构建期冒烟：镜像内必须能完整导入应用，遗漏 COPY 在此暴露
RUN .venv/bin/python -c "import app.main"

RUN mkdir -p /app/data && chown -R 10001:10001 /app

USER 10001

EXPOSE 8000

# 必须单 worker：jti 防重放/会话/WS 连接表均为进程内实现（见 docs/security.md）
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--workers", "1"]
