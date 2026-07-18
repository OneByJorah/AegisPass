import ldap3
from app.ad import client
conn = client.get_connection()
# Probe: can the service account create an OU at the domain root?
test_ou = "OU=AegisPassAdminTest,DC=example,DC=com"
try:
    conn.add(test_ou, object_class=["top", "organizationalUnit"])
    print("ROOT WRITE OK -> service account CAN create at domain root")
    # also test user creation under a real school OU to confirm delegated scope
    conn.delete(test_ou)
    print("cleaned")
except Exception as e:
    print("ROOT WRITE DENIED:", repr(e))
conn.unbind()
