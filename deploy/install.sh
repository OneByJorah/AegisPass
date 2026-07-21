#!/usr/bin/env bash
#
# install.sh — Idempotent deployment for AegisPass
#
# Safe to run repeatedly. This script is meant to run as the unprivileged
# app user (appuser) and uses sudo only for the systemd steps.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_NAME="aegispass"
UNIT_SRC="$PROJECT_ROOT/systemd/${SERVICE_NAME}.service"
UNIT_DST="/etc/systemd/system/${SERVICE_NAME}.service"

VENV_DIR="$PROJECT_ROOT/.venv"
REQ_FILE="$PROJECT_ROOT/requirements.txt"
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"
ENV_FILE="$PROJECT_ROOT/.env"

usage() {
    cat <<'EOF'
Usage: ./deploy/install.sh

Idempotent deployment for AegisPass:
  * Verifies python3.11 is available
  * Creates .venv (if missing) and installs requirements.txt
  * Copies .env.example -> .env (only if .env is missing; you MUST edit it)
  * Symlinks, enables, and (re)starts the systemd service

Run as a normal user; sudo is used only for systemd operations.
EOF
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    "") : ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
esac

if ! command -v python3.11 >/dev/null 2>&1; then
    echo "ERROR: python3.11 not found on PATH. Install Python 3.11 first." >&2
    exit 1
fi
echo "==> Found $(python3.11 --version 2>&1)"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "==> Creating virtualenv at $VENV_DIR"
    python3.11 -m venv "$VENV_DIR"
else
    echo "==> virtualenv already exists at $VENV_DIR (skipping creation)"
fi

echo "==> Installing/upgrading pip and requirements"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$REQ_FILE"

if [ ! -f "$ENV_FILE" ]; then
    if [ ! -f "$ENV_EXAMPLE" ]; then
        echo "ERROR: $ENV_EXAMPLE not found; cannot seed .env" >&2
        exit 1
    fi
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo "WARNING: Created $ENV_FILE from .env.example." >&2
    echo "         You MUST edit $ENV_FILE and fill in AD credentials and" >&2
    echo "         secrets before the service will function. It is gitignored" >&2
    echo "         and must never be committed." >&2
else
    echo "==> $ENV_FILE already exists (left untouched)"
fi

if [ ! -f "$UNIT_SRC" ]; then
    echo "ERROR: $UNIT_SRC not found" >&2
    exit 1
fi

echo "==> Installing systemd unit ($UNIT_DST)"
sudo ln -sf "$UNIT_SRC" "$UNIT_DST"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "==> Service already running — restarting"
    sudo systemctl restart "$SERVICE_NAME"
else
    echo "==> Starting service"
    sudo systemctl start "$SERVICE_NAME"
fi

echo "==> Deployment complete. Current status:"
sudo systemctl status "$SERVICE_NAME" --no-pager || true
