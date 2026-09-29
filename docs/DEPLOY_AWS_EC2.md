# Deploy Carcare on AWS EC2 (Free Tier / t3.micro)

You already have:
- an AWS Free Tier account
- an **Ubuntu** EC2 instance (`t3.micro`) running
- the **browser “Connect” terminal** open

This guide deploys Carcare on that VM with:
**PostgreSQL (localhost) → Gunicorn → Nginx → your public IP (HTTP first)**

Later you can add a domain + HTTPS (Cloudflare / Let’s Encrypt).

---

## 0. Before you start (AWS console)

### Security group (inbound rules)

In **EC2 → Instances → your instance → Security → Security groups**, allow:

| Type | Port | Source | Why |
|------|------|--------|-----|
| SSH | 22 | Your IP (or leave as-is if you only use browser Connect) | SSH / Connect |
| HTTP | 80 | `0.0.0.0/0` | Website |
| HTTPS | 443 | `0.0.0.0/0` | Later, for TLS |

Do **not** open PostgreSQL `5432` to the internet.

### Note your public IP

On the instance page, copy **Public IPv4 address** (example: `13.60.12.34`).  
You will use it as `YOUR_EC2_IP` below.

### Put the code somewhere Git can reach

Best option: push this project to **GitHub** (private repo is fine), then clone on the server.

On your Windows PC (PowerShell), from the project folder:

```powershell
git status
git add .
git commit -m "Prepare for EC2 deploy"
# create a GitHub repo, then:
git remote add origin https://github.com/Vilen007/carcare.git
git push -u origin main
```

Also build CSS on your PC **before** deploy (Node is not required on the server):

```powershell
npm ci
npm run css:build
git add static/dist/app.css
git commit -m "Build production CSS"
git push
```

---

## 1. On the Ubuntu terminal — update system + add swap

`t3.micro` has ~1 GB RAM. Swap prevents freezes during `pip install` / migrate.

Paste these commands one block at a time:

```bash
sudo apt update
sudo apt upgrade -y

# 2 GB swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

Install packages:

```bash
sudo apt install -y \
  python3-venv python3-dev build-essential libpq-dev \
  postgresql postgresql-contrib nginx git rsync ufw curl
```

Optional firewall (keep SSH open):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status
```

---

## 2. Create app user and folders

```bash
sudo adduser --system --group --home /srv/carcare carcare
sudo install -d -o root -g carcare -m 0750 /etc/carcare
sudo install -d -o root -g carcare -m 0755 /srv/carcare
sudo install -d -o carcare -g www-data -m 0750 /srv/carcare/current
sudo install -d -o carcare -g www-data -m 0750 /srv/carcare/current/media
sudo install -d -o carcare -g www-data -m 0750 /srv/carcare/current/staticfiles
```

---

## 3. PostgreSQL database

```bash
sudo -u postgres psql
```

Inside `psql`, run (change the password):

```sql
CREATE USER carcare_app WITH PASSWORD 'REPLACE_WITH_LONG_DB_PASSWORD';
CREATE DATABASE carcare OWNER carcare_app;
\q
```

Confirm Postgres is local-only (default on Ubuntu is fine). Do not open `5432` in the security group.

---

## 4. Clone the project onto the server

Replace with your repo URL:

```bash
cd /tmp
git clone https://github.com/Vilen007/carcare.git carcare-src
sudo rsync -a --delete \
  --exclude .git --exclude .venv --exclude node_modules \
  --exclude db.sqlite3 --exclude media \
  /tmp/carcare-src/ /srv/carcare/current/
sudo chown -R root:carcare /srv/carcare/current
sudo install -d -o carcare -g www-data -m 0750 /srv/carcare/current/media
sudo install -d -o carcare -g www-data -m 0750 /srv/carcare/current/staticfiles
```

If the repo is **private**, use a GitHub personal access token when Git asks for a password, or set up an SSH deploy key.

---

## 5. Python virtualenv + dependencies

```bash
sudo python3 -m venv /srv/carcare/venv
sudo /srv/carcare/venv/bin/pip install --upgrade pip
sudo /srv/carcare/venv/bin/pip install -r /srv/carcare/current/requirements/production.txt
```

On `t3.micro` this can take several minutes. Watch for OOM; swap should protect you.

---

## 6. Django environment file

Generate a secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

Create the env file (replace placeholders, including `YOUR_EC2_IP`):

```bash
sudo tee /etc/carcare/carcare.env >/dev/null <<'EOF'
DJANGO_SECRET_KEY=PASTE_GENERATED_SECRET_HERE
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=YOUR_EC2_IP,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://YOUR_EC2_IP
POSTGRES_DB=carcare
POSTGRES_USER=carcare_app
POSTGRES_PASSWORD=REPLACE_WITH_LONG_DB_PASSWORD
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
SECURE_SSL_REDIRECT=false
DEFAULT_FROM_EMAIL=Carcare <noreply@localhost>
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EOF

sudo chown root:carcare /etc/carcare/carcare.env
sudo chmod 0640 /etc/carcare/carcare.env
```

**Important for first HTTP deploy:** `SECURE_SSL_REDIRECT=false` and `CSRF_TRUSTED_ORIGINS=http://YOUR_EC2_IP` (not `https://` yet).

---

## 7. Migrate, collectstatic, create staff user

```bash
sudo -u carcare bash -c 'set -a; source /etc/carcare/carcare.env; set +a; cd /srv/carcare/current && /srv/carcare/venv/bin/python manage.py migrate --noinput'
sudo -u carcare bash -c 'set -a; source /etc/carcare/carcare.env; set +a; cd /srv/carcare/current && /srv/carcare/venv/bin/python manage.py collectstatic --noinput'
sudo -u carcare bash -c 'set -a; source /etc/carcare/carcare.env; set +a; cd /srv/carcare/current && /srv/carcare/venv/bin/python manage.py createsuperuser'
```

Optional demo catalog:

```bash
sudo -u carcare bash -c 'set -a; source /etc/carcare/carcare.env; set +a; cd /srv/carcare/current && /srv/carcare/venv/bin/python manage.py seed_store'
```

---

## 8. Gunicorn systemd service

Copy the project unit file. On free tier, prefer **1 worker** to save RAM:

```bash
sudo cp /srv/carcare/current/deploy/carcare.service /etc/systemd/system/carcare.service
sudo sed -i 's/--workers 2/--workers 1/' /etc/systemd/system/carcare.service
sudo systemctl daemon-reload
sudo systemctl enable --now carcare
sudo systemctl status carcare --no-pager
```

If it failed:

```bash
sudo journalctl -u carcare -n 80 --no-pager
```

---

## 9. Nginx (HTTP first — no certificate yet)

Use the HTTP bootstrap config (included in the repo):

```bash
sudo cp /srv/carcare/current/deploy/nginx.http.conf /etc/nginx/sites-available/carcare
sudo sed -i "s/YOUR_EC2_IP/$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)/" /etc/nginx/sites-available/carcare
# If metadata IP is empty, edit manually:
#   sudo nano /etc/nginx/sites-available/carcare
# and set server_name to your public IP.

sudo ln -sfn /etc/nginx/sites-available/carcare /etc/nginx/sites-enabled/carcare
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

Confirm services:

```bash
sudo systemctl is-active carcare nginx postgresql
```

---

## 10. Open the site

In your browser:

- Storefront: `http://YOUR_EC2_IP/`
- Ops dashboard: `http://YOUR_EC2_IP/dashboard/login/`
- Advanced admin: `http://YOUR_EC2_IP/admin/`

Sign in with the superuser from step 7.

---

## 11. Update the app later (after code changes)

On your PC:

```powershell
npm run css:build
git add -A
git commit -m "Update"
git push
```

On the server:

```bash
cd /tmp
rm -rf carcare-src
git clone https://github.com/Vilen007/carcare.git carcare-src
sudo rsync -a --delete \
  --exclude .git --exclude .venv --exclude node_modules \
  --exclude db.sqlite3 --exclude media --exclude staticfiles \
  /tmp/carcare-src/ /srv/carcare/current/
sudo chown -R root:carcare /srv/carcare/current
sudo install -d -o carcare -g www-data -m 0750 /srv/carcare/current/media
sudo install -d -o carcare -g www-data -m 0750 /srv/carcare/current/staticfiles

sudo /srv/carcare/venv/bin/pip install -r /srv/carcare/current/requirements/production.txt
sudo -u carcare bash -c 'set -a; source /etc/carcare/carcare.env; set +a; cd /srv/carcare/current && /srv/carcare/venv/bin/python manage.py migrate --noinput && /srv/carcare/venv/bin/python manage.py collectstatic --noinput'
sudo systemctl restart carcare
sudo nginx -t && sudo systemctl reload nginx
```

---

## 12. Next: domain + HTTPS (when ready)

When you have a domain (example `carcare.pk`):

1. Point DNS **A record** to `YOUR_EC2_IP` (or use Cloudflare proxy).
2. Update `/etc/carcare/carcare.env`:
   - `DJANGO_ALLOWED_HOSTS=carcare.pk,www.carcare.pk`
   - `CSRF_TRUSTED_ORIGINS=https://carcare.pk,https://www.carcare.pk`
   - `SECURE_SSL_REDIRECT=true`
3. Install certificates (Cloudflare Origin Cert **or** Let’s Encrypt).
4. Switch Nginx to `deploy/nginx.conf` (HTTPS), replace `carcare.example.com`, then:

```bash
sudo systemctl restart carcare
sudo nginx -t && sudo systemctl reload nginx
```

Full TLS/Cloudflare notes are also in the main `README.md`.

---

## Troubleshooting cheat sheet

| Problem | Check |
|---------|--------|
| Site not loading | Security group port **80**, `sudo systemctl status nginx carcare` |
| 502 Bad Gateway | `sudo journalctl -u carcare -n 100 --no-pager` |
| DisallowedHost | `DJANGO_ALLOWED_HOSTS` must include the IP/domain you type in the browser |
| CSRF failed on login | `CSRF_TRUSTED_ORIGINS` must match scheme + host (`http://IP` for HTTP) |
| Login / add-to-cart / checkout “does nothing” on HTTP | Ensure `SECURE_SSL_REDIRECT=false` in `carcare.env`, then restart `carcare`. Secure cookies must not be forced over plain HTTP. |
| Static CSS missing | Rebuild `npm run css:build` on PC, push `static/dist/app.css`, redeploy + `collectstatic` |
| DB auth errors | Password in `/etc/carcare/carcare.env` must match Postgres user |

Useful commands:

```bash
sudo systemctl status carcare nginx postgresql --no-pager
sudo journalctl -u carcare -n 100 --no-pager
sudo nginx -t
tail -n 50 /var/log/nginx/error.log
```

---

## Minimal command checklist (order)

1. Swap + `apt install …`
2. Create `carcare` user + folders
3. Create Postgres user/DB
4. `git clone` → `/srv/carcare/current`
5. `venv` + `pip install -r requirements/production.txt`
6. `/etc/carcare/carcare.env`
7. `migrate` + `collectstatic` + `createsuperuser`
8. Enable `carcare` systemd service
9. Enable Nginx HTTP site
10. Open `http://YOUR_EC2_IP/`
