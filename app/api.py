"""Consistent API response envelopes + audit integration for the JSON API."""
from __future__ import annotations

import functools
from typing import Any, Optional

from flask import jsonify, request, session

from app import audit


def ok(data: Any = None, meta: Optional[dict] = None):
    body = {"ok": True, "data": data, "error": None, "code": None}
    if meta:
        body["meta"] = meta
    return jsonify(body)


def fail(message: str, code: str = "error", status: int = 400, data: Any = None):
    return jsonify({"ok": False, "data": data, "error": message, "code": code}), status


def _actor() -> str:
    return (session.get("user") or {}).get("sAMAccountName", "") or "anonymous"


def _ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "")


def audit_action(action: str, target_getter=None):
    """Decorator: audit a mutating API call.

    target_getter(resp_data, *args, **kwargs) -> str  (optional; derives DN)
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            actor = _actor()
            ip = _ip()
            try:
                resp = f(*args, **kwargs)
            except PermissionError as e:
                audit.log(action, actor, target="", outcome="denied",
                          detail=str(e), ip=ip)
                return fail(str(e), code="denied", status=403)
            except Exception as e:
                audit.log(action, actor, outcome="error", detail=str(e), ip=ip)
                return fail(str(e), code="server_error", status=500)
            # success
            target = ""
            if target_getter:
                try:
                    target = target_getter(resp, *args, **kwargs) or ""
                except Exception:
                    target = ""
            audit.log(action, actor, target=target, outcome="success", ip=ip)
            return resp
        return wrapper
    return decorator
