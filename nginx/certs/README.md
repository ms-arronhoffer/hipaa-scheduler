# nginx TLS certificates

Drop production certs here (bind-mounted at `/etc/nginx/certs`):

- `staff.crt` / `staff.key`   — default server_name; used by the staff SPA vhost
- `admin.crt` / `admin.key`   — admin.<domain>
- `portal.crt` / `portal.key` — portal.<domain>

## Automatic self-signed fallback

If any of these cert pairs are missing when the `nginx` container starts, the
entrypoint script `nginx/docker-entrypoint.d/40-ensure-tls-certs.sh` generates a
self-signed certificate for the missing pair. This keeps nginx from
crash-looping on a fresh host (which would otherwise leave the stack with no
published ports). **Provision real certificates for production** — self-signed
certs trigger browser warnings. Existing certs in this directory are always used
as-is and are never overwritten.

For local dev, generate self-signed certs with:

```bash
mkcert -install
mkcert -cert-file staff.crt   -key-file staff.key   localhost 127.0.0.1
mkcert -cert-file admin.crt   -key-file admin.key   admin.localhost
mkcert -cert-file portal.crt  -key-file portal.key  portal.localhost
```

or fall back to `openssl req -x509 -newkey rsa:4096 -nodes ...`.

`.gitignore` excludes `*.key` and `*.crt` in this directory — never commit.
