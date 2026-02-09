# -----------------------------------------------------------------------------
# OptiTrade Production Dockerfile
# Optimized for CrewAI (Async) + Streamlit
# -----------------------------------------------------------------------------

# 1. Base Image: Lightweight Python 3.10 (Slug: Slim)
# Python 3.10+ is required for modern async features used in CrewAI
FROM python:3.10-slim

# 2. Set Environment Variables
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files (useless in containers)
# PYTHONUNBUFFERED: Ensures logs are streamed directly to the container logs (critical for Jenkins debugging)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 3. System Dependencies
# Install build tools needed for heavy math libraries (Pandas/Numpy/Scipy)
# curl is required for the HEALTHCHECK command
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 4. Security: Create a non-root user
# Running as 'root' inside Docker is a security risk. We create 'optiuser'.
RUN useradd -m -u 1000 optiuser

# 5. Set Working Directory
WORKDIR /app

# 6. Install Python Dependencies
# We copy requirements.txt FIRST to leverage Docker layer caching.
# If you change app.py but not requirements.txt, Docker won't re-install pip packages (saving minutes).
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 7. Copy Application Code
COPY . .

# 8. Permissions
# Transfer ownership of the /app directory to our non-root user
RUN chown -R optiuser:optiuser /app

# 9. Switch to Non-Root User
USER optiuser

# 10. Expose Network Port
# Streamlit runs on 8501 by default
EXPOSE 8501

# 11. Healthcheck
# Docker/Jenkins will ping this every 30s. If it fails, it restarts the container.
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# 12. Entrypoint
# Launches the app binding to 0.0.0.0 (required to be accessible outside the container)
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]