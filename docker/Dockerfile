# syntax=docker/dockerfile:1
FROM python:3.11-slim

# ── Non-root user ────────────────────────────────────────────────────────
RUN groupadd --system --gid 1001 appuser \
    && useradd  --system --uid 1001 --gid appuser --create-home --shell /usr/sbin/nologin appuser

# ── Environment ──────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the application source.
# NOTE: .env is gitignored and must NOT be baked into the image. Supply it at
# runtime via `docker run --env-file .env` or docker-compose `env_file`.
COPY . .

# The pinned DC certificate is expected at app/ad/ca/ad-example.example.com.pem
# (committed in the repo) and is used for LDAPS certificate pinning.
# Ensure it is present in the build context; chown to the non-root user.
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# gunicorn listens on all interfaces inside the container; publish with care.
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
