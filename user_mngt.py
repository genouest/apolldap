from __future__ import print_function

import sys
import os
import ldap
import requests

base_apollo_url="http://0.0.0.0:8080"

apollo_auth = {
    'username': os.environ['APOLLO_ADMIN'],
    'password': os.environ['APOLLO_PASSWORD']
}

ldap_conf = {
    'url': os.environ['LDAP_URL'],
    'people_dn': os.environ['LDAP_USER_DN'],
    'group_dn': os.environ['LDAP_GROUP_DN']
}

mail_suffix = os.environ['MAIL_SUFFIX']


def apollo_get_users():
    r = requests.post(base_apollo_url + '/user/loadUsers', json=apollo_auth)
    users_mail = []
    users = r.json()
    for user in users:
        users_mail.append(user['username'].split("@")[0])
    return users_mail

def apollo_get_groups():
    r = requests.post(base_apollo_url + '/group/loadGroups', json=apollo_auth)
    groups = r.json()
    group_list = {}
    for group in groups:
        print(group)
        group_list[group['name']] = group['id']
    return group_list

def apollo_create_groups(groups_name_list, apollo_existing_groups):
    for group in groups_name_list:
        body = apollo_auth
        body['name'] = groups_name_list[group]
        r = requests.post(base_apollo_url + '/group/createGroup', json=body)
        res = r.json()
        apollo_existing_groups[group] = res['id']
    return apollo_existing_groups

def apollo_update_groups(groups_membership, id_table):
    for group in groups_membership:
        body = apollo_auth
        body['users'] = groups_membership[group]
        body['groupId'] = id_table[group]
        r = requests.post(base_apollo_url + '/group/updateMembership', json=body)
        if r.status_code != 200:
            print(r)

def ldap_get_users(apollo_user_list):
    con = ldap.initialize(ldap_conf['url'])
    con.simple_bind_s()
    ldap_users = con.search_s(ldap_conf['people_dn'], ldap.SCOPE_SUBTREE, '(mail=*)', ['uid','mail','cn'])
    users = {}
    for u in ldap_users:
        # If user is not in apollo, ignore it
        if u[1]['uid'][0] in apollo_user_list:
            users[u[1]['uid'][0]] = u[1]['uid'][0] + mail_suffix
    return users

def ldap_get_groups(user_list):
    con = ldap.initialize(ldap_conf['url'])
    con.simple_bind_s()
    ldap_groups = con.search_s(ldap_conf['group_dn'], ldap.SCOPE_SUBTREE, "cn=*", ['cn','memberUid'])
    groups = {}

    for g in ldap_groups:
        members = []
        if 'memberUid' in g[1]:
            for member in g[1]['memberUid']:
                if member in user_list:
                    members.append(user_list[member])
        groups[g[1]['cn'][0]] = members

    return groups

def filter_groups(apollo_groups, ldap_groups):
    # Return list of missing groups in Apollo. What to do with missing groups in ldap? Remove from apollo?
    missing_groups = []
    for ldap_group in ldap_groups:
        if ldap_group not in apollo_groups:
            missing_groups.append(ldap_group)
    return missing_groups

def is_ldap_enabled():
    if 'LDAP_ENABLED' not in os.environ:
        return False
    value = os.environ['LDAP_ENABLED']
    if value.lower() in ('true', 't', '1'):
        return True
    else:
        return False

def main():

    if not is_ldap_enabled():
        sys.exit(0)

    apollo_user_list = apollo_get_users()
    apollo_groups = apollo_get_groups()

    user_list=ldap_get_users(apollo_user_list)
    ldap_groups=ldap_get_groups(user_list)

    missing_apollo_groups = filter_groups(apollo_groups, ldap_groups)

    # Create missing groups

    apollo_groups = apollo_create_groups(missing_apollo_groups, apollo_groups)

    # Populate groups

    apollo_update_groups(ldap_groups, apollo_groups)

if __name__ == "__main__": main()
