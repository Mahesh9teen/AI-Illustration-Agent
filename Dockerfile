# ─────────────────────────────────────────────────────────
# AI Illustration Agent — Dockerfile
# Target: Google Cloud Run (amd64 Linux)
# ─────────────────────────────────────────────────────────

# Stage 1: dependency builder (keeps final image lean)
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools needed for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install into an isolated prefix so we can copy just the site-packages
RUN pip install --upgrade pip \
 && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ─────────────────────────────────────────────────────────
# Stage 2: runtime image
# ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="AI Illustration Agent"
LABEL description="ADK-based illustration agent powered by Google Gemini"

# Cloud Run requires the container to listen on $PORT (default 8080)
ENV PORT=8080
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ /app/

# Create a non-root user for security best practices
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

# Expose the port Cloud Run will route to
EXPOSE 8080

# Health check so Cloud Run marks the revision healthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')"

# Use exec form to ensure signals are forwarded correctly
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
