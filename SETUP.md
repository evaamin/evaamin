# Kaggle exploration badges → GitHub README (auto-updating)

## What this does

A GitHub Action runs on a schedule, fetches your public Kaggle profile page,
pulls out your "earned by exploration" achievement badges (Community Member,
course completions, tenure badges, etc.), renders them as an SVG, and commits
that SVG back into your repo. Your README just points at the file, so it
updates itself whenever new badges land and the Action next runs.

## Important caveat, read this first

Kaggle has no official public API for this badge data. This script works by
parsing JSON that Kaggle embeds in the profile page's HTML for its own
frontend to use — the same technique the existing medal-badge tools
(road-to-kaggle-grandmaster, kaggle-profile-card) rely on. That means:

- It could break if Kaggle changes their page structure. If it does, re-run
  the script with `--debug` and it will dump the raw JSON it found into
  `kaggle_debug_blobs.json` so the parsing logic can be patched.
- I was not able to test this against the live kaggle.com site myself (my
  environment can't reach that domain), so treat the first run as a trial —
  check the Action's log output and the resulting SVG, and let me know if it
  comes back with zero badges found so I can adjust it with you.

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
5. Commit and push. Then go to the **Actions** tab, select "Update Kaggle
   badges," and click **Run workflow** to trigger it manually the first time
   rather than waiting for the daily schedule.
6. Check the run log. If it succeeds, `kaggle-badges.svg` will appear at the
   root of your repo.

## If it finds zero badges

Run it with debug mode to see what Kaggle actually sent back:

```bash
python scripts/fetch_and_render.py --username evanka1 --out kaggle-badges.svg --debug
```

This writes `kaggle_debug_blobs.json`. Share that file's content (or the
relevant chunk) and the parsing logic in `find_badge_lists` /
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
