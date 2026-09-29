# Carcare

Django storefront for products, bundles, session carts, cash-on-delivery orders, reviews, and order tracking.

## Local setup and tests

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements\base.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py seed_store
.\.venv\Scripts\python manage.py createsuperuser
npm ci
npm run css:build
.\.venv\Scripts\python manage.py runserver
```

Run the regression suite with:

```powershell
.\.venv\Scripts\python manage.py test tests
```

The tests use Django `TestCase` and cover pricing, session cart totals, shipping thresholds, guest COD checkout and inventory, order snapshots, tracking privacy, review moderation/uniqueness, admin access, and the staff ops dashboard.

## Operations dashboard

Day-to-day staff work lives at `/dashboard/` (not Django admin).

1. Create a staff user (`createsuperuser` or set `is_staff=True` on an existing account).
2. Open `http://127.0.0.1:8000/dashboard/login/` and sign in.
3. Use the sidebar for orders, catalog, inventory, bundles, promotions, shipping, reviews, customers, content, and inbox.

**Advanced:** the sidebar **Advanced admin** link opens `/admin/` for Users/Groups and rare edge cases. Prefer `/dashboard/` for routine operations (confirm orders, stock adjusts, review moderation, coupons, shipping zones).

## Deploy on AWS EC2 (Free Tier)

Step-by-step commands for a running Ubuntu `t3.micro` (browser Connect terminal) are in:

**[docs/DEPLOY_AWS_EC2.md](docs/DEPLOY_AWS_EC2.md)**

That guide covers security group ports, swap, PostgreSQL, Gunicorn, Nginx (HTTP first), and how to open the ops dashboard on your public IP.

## Production topology

Use one Ubuntu 24.04 LTS VM with:

- PostgreSQL bound only to localhost
- a Python virtual environment and Gunicorn with two workers
- one Nginx instance serving `/static/` and `/media/`, and proxying all other requests to Gunicorn over a Unix socket
- Cloudflare in front of Nginx, with **Full (strict)** TLS

A 1 vCPU/1 GB VM is workable for a small, low-traffic shop if it has 1–2 GB swap. Prefer 2 vCPU/2 GB once traffic, image volume, or admin activity grows. Two Gunicorn workers are intentionally conservative: each worker, PostgreSQL, Nginx, and the OS need memory. Measure RSS and request latency before increasing workers.

## First deployment

### 1. Provision the host

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential libpq-dev postgresql nginx rsync
sudo adduser --system --group --home /srv/carcare carcare
sudo install -d -o root -g carcare -m 0750 /etc/carcare
sudo install -d -o carcare -g www-data -m 0750 /srv/carcare/current/media
sudo -u postgres psql
```

In `psql`, create a least-privilege application database:

```sql
CREATE USER carcare_app WITH PASSWORD 'replace-with-a-long-random-password';
CREATE DATABASE carcare OWNER carcare_app;
\q
```

PostgreSQL should listen on `127.0.0.1` only. Do not expose port 5432 in the cloud firewall or UFW.

### 2. Upload the application

Copy the project to `/srv/carcare/current` (or clone it there), excluding development artifacts:

```bash
rsync -a --delete \
  --exclude .git --exclude .venv --exclude node_modules \
  --exclude db.sqlite3 --exclude media --exclude staticfiles \
  ./ user@SERVER:/tmp/carcare/

ssh user@SERVER
sudo rsync -a --delete --exclude media /tmp/carcare/ /srv/carcare/current/
sudo chown -R root:carcare /srv/carcare/current
sudo install -d -o carcare -g www-data -m 0750 /srv/carcare/current/media
sudo install -d -o carcare -g www-data -m 0750 /srv/carcare/current/staticfiles
sudo python3 -m venv /srv/carcare/venv
sudo /srv/carcare/venv/bin/pip install --upgrade pip
sudo /srv/carcare/venv/bin/pip install -r /srv/carcare/current/requirements/production.txt
```

Build Tailwind **before deployment** on the workstation or CI runner:

```bash
npm ci
npm run css:build
```

Commit or upload the generated `static/dist/app.css` with the release. Node and Tailwind are not needed on the production VM.

### 3. Configure Django

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(64))"` and create `/etc/carcare/carcare.env`:

```dotenv
DJANGO_SECRET_KEY=replace-with-generated-secret
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=carcare.example.com
CSRF_TRUSTED_ORIGINS=https://carcare.example.com
POSTGRES_DB=carcare
POSTGRES_USER=carcare_app
POSTGRES_PASSWORD=replace-with-database-password
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
DEFAULT_FROM_EMAIL="Carcare <orders@carcare.example.com>"
```

Protect the file and prepare Django:

```bash
sudo chown root:carcare /etc/carcare/carcare.env
sudo chmod 0640 /etc/carcare/carcare.env
sudo -u carcare bash -c 'set -a; source /etc/carcare/carcare.env; set +a; cd /srv/carcare/current && /srv/carcare/venv/bin/python manage.py migrate --noinput && /srv/carcare/venv/bin/python manage.py collectstatic --noinput && /srv/carcare/venv/bin/python manage.py check --deploy'
```

The same environment file syntax is accepted by systemd and Bash; quote values containing spaces as shown.

### 4. Install Gunicorn and Nginx

Replace `carcare.example.com` and the certificate paths in `deploy/nginx.conf`, then:

```bash
sudo cp /srv/carcare/current/deploy/carcare.service /etc/systemd/system/carcare.service
sudo cp /srv/carcare/current/deploy/nginx.conf /etc/nginx/sites-available/carcare
sudo ln -sfn /etc/nginx/sites-available/carcare /etc/nginx/sites-enabled/carcare
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl daemon-reload
sudo systemctl enable --now carcare
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl enable nginx
```

Inspect failures with:

```bash
sudo systemctl status carcare nginx
sudo journalctl -u carcare -n 100 --no-pager
```

## TLS and Cloudflare

1. Put the domain in Cloudflare and proxy its DNS record.
2. Create a Cloudflare Origin Certificate for the hostname, store it as `/etc/ssl/cloudflare/carcare.pem` and its key as `/etc/ssl/cloudflare/carcare.key`, and restrict the key to root (`chmod 0600`).
3. Set Cloudflare SSL/TLS mode to **Full (strict)**. Never use Flexible mode; Django would see incorrect scheme information and redirects could loop.
4. Enable “Always Use HTTPS”. Keep port 80 for redirect/validation and port 443 for traffic.
5. Allow SSH only from administrator IPs. Optionally restrict ports 80/443 at the provider firewall to Cloudflare's published IP ranges, but keep that list updated.

The supplied proxy headers match Django's existing `SECURE_PROXY_SSL_HEADER`. Nginx also terminates TLS and serves static/media directly.

## Routine updates

Build CSS and run tests before uploading:

```bash
npm ci
npm run css:build
.\.venv\Scripts\python manage.py test tests
```

On the VM, after replacing the files in `/srv/carcare/current`:

```bash
sudo /srv/carcare/venv/bin/pip install -r /srv/carcare/current/requirements/production.txt
sudo -u carcare bash -c 'set -a; source /etc/carcare/carcare.env; set +a; cd /srv/carcare/current && /srv/carcare/venv/bin/python manage.py migrate --noinput && /srv/carcare/venv/bin/python manage.py collectstatic --noinput && /srv/carcare/venv/bin/python manage.py check --deploy'
sudo systemctl restart carcare
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl is-active --quiet carcare nginx
```

Take a database backup before migrations. For safer rollbacks, upload each release to a timestamped directory, point `/srv/carcare/current` at the new release, and keep the previous release until health checks pass. Database migrations may still require a forward fix or a tested reverse migration.

## Backups and restore drills

Back up both PostgreSQL and user-uploaded media; source code and collected static files can be rebuilt. Keep encrypted copies off the VM.

Example nightly root cron job:

```bash
set -eu
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
install -d -m 0700 /var/backups/carcare
sudo -u postgres pg_dump --format=custom --file="/var/backups/carcare/db-$STAMP.dump" carcare
tar -C /srv/carcare/current -czf "/var/backups/carcare/media-$STAMP.tar.gz" media
find /var/backups/carcare -type f -mtime +14 -delete
```

Sync `/var/backups/carcare` to object storage after creation. Test restore quarterly on a separate database:

```bash
sudo -u postgres createdb carcare_restore
sudo -u postgres pg_restore --clean --if-exists --no-owner \
  --dbname=carcare_restore /var/backups/carcare/db-TIMESTAMP.dump
tar -C /tmp/carcare-restore -xzf /var/backups/carcare/media-TIMESTAMP.tar.gz
```

Monitor disk space, backup age, Nginx 5xx rates, Gunicorn restarts, PostgreSQL connections, and p95 response time. Resize before sustained swap use or CPU saturation. Images are the likely disk-growth driver; compress uploads operationally and alert well before the filesystem fills.
