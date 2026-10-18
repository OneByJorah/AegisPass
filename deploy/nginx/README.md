# HTTPS local setup for kervado

Self-signed or real-certificate nginx setup for kervado.

## What was configured

1. Self-signed SSL certificate (example):
   - `/etc/ssl/local/kervado.example.com.crt`
   - `/etc/ssl/local/kervado.example.com.key`
2. Nginx site config enabled at `/etc/nginx/sites-enabled/kervado.conf`
3. HTTP to HTTPS redirect on port 80
4. Flask app behind reverse proxy on `127.0.0.1:8000`

## Using a real certificate

Replace the paths in `deploy/nginx-kervado.conf` with your real certificate
and key (Let's Encrypt, internal CA, etc.).

## Start / restart

```bash
sudo nginx -t
sudo systemctl restart nginx
cd /opt/kervado
source .venv/bin/activate
SESSION_COOKIE_SECURE=True PYTHONPATH=. python -c "from app import app; app.run(host='127.0.0.1', port=8000)"
```

For production, use the provided systemd unit instead of the Flask dev server.
