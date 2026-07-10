#!/usr/bin/env python3
import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "portfolio-projects.json"


def request_json(base_url, path, token, query=None):
    url = base_url.rstrip("/") + path
    if query:
        url += "?" + urllib.parse.urlencode(query)

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"token {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def paginated(base_url, path, token, query=None):
    page = 1
    results = []
    while True:
        page_query = {"page": page, "limit": 50}
        page_query.update(query or {})
        chunk = request_json(base_url, path, token, page_query)
        if not chunk:
            return results
        results.extend(chunk)
        if len(chunk) < 50:
            return results
        page += 1


def repo_slug(repo):
    return repo["name"].lower()


def public_repo_url(repo):
    return repo.get("html_url") or repo.get("clone_url", "").removesuffix(".git")


def infer_stack(repo):
    language = repo.get("language")
    topics = repo.get("topics") or []
    stack = []
    if language:
        stack.append(language)
    stack.extend(topic for topic in topics if topic not in stack)
    return stack


def aliases(project):
    return {item.lower() for item in project.get("gitea_aliases", [])}


def match_slug(by_slug, repo):
    slug = repo_slug(repo)
    if slug in by_slug:
        return slug

    for project_slug, project in by_slug.items():
        if slug in aliases(project):
            return project_slug

    return slug


def merge_repo(existing, repo, preserve_manual_url=False):
    merged = dict(existing)
    merged.setdefault("slug", repo_slug(repo))
    merged.setdefault("name", repo["name"])
    merged.setdefault("status", "review")
    merged.setdefault("visibility", "candidate")
    merged.setdefault("show_on_profile", False)
    merged.setdefault("show_on_cv", False)
    merged.setdefault("source", "gitea")
    merged.setdefault("focus", repo.get("language") or "Project")
    merged.setdefault("summary", repo.get("description") or "Project imported from Gitea for review.")
    merged.setdefault("cv_summary", merged["summary"])
    merged.setdefault("highlights", [])
    merged.setdefault("priority", 999)
    merged.setdefault("notes", "")

    if not preserve_manual_url or not merged.get("repo_url"):
        merged["repo_url"] = public_repo_url(repo)
    if infer_stack(repo):
        merged["stack"] = infer_stack(repo)
    merged["gitea"] = {
        "owner": repo["owner"]["login"],
        "name": repo["name"],
        "full_name": repo["full_name"],
        "private": repo.get("private", False),
        "fork": repo.get("fork", False),
        "updated_at": repo.get("updated_at", ""),
    }
    return merged


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("GITEA_BASE_URL", ""))
    parser.add_argument("--username", default=os.environ.get("GITEA_USERNAME", ""))
    parser.add_argument("--token", default=os.environ.get("GITEA_TOKEN", ""))
    args = parser.parse_args()

    if not args.base_url or not args.username:
        raise SystemExit(
            "Set GITEA_BASE_URL and GITEA_USERNAME, or pass --base-url and --username."
        )

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    by_slug = {project["slug"]: project for project in data["projects"]}

    repos = []
    if args.token:
        repos.extend(paginated(args.base_url, "/api/v1/user/repos", args.token))
    repos.extend(paginated(args.base_url, f"/api/v1/users/{args.username}/repos", args.token))

    unique_repos = {}
    for repo in repos:
        slug = repo_slug(repo)
        unique_repos[repo["full_name"]] = repo

    for repo in unique_repos.values():
        slug = match_slug(by_slug, repo)
        by_slug[slug] = merge_repo(by_slug.get(slug, {}), repo)

    data["projects"] = sorted(by_slug.values(), key=lambda project: project.get("priority", 999))
    data["updated_at"] = datetime.now(timezone.utc).date().isoformat()
    DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Imported {len(unique_repos)} Gitea repositories into {DATA_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
