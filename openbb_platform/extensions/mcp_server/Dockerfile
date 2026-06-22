FROM python:3.12-slim

ARG OPENBB_VERSION=4.7.2

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/openbb \
    OPENBB_MCP_NAME="OpenBB MCP 股票" \
    OPENBB_MCP_ALLOWED_TOOL_CATEGORIES="equity,etf,index,news" \
    OPENBB_MCP_DEFAULT_TOOL_CATEGORIES="equity,etf,index,news" \
    OPENBB_MCP_ENABLE_TOOL_DISCOVERY="false" \
    OPENBB_MCP_UVICORN_CONFIG="host:0.0.0.0,port:8001"

WORKDIR /tmp/build

COPY . /tmp/build/openbb-mcp-server

RUN python -m pip install --upgrade pip && \
    python -m pip install "openbb==${OPENBB_VERSION}" && \
    python -m pip install /tmp/build/openbb-mcp-server && \
    useradd --create-home --home-dir /home/openbb --shell /bin/bash openbb && \
    mkdir -p /home/openbb/.openbb_platform && \
    chown -R openbb:openbb /home/openbb

WORKDIR /home/openbb
USER openbb

EXPOSE 8001
VOLUME ["/home/openbb/.openbb_platform"]

ENTRYPOINT ["openbb-mcp"]
CMD []
