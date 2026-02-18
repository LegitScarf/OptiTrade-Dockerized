FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 optiuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

# FIX: Critical verification step — ensure the src/ directory was actually copied.
# If this fails, the build stops immediately instead of creating a broken image.
RUN test -d /app/src || (echo "ERROR: src/ directory not found in image!" && exit 1)

# FIX: Force-delete any stale .pyc files that might have been copied from the host.
# These can cause Python to load old cached bytecode instead of the new source.
RUN find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
RUN find /app -type f -name "*.pyc" -delete 2>/dev/null || true

# FIX: Explicitly create the output directory with correct permissions.
# This prevents permission errors when the container tries to write output files.
RUN mkdir -p /app/output && chown -R optiuser:optiuser /app

USER optiuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]