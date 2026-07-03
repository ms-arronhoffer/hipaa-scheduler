# -----------------------------------------------------------------------------
# Outer reverse proxy image.
#
# Based on the official nginx alpine image, but with the `openssl` CLI baked in.
# The entrypoint hook (docker-entrypoint.d/40-ensure-tls-certs.sh) generates a
# self-signed fallback certificate for any missing vhost cert pair so the proxy
# — the only container that publishes host ports (HTTPS_PORT->443, HTTP_PORT->80)
# — always comes up and binds those ports.
#
# The stock nginx:alpine image does NOT include the `openssl` binary, and the
# entrypoint's runtime `apk add openssl` fallback needs internet access. On a
# locked-down HIPAA VM with no egress that install fails, no certs are written,
# nginx fails to load `ssl_certificate`, and it crash-loops under
# `restart: unless-stopped` — so the published ports never bind. Installing
# openssl here at build time (the build runs on a networked CI runner) removes
# that runtime network dependency.
# -----------------------------------------------------------------------------
FROM nginx:1.27-alpine

RUN apk add --no-cache openssl
