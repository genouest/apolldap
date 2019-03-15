FROM alpine:3.8
MAINTAINER Mateo Boudet <mateo.boudet@irisa.fr>

# Install packages for python-ldap

RUN apk add --update \
        python \
        python-dev \
        py-pip \
        build-base \
        build-base \
        openldap-dev \
        python2-dev \
        python3-dev \
    && pip install python-ldap requests

WORKDIR /var/scripts
ADD user_mngt.py .

ENV LDAP_ENABLED=0 \
    REPEAT_TIMER=3600 \
    APOLLO_URL="http://0.0.0.0:8080" \
    APOLLO_ADMIN="admin" \
    APOLLO_PASSWORD="password" \
    LDAP_URL="ldap://dsldap" \
    LDAP_USER_DN="ou=People,dc=default,dc=org" \
    LDAP_GROUP_DN="ou=Groups,dc=default,dc=org" \
    MAIL_SUFFIX="@default"

ENTRYPOINT watch -n $REPEAT_TIMER python /var/scripts/user_mngt.py
