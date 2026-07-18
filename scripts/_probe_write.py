import ldap3
from app.ad import client
conn = client.get_connection()
# Find OUs the service account likely manages: search for a user we can already
# read and see which OU it lives in, then test-create a test OU there.
conn.search("DC=example,DC=com", "(sAMAccountName=rupender.sharma)", search_scope=ldap3.SUBTREE,
            attributes=["distinguishedName"])
if conn.entries:
    dn = conn.entries[0].entry_dn
    print("sample user DN:", dn)
    parent = ",".join(dn.split(",")[1:])  # drop CN=, keep rest
    print("parent OU:", parent)
    test_ou = "OU=AegisPassAdminTest," + parent
    try:
        conn.add(test_ou, object_class=["top", "organizationalUnit"])
        print("CREATE OU UNDER parent OK:", test_ou)
        conn.delete(test_ou)
        print("cleaned test OU")
    except Exception as e:
        print("CREATE under parent ERR:", repr(e))
else:
    print("sample user not found")
conn.unbind()
