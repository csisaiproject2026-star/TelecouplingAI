#!/usr/bin/env bash
set -euo pipefail

: "${PUBLIC_IP:?PUBLIC_IP must be set}"

PROJECT_ROOT="${PROJECT_ROOT:-/home/csisaiproject2026/csis-platform/telecouplingAI-project}"
CERTBOT_IMAGE="${CERTBOT_IMAGE:-certbot/certbot:v5.4.0}"
CERT_NAME="${CERT_NAME:-csis-gcp-ip}"
LETSENCRYPT_DIR="${LETSENCRYPT_DIR:-/etc/letsencrypt-csis}"
CERTBOT_WORK_DIR="${CERTBOT_WORK_DIR:-/var/lib/letsencrypt-csis}"
RENEW_BEFORE_SECONDS="${RENEW_BEFORE_SECONDS:-259200}"
NGINX_CONTAINER="${NGINX_CONTAINER:-tele-nginx}"

LIVE_DIR="${LETSENCRYPT_DIR}/live/${CERT_NAME}"
TARGET_DIR="${PROJECT_ROOT}/nginx/certs"
LOCK_FILE="/run/lock/csis-ip-cert-renew.lock"

exec 9>"${LOCK_FILE}"
flock -n 9 || exit 0

certificate_is_current() {
    test -f "${LIVE_DIR}/fullchain.pem" &&
        test -f "${LIVE_DIR}/privkey.pem" &&
        openssl x509 -checkend "${RENEW_BEFORE_SECONDS}" -noout \
            -in "${LIVE_DIR}/fullchain.pem" >/dev/null &&
        openssl x509 -checkip "${PUBLIC_IP}" -noout \
            -in "${LIVE_DIR}/fullchain.pem" >/dev/null
}

install_certificate() {
    install -d -m 0755 "${TARGET_DIR}"
    install -m 0644 "${LIVE_DIR}/fullchain.pem" "${TARGET_DIR}/server.crt.next"
    install -m 0600 "${LIVE_DIR}/privkey.pem" "${TARGET_DIR}/server.key.next"
    mv -f "${TARGET_DIR}/server.crt.next" "${TARGET_DIR}/server.crt"
    mv -f "${TARGET_DIR}/server.key.next" "${TARGET_DIR}/server.key"
}

if certificate_is_current; then
    if ! cmp -s "${LIVE_DIR}/fullchain.pem" "${TARGET_DIR}/server.crt" ||
        ! cmp -s "${LIVE_DIR}/privkey.pem" "${TARGET_DIR}/server.key"; then
        install_certificate
        docker exec "${NGINX_CONTAINER}" nginx -s reload
    fi
    exit 0
fi

docker image inspect "${CERTBOT_IMAGE}" >/dev/null 2>&1 ||
    docker pull "${CERTBOT_IMAGE}" >/dev/null

nginx_was_running=false
if test "$(docker inspect -f '{{.State.Running}}' "${NGINX_CONTAINER}" 2>/dev/null)" = "true"; then
    nginx_was_running=true
    docker stop "${NGINX_CONTAINER}" >/dev/null
fi

restore_nginx() {
    if "${nginx_was_running}"; then
        docker start "${NGINX_CONTAINER}" >/dev/null 2>&1 || true
    fi
}
trap restore_nginx EXIT

docker run --rm --network host \
    -v "${LETSENCRYPT_DIR}:/etc/letsencrypt" \
    -v "${CERTBOT_WORK_DIR}:/var/lib/letsencrypt" \
    "${CERTBOT_IMAGE}" certonly \
    --non-interactive \
    --agree-tos \
    --register-unsafely-without-email \
    --preferred-profile shortlived \
    --preferred-challenges http \
    --standalone \
    --ip-address "${PUBLIC_IP}" \
    --cert-name "${CERT_NAME}" \
    --force-renewal

install_certificate

if "${nginx_was_running}"; then
    docker start "${NGINX_CONTAINER}" >/dev/null
fi
trap - EXIT

docker exec "${NGINX_CONTAINER}" nginx -t
