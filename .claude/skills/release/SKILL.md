---
name: release
description: Cut a FerryNotifier release — run tests, commit, push main, create the GitHub release, watch the GHCR publish action, and confirm the image is pullable. Use when asked to "cut a release", "push to main and release", "ship it", or to publish a new version.
---

# Cut a FerryNotifier release

The whole flow, end to end. Do not stop at "release created" — a release is not done until
the `publish.yml` action is green and the image exists on GHCR.

## 1. Pre-flight

```bash
git status --short
git fetch -q --tags origin
git log --oneline -1 HEAD; git log --oneline -1 origin/main
gh release list --limit 3
```

Pick the next version from **`gh release list`**, not from `git tag`. `gh release create`
creates the tag server-side, so local tags run behind (they stopped at v0.7.1 while releases
were at v0.8.5). Semver: patch for fixes/docs, minor for new capability.

## 2. Test

```bash
ENABLE_SCHEDULER=false python3 -m pytest web/test_app.py -q
```

Must pass before anything is pushed. `ENABLE_SCHEDULER=false` keeps the background push loop
from starting and hitting real devices.

If the change touches `TRMNL_MK_*`, confirm `assets/trmnl-markup.liquid` was updated to match.

## 3. Commit and push

Write a real commit message — what changed and why, not a version bump note. Use a heredoc so
the body survives:

```bash
git add -A
git commit -q -F - <<'EOF'
<subject line under ~72 chars>

<body: what changed, why, and how it was verified>

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
git push origin main
```

Pushing straight to `main` is this repo's established flow, but the auto-mode classifier may
block it. **If blocked, stop and tell the user** — do not route around it with a different
command.

## 4. Create the release

```bash
gh release create vX.Y.Z \
  --target main \
  --title "vX.Y.Z — <short summary>" \
  --notes "$(cat <<'EOF'
## What's new
- ...

## Update
```
./deployment/update.sh   # applies it, keeps your settings
```
EOF
)"
```

Notes should be user-facing: what they'll see, not which functions moved. If a release fixes
something the user reported, say so in their terms.

## 5. Watch the build

`publish.yml` runs tests, then builds and pushes `ghcr.io/cdibona/ferrynotifier:X.Y.Z` and
`:latest`, baking `APP_VERSION` from the tag.

```bash
sleep 12
RID=$(gh run list --workflow=publish.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RID" --exit-status 2>&1 | tail -3
gh run view "$RID" --json conclusion -q .conclusion
```

If it fails, read the logs and fix it — a red action means the release is broken, and saying
"released" at that point is wrong.

## 6. Confirm the image

```bash
gh auth token | docker login ghcr.io -u cdibona --password-stdin >/dev/null 2>&1
docker pull ghcr.io/cdibona/ferrynotifier:X.Y.Z 2>&1 | tail -1
```

## 7. Report

Tell the user the version, the release URL, and the pull command. **Do not run
`./deployment/update.sh` against their live instance as part of this** — deploying interrupts
whatever they're doing in the UI. Offer it; let them say when.
