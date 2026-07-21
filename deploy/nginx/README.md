# HTTPS local setup for AegisPass

Self-signed or real-certificate nginx setup for AegisPass.

## What was configured

1. Self-signed SSL certificate (example):
   - `/etc/ssl/local/aegispass.example.com.crt`
   - `/etc/ssl/local/aegispass.example.com.key`
2. Nginx site config enabled at `/etc/nginx/sites-enabled/aegispass.conf`
3. HTTP to HTTPS redirect on port 80
4. Flask app behind reverse proxy on `127.0.0.1:8000`

## Using a real certificate

Replace the paths in `deploy/nginx-aegispass.conf` with your real certificate
and key (Let's Encrypt, internal CA, etc.).

## Start / restart

```bash
sudo nginx -t
sudo systemctl restart nginx
cd /opt/aegispass
source .venv/bin/activate
SESSION_COOKIE_SECURE=True PYTHONPATH=. python -c "from app import app; app.run(host='127.0.0.1', port=8000)"
```

For production, use the provided systemd unit instead of the Flask dev server.
