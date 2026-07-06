# Installation Guide for FerryNotifier

This guide provides step-by-step instructions for deploying FerryNotifier on a production server.

## Quick start (Docker) + first-run setup

The fastest path is the published container with a persistent volume:

```bash
docker run -d --name ferrynotifier -p 5050:5050 \
  --env-file .env -v "$HOME/.ferrynotifier:/app/data" \
  ghcr.io/cdibona/ferrynotifier:latest
```

**Important — persistence:** settings live in `/app/data`; the `-v` bind mount
above keeps them on the host so they survive updates. When you update later, use
`deployment/update.sh` (it re-mounts the same directory) — never a bare
`docker run` of a new image, which would start with an empty data dir. The app
logs a loud warning at startup if `/app/data` is not a mounted volume.

Then open the **control panel** at `http://<host>:5050/` and:

1. **WSDOT key** — if you didn't set `WSDOT_API_KEY` in `.env`, paste your key into
   the "WSDOT API Key" field on either tab. ([Get one free](https://wsdot.wa.gov/traffic/api/).)
   Everything you enter is saved server-side to the `ferry-data` volume and
   survives restarts.
2. **Add a Vestaboard** — on the Vestaboard tab, choose "Add new board", set its
   name, model (**Flagship** 6×22 or **Note** 3×15), route, direction, and its
   Read/Write key (from [web.vestaboard.com](https://web.vestaboard.com)). The
   preview renders live. Turn on **Auto-push**; the default "on arrivals & space
   changes" pushes when a ferry docks, when drive-up spaces move >25% of capacity,
   or at least every 15 minutes.
3. **Add a TRMNL device (optional push)** — TRMNL usually *polls* your server; to
   have the server push, create a **Webhook** Private Plugin in your
   [TRMNL dashboard](https://usetrmnl.com/), paste the four layouts from
   `assets/trmnl-markup.liquid` into its Markup tabs, and copy the plugin's webhook
   URL into a TRMNL target here. Enable **Auto-push** (aligned to minute 13 of the
   15-minute refresh). For polling instead, point a Polling plugin at
   `http://<host>:5050/api/trmnl?route_id=sea-bi&direction=Seattle`.
4. **Verify** — the header shows "● Scheduler running" and each target shows its
   last-push time. Use **Push now** to test immediately.

Keep this server on a trusted network (e.g. a tailnet) — API keys are stored in
plaintext in the volume. The rest of this guide covers a from-source deployment
behind nginx.

---


## Prerequisites

- Ubuntu 20.04 LTS or newer (or similar Linux distribution)
- Python 3.8 or higher
- Nginx web server
- Domain name with DNS configured (for SSL)
- WSDOT Ferries API key

## Step 1: System Preparation

Update your system:

```bash
sudo apt update
sudo apt upgrade -y
```

Install required system packages:

```bash
sudo apt install -y python3 python3-pip python3-venv nginx git
```

## Step 2: Create Application Directory

Create a directory for the application:

```bash
sudo mkdir -p /opt/FerryTrmnl
sudo chown $USER:$USER /opt/FerryTrmnl
```

## Step 3: Clone Repository

Clone the FerryTrmnl repository:

```bash
cd /opt/FerryTrmnl
git clone https://github.com/cdibona/FerryTrmnl.git .
```

## Step 4: Set Up Python Virtual Environment

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install Python dependencies:

```bash
pip install --upgrade pip
pip install -r web/requirements.txt
```

## Step 5: Configure Environment Variables

Copy the environment template:

```bash
cp .env.template .env
```

Edit the `.env` file:

```bash
nano .env
```

Set at minimum:
- `WSDOT_API_KEY`: Your WSDOT API key
- `FERRY_ROUTE_ID`: Your preferred ferry route (optional)

Save and exit (Ctrl+X, then Y, then Enter).

## Step 6: Test the Application

Test that the application runs:

```bash
python web/app.py
```

You should see output like:
```
INFO:__main__:Starting Washington State Ferry Webhook Server
INFO:__main__:Server will run on 0.0.0.0:5050
```

Press Ctrl+C to stop the test server.

In another terminal, test the endpoints:

```bash
curl http://localhost:5050/health
curl http://localhost:5050/webhook
```

## Step 7: Set Up Systemd Service

Create log directory:

```bash
sudo mkdir -p /var/log/ferrytrmnl
sudo chown www-data:www-data /var/log/ferrytrmnl
```

Copy the systemd service file:

```bash
sudo cp deployment/ferrytrmnl.service /etc/systemd/system/
```

Edit the service file if needed (adjust paths, user, workers):

```bash
sudo nano /etc/systemd/system/ferrytrmnl.service
```

Set proper ownership:

```bash
sudo chown -R www-data:www-data /opt/FerryTrmnl
```

Reload systemd and enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ferrytrmnl
sudo systemctl start ferrytrmnl
```

Check the service status:

```bash
sudo systemctl status ferrytrmnl
```

View logs:

```bash
sudo journalctl -u ferrytrmnl -f
```

## Step 8: Configure Nginx

Copy the nginx configuration:

```bash
sudo cp deployment/nginx.conf.example /etc/nginx/sites-available/ferrytrmnl
```

Edit the configuration file:

```bash
sudo nano /etc/nginx/sites-available/ferrytrmnl
```

Replace `ferry.yourdomain.com` with your actual domain name.

For now, comment out the HTTPS server block (we'll set up SSL next).

Test nginx configuration:

```bash
sudo nginx -t
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/ferrytrmnl /etc/nginx/sites-enabled/
sudo systemctl reload nginx
```

## Step 9: Set Up SSL with Let's Encrypt

Install certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

Obtain SSL certificate:

```bash
sudo certbot --nginx -d ferry.yourdomain.com
```

Follow the prompts. Certbot will automatically configure nginx for HTTPS.

Test auto-renewal:

```bash
sudo certbot renew --dry-run
```

## Step 10: Final Testing

Test your deployment:

```bash
# Test health check
curl https://ferry.yourdomain.com/health

# Test webhook
curl https://ferry.yourdomain.com/webhook

# Test API
curl https://ferry.yourdomain.com/api/ferry-status
```

## Step 11: Configure Trmnl

1. Log in to your Trmnl account at [usetrmnl.com](https://usetrmnl.com/)
2. Create a new webhook plugin
3. Set the webhook URL to: `https://ferry.yourdomain.com/webhook`
4. Set refresh interval (recommended: 15-30 minutes)
5. Save and test the plugin
6. Assign to your Trmnl device

## Docker Deployment (Alternative)

### Build and Run

```bash
# Build the Docker image from project root
docker build -f deployment/Dockerfile -t ferrytrmnl .

# Run with .env file
docker run -p 5050:5050 --env-file .env ferrytrmnl
```

Or use docker-compose:

```bash
cd deployment
docker-compose up --build -d
```

### Test Health Check

```bash
# Check if container is healthy
docker ps

# Should show "healthy" in the STATUS column
```

### View Logs

```bash
docker-compose logs -f
```

## Monitoring and Maintenance

### View Application Logs

```bash
# Systemd logs
sudo journalctl -u ferrytrmnl -f

# Application logs (if configured)
sudo tail -f /var/log/ferrytrmnl/error.log
sudo tail -f /var/log/ferrytrmnl/access.log
```

### View Nginx Logs

```bash
sudo tail -f /var/log/nginx/ferrytrmnl_access.log
sudo tail -f /var/log/nginx/ferrytrmnl_error.log
```

### Restart Services

```bash
# Restart application
sudo systemctl restart ferrytrmnl

# Restart nginx
sudo systemctl restart nginx

# Reload nginx (no downtime)
sudo systemctl reload nginx
```

### Update Application

```bash
cd /opt/FerryTrmnl
git pull
source venv/bin/activate
pip install -r web/requirements.txt
sudo systemctl restart ferrytrmnl
```

## CI/CD Deployment

For automated deployments using GitHub Actions, see the workflow configuration in `.github/workflows/deploy.yml`.

### GitHub Secrets Required

Configure these secrets in your GitHub repository settings:

| Secret | Description |
|--------|-------------|
| `STAGING_HOST` | Staging server hostname |
| `STAGING_USER` | SSH username for staging |
| `STAGING_SSH_KEY` | SSH private key for staging |
| `PROD_HOST` | Production server hostname |
| `PROD_USER` | SSH username for production |
| `PROD_SSH_KEY` | SSH private key for production |

### Deployment Triggers

- **Push to main**: Deploys to staging
- **Create release/tag**: Deploys to production
- **Manual trigger**: Deploy to staging or production via GitHub Actions UI

## Troubleshooting

### Service Won't Start

Check logs:
```bash
sudo journalctl -u ferrytrmnl -n 50
```

Common issues:
- Missing or incorrect `.env` file
- Invalid API key
- Port already in use
- Permission issues

### Nginx 502 Bad Gateway

- Ensure ferrytrmnl service is running: `sudo systemctl status ferrytrmnl`
- Check if port 5050 is listening: `sudo netstat -tlnp | grep 5050`
- Review nginx error logs

### API Errors

- Verify WSDOT API key is valid
- Check internet connectivity
- Review application logs for specific errors

## Security Notes

- Keep your `.env` file secure (it contains your API key)
- Regularly update system packages and Python dependencies
- Monitor logs for unusual activity
- Consider setting up fail2ban for additional security
- Use strong SSL/TLS configuration (provided in nginx.conf.example)

## Performance Tuning

### Adjust Gunicorn Workers

Edit `/etc/systemd/system/ferrytrmnl.service`:

```ini
# Formula: (2 x CPU cores) + 1
ExecStart=/opt/FerryTrmnl/venv/bin/gunicorn --workers 4 ...
```

For a 2-core server: 5 workers
For a 4-core server: 9 workers

After changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ferrytrmnl
```

### Nginx Caching (Optional)

Add caching to nginx configuration to reduce load on WSDOT API:

```nginx
# Add to http block in /etc/nginx/nginx.conf
proxy_cache_path /var/cache/nginx/ferrytrmnl levels=1:2 keys_zone=ferrytrmnl_cache:10m max_size=100m inactive=60m use_temp_path=off;

# Add to location / block in your site config
proxy_cache ferrytrmnl_cache;
proxy_cache_valid 200 10m;
proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;
add_header X-Cache-Status $upstream_cache_status;
```

## Support

For issues or questions, please visit the [GitHub repository](https://github.com/cdibona/FerryTrmnl).
