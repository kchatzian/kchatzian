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

## GitHub Actions Update

For scheduled updates, add this repository secret:

```text
ZONE01_JWT
```

The workflow `.github/workflows/update-zone01-card.yml` runs every day and regenerates the card.

Do not commit tokens, cookies, passwords, or browser storage files.
