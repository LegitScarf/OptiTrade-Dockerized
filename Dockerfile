FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

RUN test -d /app/src || (echo "ERROR: src/ directory not found in image!" && exit 1)

RUN find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
RUN find /app -type f -name "*.pyc" -delete 2>/dev/null || true

# FIX: Create ALL directories that SmartApi, Streamlit, and Python will ever
# need to write to, then chmod 777 so ANY UID (including Jenkins override UID)
# can write to them. This eliminates the UID mismatch between optiuser (1000)
# and the Jenkins --user flag entirely.
RUN mkdir -p /app/output \
    /app/logs \
    /tmp/smartapi_logs \
    /tmp/.streamlit \
    /tmp/.local && \
    chmod -R 777 /app/output \
    /app/logs \
    /tmp/smartapi_logs \
    /tmp/.streamlit \
    /tmp/.local

# Do NOT set USER — let the container run as whatever UID Docker/Jenkins assigns

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]