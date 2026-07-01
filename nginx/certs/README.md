# nginx TLS certificates

Drop production certs here (bind-mounted read-only at `/etc/nginx/certs`):

- `staff.crt` / `staff.key`   — default server_name; used by the staff SPA vhost
- `admin.crt` / `admin.key`   — admin.<domain>
- `portal.crt` / `portal.key` — portal.<domain>

For local dev, generate self-signed certs with:

```bash
mkcert -install
mkcert -cert-file staff.crt   -key-file staff.key   localhost 127.0.0.1
mkcert -cert-file admin.crt   -key-file admin.key   admin.localhost
mkcert -cert-file portal.crt  -key-file portal.key  portal.localhost
```

or fall back to `openssl req -x509 -newkey rsa:4096 -nodes ...`.

`.gitignore` excludes `*.key` and `*.crt` in this directory — never commit.
