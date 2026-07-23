# FerryNotifier — working notes for Claude

Flask app that reads Washington State Ferry status from the WSDOT API and pushes it to
TRMNL e-ink devices and Vestaboard split-flap displays. Public, MIT,
`github.com/cdibona/FerryNotifier`.

## Shell conventions

- **Your cwd is already the repo root. Never prefix commands with `cd <repo root>`.** Use
  paths relative to the root (`web/app.py`, `deployment/update.sh`). A `cd` inside a compound
  command triggers a permission prompt for no benefit.
- Run tests with `ENABLE_SCHEDULER=false python3 -m pytest web/test_app.py -q`. The
  `ENABLE_SCHEDULER=false` matters — without it the test process starts the background push
  loop and can hit real devices.
- Refer to host paths as `$HOME/...` or `~/...`, never as an absolute path containing a
  username. This repo is public.

## Layout

Almost everything is `web/app.py` (~3.3k lines), in this order:

| Lines (approx) | What |
|---|---|
| 1–310 | config, `APP_VERSION`, timezone helpers, Discord notify |
| 313–520 | `TRMNL_MK_*` Liquid markup constants, one per device layout |
| 520–1630 | the control-panel HTML/CSS/JS, inline as Python strings |
| 1634–1970 | WSDOT fetch, route/direction logic, delay parsing |
| 1973–2290 | Vestaboard encoding, board capture history |
| 2287–2400 | TRMNL webhook push, merge variables |
| 2400–2980 | settings normalization/persistence, Flask routes |
| 2980–3290 | push scheduler, quiet hours, startup persistence check |

`assets/trmnl-markup.liquid` is a standalone copy of the markup and must be kept in sync
with the `TRMNL_MK_*` constants when they change.

## Deployment

- **Container:** name `ferrynotifier`, image `ghcr.io/cdibona/ferrynotifier:latest`,
  `--restart unless-stopped`, host port 5050.
- **Durable data:** bind mount `$HOME/.ferrynotifier` → `/app/data`
  (`settings.json`, `schedule_state.json`, `history/`). Override with `FERRY_DATA`.
- **HTTPS** is typically fronted by Tailscale serve or the nginx example in
  `deployment/nginx.conf.example`; the app itself only listens on 5050.

### Settings loss — do not re-introduce this bug

Updating with a bare `docker run <newimage>` wipes saved targets, keys, and schedules.
The Dockerfile deliberately has **no `VOLUME` directive** (it created a throwaway anonymous
volume on every unmounted run). Always update via `./deployment/update.sh`, which re-mounts
the data directory. The app warns at startup if `/app/data` isn't a real mount.

Note the inconsistency: `deployment/docker-compose.ghcr.yml` uses a named volume
(`ferry-data`), while `update.sh` uses the `$HOME/.ferrynotifier` bind mount. They are
different stores — don't switch a running deployment between them without migrating the data.

## Treat a running instance as production

Whoever is running this is often actively editing boards in the UI.

- Verify **read-only** by default: inspect the data dir's `settings.json`, `docker inspect`
  the mount, `docker logs ferrynotifier`. Don't restart, don't run `update.sh`, and don't
  read or push a real Vestaboard mid-session unless asked.
- **Never claim a UI change works until it has been tested on the actual running instance**,
  not a throwaway test container. A live container often runs an older image than the working
  tree, so a green test on a fresh container proves nothing about what the user sees.
  Build → deploy via `update.sh` → drive the real UI → look at a screenshot of the exact
  action described. See `/verify-ui`.
- After deploying, remind them to reload the tab — their open page still runs the old JS.

## TRMNL rendering constraints

Both of these are device-only bugs that a browser preview will not reveal.

1. **Webhook markup only reliably reaches TOP-LEVEL merge variables.** Nested access like
   `{{ status.time_str }}` renders blank on the device even though the payload contains the
   object and `{{ route_name }}` works. `ferry_merge_variables()` therefore flattens fields
   to top-level names (`has_status`, `dir_line`, `dir_short`, `time_str`, `spaces`, `delay`);
   the nested `status` object exists only for the polling/JSON API. This was the
   "`-- next departure` / `-- spaces`" bug.
2. **TRMNL renders each layout at its own viewport and CROPS overflow — CSS media queries do
   not reflow one template across layouts.** One responsive Shared template clips on
   half/quadrant. Ship per-layout markup: `TRMNL_MK_FULL` (800×480), `TRMNL_MK_HALF_H`
   (800×240), `TRMNL_MK_HALF_V` (400×480), `TRMNL_MK_QUADRANT` (400×240); the Shared tab is a
   stub. `TRMNL_MK_SHARED` is the kept-as-alternative responsive one.

Also: **in Liquid an empty string is truthy** (only `nil`/`false` are falsy), so
`{% if delay %}` requires `delay` to be `None`, not `""`, when there is no delay.

Vestaboard: check `vb_dimensions(model)` before assuming grid size — Note is 3 rows × 15 cols,
Flagship is 6 × 22, and markup that fits one clips on the other.

## Releases

Use `/release`. The short version: tests → commit → push `main` → `gh release create vX.Y.Z`
(this creates the tag remotely) → the `publish.yml` action builds and pushes
`ghcr.io/cdibona/ferrynotifier:X.Y.Z` and `:latest` with `APP_VERSION` baked from the tag.

- Local tags go stale because `gh release create` tags server-side — `git fetch --tags`
  before picking the next version number.
- Pushing directly to `main` is the established flow here, but the auto-mode classifier will
  block it. If blocked, say so and ask rather than routing around it.

## Secrets and public-repo hygiene

Real WSDOT and Vestaboard keys live in `.env` (gitignored, and denied to Read in
`.claude/settings.json` so they can't leak into a transcript). This repo is public: never
write keys, hostnames, static IPs, or local usernames into tracked files. The
`deployment/*.service` units use a generic `ferrynotifier` service user under
`/opt/FerryNotifier` for exactly this reason.

Host-specific details for this machine, if present, are in the gitignored file imported below.

@.claude/CLAUDE.local.md
