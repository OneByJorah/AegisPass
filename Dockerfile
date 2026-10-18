FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

COPY . .

RUN useradd -m -u 1000 appuser && mkdir -p /app/logs && chown -R appuser:appuser /app
USER appuser

VOLUME ["/app/logs"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD ["sh", "-c", "wget --no-verbose --tries=1 --spider http://localhost:8000/health || exit 1"]

ENV PATH="/home/appuser/.local/bin:${PATH}"

# Run via gunicorn. Number of workers auto-scales with available CPU cores.
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "--timeout", "30", "--log-level", "info", "app:app"]
