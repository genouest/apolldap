[![Docker Repository on Quay](https://quay.io/repository/genouest/apolldap/status "Docker Repository on Quay")](https://quay.io/repository/genouest/apolldap)

# Apolldap

A Docker image allowing to synchronize users and groups from an ldap server into an [Apollo](https://github.com/GMOD/apollo) instance.

This is especially useful when Apollo authentication is performed using the REMOTE_USER method, and an ldap module on an upstream HTTP proxy.

## Configuration

```
REPEAT_TIMER=3600                           # Delay between each synchronization (in seconds)
APOLLO_URL="http://0.0.0.0:8080"            # Url to the Apollo server
APOLLO_ADMIN="admin"                        # Apollo admin user name
APOLLO_PASSWORD="password"                  # Apollo admin user password
LDAP_URL="ldap://ldap"                      # Connection url for the LDAP server
LDAP_USER_DN="ou=People,dc=default,dc=org"  # DN for users in the LDAP server
LDAP_GROUP_DN="ou=Groups,dc=default,dc=org" # DN for groups in the LDAP server
MAIL_SUFFIX="@default"                      # Suffix appended to uid to produce Apollo usernames
```
