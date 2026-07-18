# SSL / HTTPS local setup for passwordreset.example.com

This folder contains the nginx reverse-proxy configuration to serve the Flask app over HTTPS on `passwordreset.example.com`.

## What was configured

1. **Self-signed SSL certificate** generated at:
   - `/etc/ssl/local/passwordreset.example.com.crt`
   - `/etc/ssl/local/passwordreset.example.com.key`

2. **Nginx site config** enabled at:
   - `/etc/nginx/sites-enabled/passwordreset.example.com.conf`

3. **HTTP → HTTPS redirect** on port 80.

4. **Flask app behind reverse proxy** on `127.0.0.1:8000`.

## Browser trust note

Because this uses a **self-signed certificate**, browsers will show a certificate warning the first time you visit `https://passwordreset.example.com`. You can either:

- Click **Advanced → Proceed** once per browser, or
- Install the cert into your system/browser trust store:
  ```bash
  sudo cp /etc/ssl/local/passwordreset.example.com.crt /usr/local/share/ca-certificates/
  sudo update-ca-certificates
  ```

## Using a real certificate

Replace the paths in this nginx config with your real certificate and key (e.g., from Let's Encrypt or your district CA):

```nginx
ssl_certificate     /path/to/fullchain.pem;
ssl_certificate_key /path/to/privkey.pem;
```

## Start / restart

```bash
sudo nginx -t
sudo systemctl restart nginx

# Start Flask backend (still required)
cd /home/j1admin/aegispass
source .venv/bin/activate
SESSION_COOKIE_SECURE=True PYTHONPATH=. python -c "from app import app; app.run(host='127.0.0.1', port=8000)"
```

For production use a WSGI server (Gunicorn, uWSGI) instead of the Flask dev server.
