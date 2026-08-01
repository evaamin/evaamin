# Kaggle exploration badges → GitHub README (auto-updating)

## What this does

Fetches your public Kaggle profile page, pulls out your "earned by
exploration" achievement badges (Community Member, course completions,
tenure badges, etc.), renders them as an SVG, and commits that SVG into your
repo. Your README just points at the file, so it updates whenever you
regenerate it and push.

## Important caveat, read this first

Kaggle has no official public API for this badge data (confirmed by checking
the full source of the official `kaggle` API client — no user/profile/badge
endpoint exists anywhere in it). This script works by parsing JSON that
Kaggle embeds in the profile page's HTML for its own frontend to use — the
same technique the existing medal-badge tools (road-to-kaggle-grandmaster,
kaggle-profile-card) rely on. That means:

- It could break if Kaggle changes their page structure. If it does, re-run
  the script with `--debug` and it will dump the raw JSON it found into
  `kaggle_debug_blobs.json` so the parsing logic can be patched.
- **Kaggle blocks plain/anonymous scraping.** A request with no session
  cookie — whether from a GitHub Actions runner or a home connection — gets
  served a reCAPTCHA challenge page instead of the real profile, which
  `--debug` will show up as zero JSON blobs found. There's no official API
  to fall back on, so the fix is to send a real logged-in session's cookie
  (see below), not an automated CAPTCHA bypass.
- Because of that, this no longer runs on a daily schedule. The workflow is
  `workflow_dispatch`-only (manual trigger from the Actions tab), and the
  normal path is to regenerate the SVG **locally** with a cookie and push it
  yourself, since GitHub-hosted runners have no session to authenticate
  with and would just hit the same challenge page.

## Regenerating the badges locally

1. Log into kaggle.com in your browser.
2. Open DevTools → Network tab, reload the page, click any request to
   `kaggle.com`, and copy the full value of the `Cookie` request header.
3. Save it to a local file that is *not* committed (already covered by
   `.gitignore`):
   ```bash
   echo 'paste the cookie value here' > kaggle_cookie.txt
   ```
4. Run the script with `--cookie-file`:
   ```bash
   python scripts/fetch_and_render.py \
     --username evanka1 --out kaggle-badges.svg --theme dark \
     --cookie-file kaggle_cookie.txt
   ```
5. If it reports badges found, commit and push `kaggle-badges.svg`.
6. Kaggle session cookies expire — repeat this whenever you want to refresh
   the badges, or if a run comes back with zero badges again.

Never commit `kaggle_cookie.txt` or paste that cookie value anywhere public —
it's equivalent to your logged-in Kaggle session.

## Setup

1. Create a new repo (or use your existing profile README repo — the one
   named exactly `<your-github-username>/<your-github-username>`).
2. Copy `scripts/fetch_and_render.py` and `.github/workflows/kaggle-badges.yml`
   into it, preserving the folder structure.
3. In the workflow file, `--username evanka1` is already set to your Kaggle
   username. Change it if needed.
4. In your repo settings: **Settings → Actions → General → Workflow
   permissions → Read and write permissions**. This lets the Action commit
   the updated SVG back to the repo.
5. Commit and push.
6. The `update-badges` workflow itself is `workflow_dispatch`-only now — it
   has no cookie to authenticate with, so running it from the Actions tab
   will just hit the same reCAPTCHA wall as an unauthenticated local run.
   Follow "Regenerating the badges locally" above instead to actually
   produce `kaggle-badges.svg`, then commit and push it the normal way.

## If a run finds zero badges

That almost always means Kaggle served the reCAPTCHA challenge page instead
of the real profile (see the caveat above) — check `kaggle_debug_blobs.json`
from a `--debug` run; if it's `[]`, the cookie is missing, wrong, or
expired. If it's *not* empty but still finds zero badges, that's a genuine
page-structure change — share the file's content (or the chunk containing
"Community Member") and the parsing logic in `find_badge_lists` /
`looks_like_badge` in `fetch_and_render.py` can be adjusted to match
Kaggle's current structure.

## Add to your README

Once `kaggle-badges.svg` exists in your repo, reference it with the raw
GitHub URL so it always shows the latest committed version:

```markdown
![Kaggle badges](https://raw.githubusercontent.com/<your-github-username>/<repo-name>/main/kaggle-badges.svg)
```

Replace `<your-github-username>` and `<repo-name>` accordingly, and `main`
with your default branch name if different.
