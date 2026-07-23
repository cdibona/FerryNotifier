---
name: verify-ui
description: Prove a FerryNotifier UI or rendering change actually works by deploying it to the running instance and driving the real control panel in a browser with a screenshot. Use before telling the user a UI change is done, or when they say a change "didn't work" / "isn't showing up".
---

# Verify a change on the real UI

The recurring failure on this project is claiming a UI change works after testing something
that isn't what the user looks at. A fresh throwaway container, a unit test, or a rendered
template string all prove nothing: **the live container usually runs an older image than the
working tree.**

A change is verified when a screenshot of the user's actual instance shows the thing they
asked for, doing the action they described.

## 0. Ask first if they're mid-session

Deploying restarts the container. If the user may be editing boards right now, say what you're
about to do and wait. Read-only inspection needs no permission:

```bash
docker inspect ferrynotifier --format '{{json .Mounts}}'
docker logs --tail 50 ferrynotifier
```

## 1. Test, then deploy

```bash
ENABLE_SCHEDULER=false python3 -m pytest web/test_app.py -q
```

The instance runs the **published GHCR image**, not your working tree. So either cut a release
first (see `/release`) and then:

```bash
./deployment/update.sh
```

or, to check an unreleased change, build and run the local tree with the same data mount:

```bash
docker build -t ferrynotifier:wip -f deployment/Dockerfile .
docker rm -f ferrynotifier-wip 2>/dev/null || true
docker run -d --name ferrynotifier-wip -p 5051:5050 \
  --env-file .env -v "$HOME/.ferrynotifier:/app/data" ferrynotifier:wip
```

Never `docker run` a new image at the real container's name without `-v` on the data dir —
that is the settings-loss bug.

Confirm it's up and serving the version you expect:

```bash
curl -s http://127.0.0.1:5050/health
curl -s http://127.0.0.1:5050/api/info
```

## 2. Drive the real UI

Load the `claude-in-chrome` skill and open the instance URL (in `.claude/CLAUDE.local.md`).
Then **perform the user's exact steps** — not an approximation:

- If they said "click Vestaboard and the sleep message isn't in the box", click the Vestaboard
  tab and screenshot the sleep box.
- If they said "pick a capture from history and nothing changes", pick one from the dropdown
  and screenshot the result.
- If it's a TRMNL layout, check **each** layout tab at its real size — Full 800×480,
  Half-H 800×240, Half-V 400×480, Quadrant 400×240. TRMNL crops rather than reflows, so a
  correct Full tab tells you nothing about Quadrant.

Hard-reload the page (cache-bypass) before looking — a stale tab runs the old JS.

## 3. Look at the screenshot

Actually read it. If the element is missing, clipped, or shows `--`, the change is not done —
fix it and repeat. For `--` values in TRMNL, suspect nested merge variables (see `CLAUDE.md`).

## 4. Report

Say what you clicked, what the screenshot showed, and paste it. If something couldn't be
verified from here — a physical TRMNL device render, a real Vestaboard push — say so plainly
rather than implying it was checked.

Clean up any `-wip` container, and remind the user to reload their own tab.
