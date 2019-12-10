FROM alpine:3.8
MAINTAINER Mateo Boudet <mateo.boudet@irisa.fr>

COPY requirements.txt /tmp/requirements.txt

RUN apk add --no-cache \
    python3 \
    bash \
    nano \
    ca-certificates \
    wget man man-pages libldap && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --upgrade pip setuptools && \
    apk add --no-cache --virtual .build-deps build-base python3-dev openldap-dev && \
    pip3 install -r /tmp/requirements.txt && \
    apk --purge del .build-deps && \
    rm -r /root/.cache

WORKDIR /var/scripts
ADD ldapollo.py .

ENV LDAP_ENABLED=1 \
    REPEAT_TIMER=3600 \
    APOLLO_URL="http://0.0.0.0:8080" \
    APOLLO_ADMIN="admin" \
    APOLLO_PASSWORD="password" \
    LDAP_URL="ldap://ldap" \
    LDAP_USER_DN="ou=People,dc=default,dc=org" \
    LDAP_GROUP_DN="ou=Groups,dc=default,dc=org" \
    CREATE_USERS=1

CMD watch -n $REPEAT_TIMER python3 /var/scripts/ldapollo.py
