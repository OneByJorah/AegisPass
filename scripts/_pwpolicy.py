import ldap3
from app.ad import client
conn = client.get_connection()
conn.search("DC=example,DC=com", "(objectClass=domain)", search_scope=ldap3.BASE,
            attributes=["minPwdLength", "pwdProperties", "pwdHistoryLength",
                        "lockoutThreshold", "maxPwdAge"])
if conn.entries:
    e = conn.entries[0]
    for a in ["minPwdLength", "pwdProperties", "pwdHistoryLength", "lockoutThreshold"]:
        print(a, "=", e[a].value)
    pp = int(e["pwdProperties"].value or 0)
    print("COMPLEXITY_ENABLED:", bool(pp & 1))
    ma = e["maxPwdAge"].value
    print("maxPwdAge_ticks:", ma)
conn.unbind()
