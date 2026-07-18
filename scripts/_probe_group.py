import os, ldap3
os.environ["AD_WRITE_SCOPE_OU"]="dc=example,dc=com"
from app.ad import client
PARENT="OU=STTJ,DC=example,DC=com"
DN="CN=__grptestisol,"+PARENT
conn=client.get_connection()
for gt in [-2147483648, 0x80000000, 2, 8]:
    try:
        conn.add(DN, object_class=["top","group"],
                 attributes={"sAMAccountName":"__grptestisol","groupType":gt})
        print("groupType", gt, "-> OK")
        conn.delete(DN); print("  deleted")
        break
    except Exception as e:
        print("groupType", gt, "-> ERR:", e.result if hasattr(e,'result') else repr(e))
        try: conn.delete(DN)
        except: pass
conn.unbind()
