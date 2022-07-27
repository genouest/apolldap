from __future__ import print_function

import os
import random
import re
import string
import sys
import time

from apollo import ApolloInstance

import ldap
from ldap.controls import SimplePagedResultsControl

wa = ApolloInstance(os.environ['APOLLO_URL'], os.environ['APOLLO_ADMIN'], os.environ['APOLLO_PASSWORD'])
admin_users = [os.environ['APOLLO_ADMIN']]

fake_email = os.environ['FAKE_EMAIL']
use_fake_email = fake_email and fake_email.startswith('@')

default_group = os.environ['DEFAULT_GROUP']

ldap_user_filter = '(mail=*)'
if 'LDAP_USER_FILTER' in os.environ and os.environ['LDAP_USER_FILTER']:
    ldap_user_filter = os.environ['LDAP_USER_FILTER']

ldap_group_filter = "(cn=*)"
if 'LDAP_GROUP_FILTER' in os.environ and os.environ['LDAP_GROUP_FILTER']:
    ldap_group_filter = os.environ['LDAP_GROUP_FILTER']


ldap_conf = {
    'url': os.environ['LDAP_URL'],
    'people_dn': os.environ['LDAP_USER_DN'],
    'group_dn': os.environ['LDAP_GROUP_DN']
}


def apollo_get_users():
    users = wa.users.get_users()
    users_mail = {}
    for user in users:
        users_mail[user['lastName']] = {'mail': user['username']}
    return users_mail


def apollo_get_groups():
    groups = wa.groups.get_groups()
    group_list = {}
    for group in groups:
        group_list[group['name']] = group['id']
    return group_list


def apollo_create_groups(groups_name_list):
    if groups_name_list:
        group_list = ','.join(groups_name_list)
        print("Creating groups '%s'" % group_list)
        created = wa.groups.create_group(group_list)

        return {x['name']: x['id'] for x in created}
    else:
        return {}


def apollo_update_groups(groups_membership, id_table):
    for group in groups_membership:
        print("Updating group membership: '%s' -> '%s'" % (group, groups_membership[group]))
        memberships = [{'groupId': id_table[group], 'users': groups_membership[group]}]
        wa.groups.update_membership(memberships=memberships)


def apollo_create_users(users_name_list):
    for user in users_name_list:
        print("Creating user '%s'" % (users_name_list[user]['apollo_name']))
        random_pass = ''.join(random.choice(string.ascii_lowercase) for x in range(32))
        wa.users.create_user(email=users_name_list[user]['mail'], first_name="REMOTE_USER", last_name=users_name_list[user]['apollo_name'], role="user", metadata={"INTERNAL_PASSWORD": random_pass}, password=random_pass)


def apollo_update_user_emails(apollo_users, ldap_users):
    for ldap_user in ldap_users:
        if ldap_user in apollo_users and ldap_users[ldap_user]['mail'] != apollo_users[ldap_user]['mail']:

            print("Updating email for user '%s' from '%s' to '%s'" % (ldap_users[ldap_user]['apollo_name'], apollo_users[ldap_user]['mail'], ldap_users[ldap_user]['mail']))
            wa.users.update_user(email=apollo_users[ldap_user]['mail'], first_name="REMOTE_USER", last_name=ldap_users[ldap_user]['apollo_name'], new_email=ldap_users[ldap_user]['mail'])


def ldap_get_users(restrict=None):
    con = ldap.initialize(ldap_conf['url'])
    con.simple_bind_s()
    page_size = 200
    page_control = SimplePagedResultsControl(criticality=True, size=page_size, cookie='')
    response = con.search_ext(ldap_conf['people_dn'], ldap.SCOPE_SUBTREE, ldap_user_filter, ['uid', 'mail', 'cn'], serverctrls=[page_control])
    pages = 0
    ldap_users = []
    while True:
        pages += 1
        print("Fetching page %s from ldap" % pages)
        rtype, rdata, rmsgid, serverctrls = con.result3(response)
        print("Fetched %s users from ldap (total: %s)" % (len(rdata), len(ldap_users)))
        ldap_users.extend(rdata)
        controls = [control for control in serverctrls if control.controlType == SimplePagedResultsControl.controlType]
        if not controls:
            print('The server ignores RFC 2696 control')
            break
        if not controls[0].cookie:
            break
        page_control.cookie = controls[0].cookie
        response = con.search_ext(ldap_conf['people_dn'], ldap.SCOPE_SUBTREE, ldap_user_filter, ['uid', 'mail', 'cn'], serverctrls=[page_control])

    users = {}
    for u in ldap_users:
        # If user is not in apollo, ignore it
        if use_fake_email:
            ldap_name = u[1]['uid'][0].decode("utf-8") + fake_email
            ldap_mail = ldap_name
        else:
            ldap_name = u[1]['uid'][0].decode("utf-8")
            ldap_mail = u[1]['mail'][0].decode("utf-8")
        if restrict is None or ldap_name in restrict:
            users[ldap_name] = {'apollo_name': ldap_name, 'mail': ldap_mail}
    return users


def ldap_get_groups(user_list):
    con = ldap.initialize(ldap_conf['url'])
    con.simple_bind_s()
    ldap_groups = con.search_s(ldap_conf['group_dn'], ldap.SCOPE_SUBTREE, ldap_group_filter, ['cn', 'memberUid', 'member'])
    groups = {}

    for g in ldap_groups:
        members = []
        if 'memberUid' in g[1]:
            for member in g[1]['memberUid']:
                member = member.decode("utf-8")
                if member in user_list:
                    members.append(user_list[member]['mail'])
                elif use_fake_email and member + fake_email in user_list:
                    members.append(user_list[member + fake_email]['mail'])
        if 'member' in g[1]:
            for member in g[1]['member']:
                uid_search = re.search('(?<=uid=)([^,]+)', member.decode("utf-8"))
                if uid_search:
                    uid = uid_search.group(1)
                    if uid in user_list:
                        members.append(user_list[uid]['mail'])
                    elif use_fake_email and uid + fake_email in user_list:
                        members.append(user_list[uid + fake_email]['mail'])
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
    missing_users = {}
    for ldap_user in ldap_users:
        if ldap_user not in apollo_users:
            missing_users[ldap_user] = ldap_users[ldap_user]
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

        if default_group and ldap_groups:
            all_users = filter_users([], ldap_users)
            ldap_groups[default_group] = [all_users[x]['mail'] for x in all_users]

        missing_apollo_users = filter_users(apollo_users, ldap_users)
        apollo_create_users(missing_apollo_users)

        if not use_fake_email:
            apollo_update_user_emails(apollo_users, ldap_users)
    else:
        # Only sync users already existing in Apollo
        print("Will NOT create missing Apollo users")
        apollo_and_ldap_users = ldap_get_users(apollo_users)
        ldap_groups = ldap_get_groups(apollo_and_ldap_users)

        if default_group and ldap_groups:
            all_users = filter_users([], apollo_and_ldap_users)
            ldap_groups[default_group] = [all_users[x]['mail'] for x in all_users]

    # Create missing groups
    missing_apollo_groups = filter_groups(apollo_groups, ldap_groups)
    new_groups = apollo_create_groups(missing_apollo_groups)
    for ng in new_groups:
        apollo_groups[ng] = new_groups[ng]

    # To avoid java.util.ConcurrentModificationException
    time.sleep(3)

    # Populate groups
    apollo_update_groups(ldap_groups, apollo_groups)


if __name__ == "__main__":
    main()
