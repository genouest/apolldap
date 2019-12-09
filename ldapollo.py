from __future__ import print_function

import os
import random
import re
import string
import sys
import time

from apollo import ApolloInstance

import ldap

wa = ApolloInstance(os.environ['APOLLO_URL'], os.environ['APOLLO_ADMIN'], os.environ['APOLLO_PASSWORD'])
admin_users = [os.environ['APOLLO_ADMIN']]

ldap_conf = {
    'url': os.environ['LDAP_URL'],
    'people_dn': os.environ['LDAP_USER_DN'],
    'group_dn': os.environ['LDAP_GROUP_DN']
}

mail_suffix = os.environ['MAIL_SUFFIX']


def apollo_get_users():
    users = wa.users.get_users()
    users_mail = []
    for user in users:
        users_mail.append(user['username'].split("@")[0])
    return users_mail


def apollo_get_groups():
    groups = wa.groups.get_groups()
    group_list = {}
    for group in groups:
        group_list[group['name']] = group['id']
    return group_list


def apollo_create_groups(groups_name_list, apollo_existing_groups):
    group_list = ','.join(groups_name_list)
    print("Creating groups '%s'" % group_list)
    created = wa.groups.create_group(group_list)

    return {x['name']: x['id'] for x in created}


def apollo_update_groups(groups_membership, id_table):
    memberships = []
    for group in groups_membership:
        memberships.append({'groupId': id_table[group], 'users': groups_membership[group]})
        print("Updating group membership: '%s'" % (memberships))
        wa.groups.update_membership(memberships=memberships)


def apollo_create_users(users_name_list):
    for user in users_name_list:
        print("Creating user '%s'" % (user + mail_suffix))
        random_pass = ''.join(random.choice(string.ascii_lowercase) for x in range(32))
        wa.users.create_user(email=user + mail_suffix, first_name="REMOTE_USER", last_name=user + mail_suffix, role="user", metadata={"INTERNAL_PASSWORD": random_pass}, password=random_pass)


def ldap_get_users(restrict=None):
    con = ldap.initialize(ldap_conf['url'])
    con.simple_bind_s()
    ldap_users = con.search_s(ldap_conf['people_dn'], ldap.SCOPE_SUBTREE, '(mail=*)', ['uid', 'mail', 'cn'])
    users = {}
    for u in ldap_users:
        # If user is not in apollo, ignore it
        ldap_name = u[1]['uid'][0].decode("utf-8")
        if restrict is None or (ldap_name + mail_suffix) in restrict:
            users[ldap_name] = ldap_name + mail_suffix
    return users


def ldap_get_groups(user_list):
    con = ldap.initialize(ldap_conf['url'])
    con.simple_bind_s()
    ldap_groups = con.search_s(ldap_conf['group_dn'], ldap.SCOPE_SUBTREE, "cn=*", ['cn', 'memberUid', 'member'])
    groups = {}

    for g in ldap_groups:
        members = []
        if 'memberUid' in g[1]:
            for member in g[1]['memberUid']:
                if member in user_list:
                    members.append(user_list[member])
        if 'member' in g[1]:
            for member in g[1]['member']:
                uid_search = re.search('(?<=uid=)([^,]+)', member.decode("utf-8"))
                if uid_search:
                    uid = uid_search.group(1)
                    if uid in user_list:
                        members.append(user_list[uid])
        groups[g[1]['cn'][0].decode("utf-8")] = members

    return groups


def filter_groups(apollo_groups, ldap_groups):
    # Return list of missing groups in Apollo.
    missing_groups = []
    for ldap_group in ldap_groups:
        if ldap_group not in apollo_groups:
            missing_groups.append(ldap_group)
    return missing_groups


def filter_users(apollo_users, ldap_users):
    # Return list of missing users in Apollo.
    missing_users = []
    for ldap_user in ldap_users:
        if ldap_user not in apollo_users:
            missing_users.append(ldap_user)
    return missing_users


def is_ldap_enabled():
    if 'LDAP_ENABLED' not in os.environ:
        return False
    value = os.environ['LDAP_ENABLED']
    if value.lower() in ('true', 't', '1'):
        return True
    else:
        return False


def should_create_users():
    if 'CREATE_USERS' not in os.environ:
        return False
    value = os.environ['CREATE_USERS']
    if value.lower() in ('true', 't', '1'):
        return True
    else:
        return False


def clean_all():
    for u in wa.users.get_users():
        if u['username'] not in admin_users:
            print("Deleting user %s" % u['username'])
            wa.users.delete_user(u['username'])
    print("Deleting groups %s" % ','.join([x['name'] for x in wa.groups.get_groups()]))
    wa.groups.delete_group(','.join([x['name'] for x in wa.groups.get_groups()]))


def main():

    if not is_ldap_enabled():
        sys.exit(0)

    # For debuging only
    # clean_all()

    apollo_users = apollo_get_users()
    apollo_groups = apollo_get_groups()

    if should_create_users():
        # Create missing users
        print("Will create missing Apollo users")
        ldap_users = ldap_get_users()
        ldap_groups = ldap_get_groups(ldap_users)

        missing_apollo_users = filter_users(apollo_users, ldap_users)
        apollo_create_users(missing_apollo_users)
    else:
        # Only sync users already existing in Apollo
        print("Will NOT create missing Apollo users")
        apollo_and_ldap_users = ldap_get_users(apollo_users)
        ldap_groups = ldap_get_groups(apollo_and_ldap_users)

    # Create missing groups
    missing_apollo_groups = filter_groups(apollo_groups, ldap_groups)
    apollo_groups = apollo_create_groups(missing_apollo_groups, apollo_groups)

    # To avoid java.util.ConcurrentModificationException
    time.sleep(3)

    # Populate groups
    apollo_update_groups(ldap_groups, apollo_groups)


if __name__ == "__main__":
    main()
