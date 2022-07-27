FROM alpine:3.16
MAINTAINER Mateo Boudet <mateo.boudet@irisa.fr>

COPY requirements.txt /tmp/requirements.txt

RUN apk add --no-cache \
    python3 \
    nano \
    bash \
    ca-certificates \
    py3-numpy \
    wget libldap && \
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
    CREATE_USERS=1 \
    FAKE_EMAIL="" \
    LDAP_USER_FILTER="(mail=*)" \
    LDAP_GROUP_FILTER="(cn=*)"

CMD sleep 600 && watch -n $REPEAT_TIMER python3 /var/scripts/ldapollo.py
