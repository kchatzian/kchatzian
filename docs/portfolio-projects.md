# Portfolio Project System

The public profile should show selected engineering signal, not every completed school step.
Use `data/portfolio-projects.json` as the source of truth and regenerate the README section with:

```bash
python3 scripts/generate_portfolio_section.py
```

## Current Profile Selection

| Project | Decision | Why |
| --- | --- | --- |
| groupie-tracker | Featured | Best complete Go web project: search, filters, geolocation, visualizations, and data handling. |
| net-cat | Featured | Strong systems/backend signal: TCP, concurrency, server/client behavior, terminal workflows. |
| lem-in | Featured | Strong algorithm signal: graph parsing, pathfinding, optimization, and movement scheduling. |
| push-swap | Selected | Good algorithm project after README polish and examples. |
| tetris-optimizer | Selected | Good backtracking/optimization project after README polish. |
| ascii-art-web-dockerize | Selected | Good supporting evidence for Go web and Docker basics. |

## Future Featured Project

`forum` should become the strongest portfolio project when it is stable, documented, and safe to publish.
Until then, keep it out of the profile and CV.

## Keep Private Or Low Priority

Small exercises, prompt/markdown projects, early CSS exercises, and duplicate school steps should stay out of the main portfolio unless there is a specific reason to show them.

## Gitea Import

The Gitea importer can fill repository URLs and metadata without overwriting the curated decisions. With `GITEA_TOKEN`, it also asks Gitea for repositories the authenticated user can access, which is the path for team projects owned by collaborators:

```bash
GITEA_BASE_URL="https://gitea.example.com" \
GITEA_USERNAME="kchatzian" \
GITEA_TOKEN="..." \
python3 scripts/fetch_gitea_projects.py
```

`GITEA_BASE_URL` can be the Gitea site root or your profile URL. For example, both `https://gitea.example.com` and `https://gitea.example.com/kchatzian` are accepted. Gitea exposes its REST API under `/api/v1`, with Swagger/OpenAPI documentation available on the instance at `/api/swagger` or `/swagger.v1.json`.

## Dashboard Plan

Start the local dashboard with:

```bash
GITEA_BASE_URL="https://gitea.example.com" \
GITEA_USERNAME="kchatzian" \
python3 scripts/portfolio_dashboard.py
```

Then open:

```text
http://127.0.0.1:8765
```

The dashboard reads `data/portfolio-projects.json` and exposes these controls:

| Control | Meaning |
| --- | --- |
| `show_on_profile` | Include in the GitHub profile README generated section. |
| `show_on_cv` | Include in a future generated CV project section. |
| `repo_url` | Link used by the generated profile section and future CV output. Leave empty for private or unfinished repositories. |
| `status` | `ready`, `polish`, `review`, or `not-ready`. |
| `visibility` | `featured`, `selected`, `candidate`, or `future-featured`. |
| `priority` | Sort order in public outputs. |

Use `Import from Gitea` to fill repository URLs automatically from the Gitea profile/API. Add a token in the dashboard form when you need private repositories or team repositories owned by collaborators. The token is used for that request and is not saved to the repository.

After editing the dashboard, use `Save + Regenerate` to update both the JSON file and the README generated section. Commit and push those file changes before expecting the public GitHub profile to change. The underlying command is:

```bash
python3 scripts/generate_portfolio_section.py
```

Later it can also generate a CV section from the `show_on_cv` projects.

## Link Policy

Use links for projects that are public, polished, and safe for a recruiter or collaborator to inspect. For private school repositories or unfinished work, keep the project in the list without a URL until there is a clean public mirror, demo, or write-up.

## Publishing Rule

Only feature a project when it has:

- A clean README
- Clear run instructions
- Safe public source
- A short explanation of what it demonstrates
- Screenshots or examples when useful
