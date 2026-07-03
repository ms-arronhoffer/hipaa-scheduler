#!/bin/sh
# -----------------------------------------------------------------------------
# Ensure nginx has TLS certificates to start with.
#
# The vhosts in conf.d reference staff/admin/portal cert pairs under
# /etc/nginx/certs. If real certs have not been provisioned yet (first boot,
# local dev, or a fresh host), nginx fails to load them at startup and
# crash-loops under `restart: unless-stopped`. Because nginx is the only
# container that publishes host ports (5443/5080), those ports then never bind
# and the whole stack looks like it has "no ports exposed".
#
# This runs from the official nginx image's /docker-entrypoint.d hook (before
# nginx starts). It generates a self-signed fallback for any *missing* cert
# pair so the proxy can always come up. Real certs, when present, are used
# as-is and are never overwritten.
# -----------------------------------------------------------------------------
set -u

CERT_DIR=/etc/nginx/certs

ensure_cert() {
  name=$1
  cn=$2
  crt="$CERT_DIR/$name.crt"
  key="$CERT_DIR/$name.key"

  # Already provisioned (real or previously generated cert): leave it alone.
  if [ -s "$crt" ] && [ -s "$key" ]; then
    return 0
  fi

  if ! command -v openssl >/dev/null 2>&1; then
    if ! apk add --no-cache openssl >/dev/null 2>&1; then
      echo "[tls] openssl unavailable; cannot generate self-signed cert for $name" >&2
      return 1
    fi
  fi

  echo "[tls] no certificate for '$name' found, generating self-signed fallback (CN=$cn)"
  if ! openssl req -x509 -newkey rsa:2048 -nodes \
      -keyout "$key" -out "$crt" -days 365 \
      -subj "/CN=$cn" -addext "subjectAltName=DNS:$cn" >/dev/null 2>&1; then
    echo "[tls] failed to generate self-signed cert for $name" >&2
    return 1
  fi
}

if ! mkdir -p "$CERT_DIR" 2>/dev/null; then
  echo "[tls] $CERT_DIR is not writable; skipping self-signed cert generation" >&2
  echo "[tls] provide real certs or mount the certs directory read-write" >&2
  return 0 2>/dev/null || exit 0
fi

# server_name defaults from conf.d/*.conf (staff = default vhost).
ensure_cert staff  localhost
ensure_cert admin  admin.localhost
ensure_cert portal portal.localhost

exit 0
