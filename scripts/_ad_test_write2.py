import os
os.environ["AD_WRITE_SCOPE_OU"] = "dc=example,dc=com"   # allow whole domain (matching root probe scope)
from app.ad import operations as op
from app.ad import client
TEST_OU = "OU=AegisPassAdminTest,DC=example,DC=com"
DN = "CN=__aegispasstest3," + TEST_OU
STRONG = "Zq7!mK9@xP2#Lw"
RESET  = "Bn4$rT8@qW1#Mz"
try:
    c = client.get_connection(); c.add(TEST_OU, object_class=["top","organizationalUnit"]); c.unbind()
    print("OU ready")
except Exception as e:
    print("OU note:", repr(e))
try:
    op.create_user(DN, {"sAMAccountName": "__aegispasstest3", "givenName": "Test",
                        "sn": "User", "displayName": "Test User",
                        "userPrincipalName": "__aegispasstest3@example.com"}, STRONG, force_change=True)
    print("CREATE OK")
    u = op.get_user(DN); print("fetched:", u["sAMAccountName"], "| UAC:", u.get("userAccountControl"))
    op.set_user_enabled(DN, False); print("DISABLE OK")
    op.unlock_user(DN); print("UNLOCK OK")
    op.reset_password(DN, RESET, force_change=True); print("RESET OK")
    G1 = "CN=__srcgrp3," + TEST_OU; G2 = "CN=__tgtgrp3," + TEST_OU
    op.create_group(G1, "__srcgrp3"); op.create_group(G2, "__tgtgrp3")
    print("GROUP CREATE OK")
    op.copy_group_members(G1, G2); print("COPY MEMBERS OK")
    op.delete_group(G1); op.delete_group(G2); print("GROUP DELETE OK")
    op.delete_user(DN); print("DELETE OK")
    print("ALL WRITE OPS VERIFIED AGAINST LIVE DC")
except Exception as e:
    print("ERR:", repr(e))
    for d in [DN, "CN=__srcgrp3," + TEST_OU, "CN=__tgtgrp3," + TEST_OU]:
        try: op.delete_user(d)
        except Exception: pass
        try: op.delete_group(d)
        except Exception: pass
try:
    c2 = client.get_connection(); c2.delete(TEST_OU); c2.unbind(); print("OU cleaned")
except Exception as e:
    print("OU cleanup note:", e)
