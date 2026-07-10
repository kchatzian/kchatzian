# Zone01 Automation

The profile README uses `data/zone01.json` as the source for the Zone01 progress card.

## Local Update

When Firefox is logged in to Zone01 on this machine:

```bash
python3 scripts/fetch_zone01_progress.py
python3 scripts/generate_zone01_card.py
git add data/zone01.json assets/zone01-progress.svg
git commit -m "Update Zone01 progress"
git push
```

The fetch script reads the existing Zone01 JWT from Firefox localStorage and does not print it.
If Firefox creates a new profile, the script searches the common Firefox profile locations automatically.

## GitHub Actions Update

For scheduled updates, add this repository secret:

```text
ZONE01_JWT
```

For long-term automatic updates, add this repository secret too:

```text
PROFILE_REPO_PAT
```

`PROFILE_REPO_PAT` allows the workflow to rotate `ZONE01_JWT` after every successful token refresh.

The workflow `.github/workflows/update-zone01-card.yml` runs every day and regenerates the card.

If the scheduled workflow fails, refresh the `ZONE01_JWT` repository secret with a token from a browser session that is currently logged in to Zone01. Without `PROFILE_REPO_PAT`, the workflow can update once, but it cannot save the refreshed token back to GitHub, so the secret may expire again.

Do not commit tokens, cookies, passwords, or browser storage files.
