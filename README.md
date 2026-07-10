# FerryNotifier

Real-time [Washington State Ferry](https://www.wsdot.wa.gov/ferries/) status on your
[TRMNL](https://usetrmnl.com/) e-ink display and/or [Vestaboard](https://www.vestaboard.com/)
split-flap board. FerryNotifier polls the WSDOT Ferries API, renders the next departure,
drive-up space, and delays, and pushes them to your devices on a schedule — all from a
small self-hosted web control panel.

<!-- Add a screenshot here, e.g. ![Control panel](assets/screenshot.png) -->

- 🚢 Next departure, drive-up spaces, and delay alerts for any WSDOT route
- 🖥️ Push to **TRMNL** (webhook or polling) and **Vestaboard** / Vestaboard Note
- ⏰ Background scheduler with per-device intervals, quiet hours, and sleep messages
- 🎛️ Web control panel — configure everything in the browser, no redeploys
- 🐳 One-command Docker image, settings persisted on a mounted volume

---

## Quick start (Docker)

You need a free **WSDOT Ferries API key** — request one (it arrives by email) at
<https://wsdot.wa.gov/traffic/api/>.

```bash
docker run -d --name ferrynotifier -p 5050:5050 \
  -e WSDOT_API_KEY=your_key_here \
  -v "$HOME/.ferrynotifier:/app/data" \
  ghcr.io/cdibona/ferrynotifier:latest
```

Then open the control panel at **<http://localhost:5050/>** and:

1. Pick a **route** and **direction**, and preview how it looks on TRMNL / Vestaboard.
2. Add a **device target** (a TRMNL webhook URL or a Vestaboard Read/Write key).
3. Turn on **Auto-push** — the built-in scheduler keeps the device updated.

> **Why the `-v` mount?** All your settings (targets, keys, schedules, capture
> history) live in `/app/data`. Bind-mounting `$HOME/.ferrynotifier` keeps them on
> the host so they **survive updates**. Update later with
> [`deployment/update.sh`](deployment/update.sh), which re-mounts the same directory —
> never a bare `docker run` of a new image, which would start with an empty data dir.

Prefer Compose? [`deployment/docker-compose.ghcr.yml`](deployment/docker-compose.ghcr.yml)
pulls the published image and manages the volume for you:

```bash
docker compose -f deployment/docker-compose.ghcr.yml up -d
```

You can also skip `-e WSDOT_API_KEY` entirely and paste the key into the control
panel — it's saved server-side with the rest of your settings.

> **Keep it on a trusted network.** API keys are stored in plaintext in the data
> volume, so run FerryNotifier on your LAN or tailnet, not the public internet.

---

## Contents

- [How it works](#how-it-works)
- [The control panel](#the-control-panel)
- [Connecting devices](#connecting-devices)
- [Ferry routes](#ferry-routes)
- [Configuration](#configuration)
- [API endpoints](#api-endpoints)
- [Other ways to run](#other-ways-to-run)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## How it works

FerryNotifier is a small Flask app. It fetches vessel locations, terminal sailing
space, and service alerts from the [WSDOT Ferries API](https://www.wsdot.wa.gov/ferries/api/),
computes the next departure and drive-up space for your chosen route + direction, and
renders that for each device type. A background scheduler pushes to every enabled
target on its own interval; you manage it all from the web control panel.

---

## The control panel

The root page (`/`) has two tabs — **TRMNL** and **Vestaboard** — for previewing and
managing devices.

**Targets & scheduling.** Add each device as a target (name, route, direction, and its
webhook URL or Read/Write key). Every target has its own schedule and a **Push now**
button. The header shows whether the scheduler is running and each target's last push.

- **Vestaboard "smart" trigger** — pushes when a ferry newly docks, when drive-up
  spaces change by more than a set % of capacity, or at least every N minutes.
- **TRMNL "aligned" trigger** — pushes at minute 13 of the 15-minute cycle so fresh
  data lands just before the device refreshes.

**Quiet hours & sleep message.** Each Vestaboard can have quiet hours (e.g.
22:00–06:00): during the window the server stops pushing updates and shows a pre-sleep
message once — a line of text or a captured layout. Click **Read current board** to
grab whatever is on the board and save it to that board's capture history, then pick
any capture as the sleep message.

**Persistence.** All settings are saved on the server as JSON (default
`/app/data/settings.json`), so they survive restarts and are shared across browsers.
Mount a volume at `/app/data` to keep them (the Docker quick-start does this).

---

## Connecting devices

### TRMNL

Create a **Private Plugin** in your [TRMNL dashboard](https://usetrmnl.com/) (needs the
Developer perk), then choose a strategy:

- **Webhook** (works on a private/tailnet server): copy the webhook URL TRMNL gives you,
  add it as a TRMNL target in the control panel, and enable Auto-push. The server pushes
  to it. TRMNL rate-limits webhooks to once per 5 minutes, so intervals are floored at 5 min.
- **Polling** (needs a publicly reachable server): point a Polling plugin at
  `http://<your-host>:5050/api/trmnl?route_id=sea-bi&direction=Seattle`.

For the plugin **markup**, the control panel's TRMNL tab shows ready-to-paste blocks —
one per layout (Full / Half Horizontal / Half Vertical / Quadrant), each sized for that
screen — with Copy buttons and step-by-step instructions. The same templates live in
[`assets/trmnl-markup.liquid`](assets/trmnl-markup.liquid).

> TRMNL renders each layout at its own size and **crops** oversized content, so paste
> the per-layout blocks into their matching tabs rather than relying on one template for
> all sizes.

### Vestaboard

On the Vestaboard tab, add a board with its name, model (**Flagship** 6×22 or **Note**
3×15), route, direction, and Read/Write key (from the Vestaboard app or
[web.vestaboard.com](https://web.vestaboard.com)). The preview renders live; enable
Auto-push to keep it updated.

---

## Ferry routes

Use these route IDs when configuring a target or a polling URL:

| Route ID | Route |
|----------|-------|
| `sea-bi` | Seattle / Bainbridge Island |
| `sea-br` | Seattle / Bremerton |
| `ed-king` | Edmonds / Kingston |
| `muk-cl` | Mukilteo / Clinton |
| `f-v-s` | Fauntleroy / Vashon |
| `f-s` | Fauntleroy / Southworth |
| `s-v` | Southworth / Vashon |
| `pt-key` | Port Townsend / Coupeville |
| `pd-tal` | Pt. Defiance / Tahlequah |
| `ana-sj` | Anacortes / San Juan Islands |

---

## Configuration

Most settings are managed in the control panel and saved to the data volume. For the
few that are process-level, set environment variables (via `-e`, `--env-file .env`, or
Compose). Copy [`.env.template`](.env.template) to `.env` to start from a documented set.

| Variable | Description | Default |
|----------|-------------|---------|
| `WSDOT_API_KEY` | WSDOT Ferries API key (can also be entered in the UI) | *required* |
| `FLASK_HOST` | Bind address | `0.0.0.0` |
| `FLASK_PORT` | Port | `5050` |
| `ENABLE_SCHEDULER` | Run the background push scheduler | `true` (in Docker) |
| `WSDOT_CACHE_SECONDS` | Min seconds between WSDOT polls per route | `300` |
| `SETTINGS_PATH` | Where settings JSON is stored | `/app/data/settings.json` |
| `VESTABOARD_RW_KEY` | Default Vestaboard Read/Write key (optional) | `` |
| `DISCORD_WEBHOOK_URL` | If set, logs each API request (caller IP + user-agent) to Discord (optional) | `` |

See `.env.template` for the full list, including Let's Encrypt and site-URL options
used by the from-source deployment.

---

## API endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Control panel (HTML) |
| `GET /api/trmnl?route_id=&direction=` | JSON payload for TRMNL polling plugins |
| `GET /api/ferry-status?route_id=` | Raw ferry status JSON |
| `GET\|POST /api/vestaboard?route_id=` | Push current status to a Vestaboard (`preview=1` returns the character grid without sending) |
| `GET /webhook?route_id=` | E-ink-formatted HTML |
| `GET /health` | Health check |

Per-request overrides `wsdot_key`, `vestaboard_key`, and `vestaboard_url` (query string
or JSON body) let the UI test with keys entered in the browser.

```bash
# JSON for a TRMNL polling plugin
curl "http://localhost:5050/api/trmnl?route_id=sea-bi&direction=Seattle"

# Preview a Vestaboard grid without sending
curl "http://localhost:5050/api/vestaboard?route_id=sea-bi&preview=true"
```

---

## Other ways to run

### Pre-built image (GHCR)

Every GitHub Release builds and pushes a container image via
[`.github/workflows/publish.yml`](.github/workflows/publish.yml):

```
ghcr.io/cdibona/ferrynotifier:latest    # newest release
ghcr.io/cdibona/ferrynotifier:0.8.4     # a specific version
```

If the package is private, log in first with a token that has `read:packages`:

```bash
echo "$GHCR_PAT" | docker login ghcr.io -u <github-username> --password-stdin
```

### Build the image yourself

```bash
docker build -f deployment/Dockerfile -t ferrynotifier .
docker run -p 5050:5050 -e WSDOT_API_KEY=your_key_here \
  -v "$HOME/.ferrynotifier:/app/data" ferrynotifier
```

### From source

Requires Python 3.8+.

```bash
git clone https://github.com/cdibona/FerryNotifier.git
cd FerryNotifier
pip install -r web/requirements.txt
cp .env.template .env         # add your WSDOT_API_KEY
python web/app.py             # dev server on http://localhost:5050
```

For production, run behind Gunicorn + nginx and manage it with systemd. Sample
[`deployment/ferrynotifier.service`](deployment/ferrynotifier.service),
[`deployment/nginx.conf.example`](deployment/nginx.conf.example), and a Let's Encrypt
helper are included — see **[INSTALL.md](INSTALL.md)** for the full walkthrough.

```bash
cd web && gunicorn -w 4 -b 0.0.0.0:5050 app:app
```

### Updating without losing settings

```bash
./deployment/update.sh        # pull latest, recreate the container, keep the data volume
# override defaults if needed:
FERRY_DATA=/opt/ferry-data FERRY_PORT=8080 ./deployment/update.sh
```

The app prints a loud warning at startup if `/app/data` is not a mounted volume.

---

## Development

```bash
pip install -r web/requirements.txt
python -m pytest web/test_app.py      # run the tests
FLASK_DEBUG=True python web/app.py     # hot-reload dev server
./deployment/run.sh                    # or the quick-start script
```

Continuous integration ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the
test suite on every push; publishing a Release builds and pushes the container image.
See [TESTING.md](TESTING.md) for more.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| **"API key not configured"** | Set `WSDOT_API_KEY` (env or UI); confirm the key is active. |
| **"Failed to fetch ferry data"** | Check connectivity and that your WSDOT key is valid. |
| **Settings disappear after an update** | You didn't reuse the `/app/data` mount — always update via `deployment/update.sh` or Compose. |
| **TRMNL device shows a cropped / partial layout** | Paste the per-layout markup into each matching tab (see [Connecting devices](#connecting-devices)); re-save and force-refresh in TRMNL. |
| **Port 5050 in use** | Change `FLASK_PORT`, or free the port. |
| **nginx 502** | Ensure the service is running (`systemctl status ferrynotifier`) and the proxy port matches. |

Logs: `docker logs -f ferrynotifier` (Docker) or `journalctl -u ferrynotifier -f` (systemd).

---

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

- [WSDOT](https://www.wsdot.wa.gov/ferries/api/) for the Ferries API
- [TRMNL](https://usetrmnl.com/) for the e-ink platform
- [Vestaboard](https://www.vestaboard.com/) for the split-flap API
- The Washington State Ferry system for getting us across the water
