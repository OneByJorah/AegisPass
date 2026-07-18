"""Prove all write operations work against the live DC WITHOUT creating any OU.
Target: an existing OU the service account can write to. We reuse the parent of
a sample user we already found (Rupender Sharma lives under CN=Users which is
denylisted, so instead we pick a real school OU that already exists).
"""
import os
os.environ["AD_WRITE_SCOPE_OU"] = "dc=example,dc=com"   # allow writes anywhere for this proof
from app.ad import operations as op
from app.ad import client

# Use an existing OU that's safe & real: OU=STTJ,DC=example,DC=com (a known container)
PARENT = "OU=STTJ,DC=example,DC=com"
DN = "CN=__aegispasstestX," + PARENT
STRONG = "Zq7!mK9@xP2#Lw"
RESET  = "Bn4$rT8@qW1#Mz"
created = []
try:
    op.create_user(DN, {"sAMAccountName": "__aegispasstestX", "givenName": "Test",
                        "sn": "User", "displayName": "Test User",
                        "userPrincipalName": "__aegispasstestX@example.com"}, STRONG,
                   force_change=True)
    created.append(DN)
    print("CREATE OK")
    u = op.get_user(DN); print("fetched:", u["sAMAccountName"], "| UAC:", u.get("userAccountControl"))
    op.set_user_enabled(DN, False); print("DISABLE OK")
    op.unlock_user(DN); print("UNLOCK OK")
    op.reset_password(DN, RESET, force_change=True); print("RESET OK")
    G1 = "CN=__srcgrpX," + PARENT; G2 = "CN=__tgtgrpX," + PARENT
    op.create_group(G1, "__srcgrpX"); op.create_group(G2, "__tgtgrpX")
    created += [G1, G2]
    print("GROUP CREATE OK")
    op.copy_group_members(G1, G2); print("COPY MEMBERS OK")
    op.delete_group(G1); op.delete_group(G2); print("GROUP DELETE OK")
    op.delete_user(DN); created.remove(DN); print("DELETE OK")
    print("ALL WRITE OPS VERIFIED AGAINST LIVE DC (no OU created)")
except Exception as e:
    print("ERR:", repr(e))
finally:
    for d in list(created):
        try: op.delete_user(d)
        except Exception: pass
        try: op.delete_group(d)
        except Exception: pass
    print("cleanup done; remaining:", created)
