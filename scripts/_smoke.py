"""Smoke test the running Flask app end-to-end against the live DC.

Requires the app running at http://127.0.0.1:8000 and a test user whose
credentials are supplied via the environment (NEVER hardcode here):
  SMOKE_USER, SMOKE_PASS
"""
import os
import requests

BASE = "http://127.0.0.1:8000"
USER = os.environ.get("SMOKE_USER", "")
PASS = os.environ.get("SMOKE_PASS", "")


def main():
    print("== /status.json ==")
    r = requests.get(BASE + "/status.json", timeout=10)
    print(r.status_code, r.json())

    print("== /health/ldap ==")
    r = requests.get(BASE + "/health/ldap", timeout=10)
    print(r.status_code, r.json())

    if not (USER and PASS):
        print("SKIP login (set SMOKE_USER/SMOKE_PASS)")
        return

    print("== login (form) ==")
    s = requests.Session()
    s.headers.update({"Connection": "close"})
    r = s.post(BASE + "/auth/login", data={"username": USER, "password": PASS}, timeout=15)
    print(r.status_code, r.json())

    print("== GET /api/users?q=rupender (authed) ==")
    r = s.get(BASE + "/api/users", params={"q": "rupender"}, timeout=15)
    print(r.status_code, "count=", r.json().get("count"))

    print("== GET /api/groups?q= (authed) ==")
    r = s.get(BASE + "/api/groups", params={"q": ""}, timeout=15)
    print(r.status_code, "count=", r.json().get("count"))

    print("SMOKE DONE")


if __name__ == "__main__":
    main()
