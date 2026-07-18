"""Verify a live pinned LDAPS bind to the DC using real .env creds (no writes)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ldap3
from app.config import Config, load_dotenv_if_present
load_dotenv_if_present()
Config.SECRET_KEY = Config.SECRET_KEY  # touch
from app.ad import client

try:
    conn = client.get_connection()
    print("BOUND OK as", conn.user)
    print("Server:", conn.server.host)
    # read the bind account to prove directory access
    conn.search(Config.AD_BASE_DN,
                f"(distinguishedName={Config.AD_BIND_USER})",
                attributes=["cn", "sAMAccountName", "userPrincipalName"])
    if conn.entries:
        e = conn.entries[0]
        print("Bind account:", e["cn"].value, "/", e["sAMAccountName"].value)
    # count users
    conn.search(Config.AD_BASE_DN, "(objectClass=user)", search_scope=ldap3.LEVEL,
                attributes=["sAMAccountName"])
    print("Users visible at BASE level:", len(conn.entries))
    conn.unbind()
    print("RESULT: PASS")
except Exception as ex:
    print("RESULT: FAIL", repr(ex))
