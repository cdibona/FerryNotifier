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

Almost everything is `web/app.py` (~3.5k lines), in this order:

| Lines (approx) | What |
|---|---|
| 1–310 | config, `APP_VERSION`, timezone helpers, Discord notify |
| 313–525 | `TRMNL_MK_*` Liquid markup constants, one per device layout |
| 530–1855 | the control-panel HTML/CSS/JS, inline as Python strings |
| 1860–2070 | WSDOT fetch, route/direction logic, delay parsing |
| 2075–2210 | Vestaboard encoding, board capture history |
| 2214–2340 | per-board layout templates (sandboxed Jinja) |
| 2340–2610 | Vestaboard/TRMNL push, merge variables |
| 2610–3210 | settings normalization/persistence, Flask routes |
| 3213–3530 | push scheduler, quiet hours, startup persistence check |

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

The Read/Write API returns **409 Conflict when the message being sent is identical to what the
board already shows** — a no-op, not a failure. `send_to_vestaboard()` maps 409 to
`{"status": "unchanged"}`. This bites custom templates with no changing field: the built-in
Note layout puts a live `NO DELAYS @HH:MM` clock on row 3 so consecutive pushes always differ,
but a template like `{{ origin }}-{{ dest }} {{ time_short }}` / `SPACES: {{ spaces }}` renders
byte-identical whenever the data is steady (and during a WSDOT blackout every field is `--` /
`N/A`), so every push 409'd and the board looked frozen. The stale-data skip (above) already
avoids pushing the blackout frame; the 409 mapping keeps a steady-data repeat from surfacing as
an error.

## Vestaboard quiet hours and board templates

A board's own Quiet Hours (set in the Vestaboard app / web2.vestaboard.com) **drop incoming
messages**, and the Read/Write API cannot read or set them — it only does read message, send
message, get/set transition. So the pre-sleep message is pushed `quiet.sleep_lead_min`
minutes (default 3) *before* our quiet window's start time, and ferry pushes stop at that
same early moment so nothing overwrites the goodnight. `_in_quiet_hours()` implements the
shift; the wake time is not shifted.

The `terminalsailingspace` endpoint is the only source of drive-up space counts, and WSDOT
intermittently **omits busy terminals (Seattle, Bainbridge) from it even while it returns 200**
— not just on timeouts. Departure *times* therefore fall back through three sources in
`compute_direction_status()` via `time_source`: `sailingspace` (time + spaces) →
`schedule` (WSF `scheduletoday`, time only) → `vessels` (live `ScheduledDeparture`, time only).
The fallbacks give a real time but `spaces` is `None` (renders `N/A`). Only when **all three**
yield no upcoming departure and there's no space count is the status a true blackout.

`push_vestaboard_target()` guards a blackout with `_ferry_data_is_stale()` and returns
`{"skipped": reason}` instead of sending; the scheduler then leaves `last_push` untouched so
the board keeps its last good message and retries next tick (fetch is cached ~5 min, so retries
don't hammer WSDOT). "Stale" for a routed board means **both** the next departure (across all
three sources) and the spaces count are missing. Note `fetch_ferry_status` caches even a
partial read, so a gap persists in-app for up to the cache TTL after WSDOT recovers.
`push_trmnl_target()` has the same guard (a blackout would push a blank `--` TRMNL screen);
`ferry_merge_variables()` itself is left unguarded because the polling/JSON API should still
return data.

A board can override the built-in layout with `board['template']` — a sandboxed Jinja
template, one rendered line per board row (`LEFT | RIGHT` splits a row, anything else
centers). Two gotchas: the env uses `trim_blocks`/`lstrip_blocks` so an `{% if %}` on its
own line doesn't emit a blank row, and `BOARD_TEMPLATE_EXAMPLES` is **per model** because a
6-row flagship example loses its conditional line when truncated to a 3-row Note. Anything
new added to `board_template_context()` should be top-level and pre-formatted, and any new
call site of `format_vestaboard_message()` must pass `template=`.

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
