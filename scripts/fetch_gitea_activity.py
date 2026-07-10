#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "gitea-activity.json"
ZONE01_PATH = ROOT / "data" / "zone01.json"


def default_start_date():
    if ZONE01_PATH.exists():
        data = json.loads(ZONE01_PATH.read_text(encoding="utf-8"))
        if data.get("joined_at"):
            return data["joined_at"]
    return "2026-01-07"


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def daterange(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def normalize_base_url(base_url, username):
    parsed = urllib.parse.urlparse(base_url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Gitea URL must include http:// or https://")

    path_parts = [part for part in parsed.path.split("/") if part]
    if username and path_parts and path_parts[-1].lower() == username.lower():
        path_parts = path_parts[:-1]

    normalized_path = "/" + "/".join(path_parts) if path_parts else ""
    return urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, normalized_path.rstrip("/"), "", "", "")
    )


def candidate_base_urls(base_url, username):
    parsed = urllib.parse.urlparse(base_url.strip())
    normalized = normalize_base_url(base_url, username)
    root = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    return list(dict.fromkeys(candidate for candidate in [normalized, root] if candidate))


def request_json(base_url, path, token, query=None):
    url = base_url.rstrip("/") + path
    if query:
        url += "?" + urllib.parse.urlencode(query)

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"token {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


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


def clean_http_message(error):
    message = error.read().decode("utf-8", errors="replace").strip()
    if message.lstrip().lower().startswith(("<!doctype", "<html")):
        return "Response was HTML, so this may be the wrong Gitea base URL."
    return message[:500]


def endpoint(base_url, path, token, query=None, required=True):
    try:
        return paginated(base_url, path, token, query)
    except urllib.error.HTTPError as error:
        if error.code == 404 and not required:
            return []
        message = clean_http_message(error)
        if error.code == 403 and "Only signed in user is allowed" in message:
            raise RuntimeError(
                "Zone01 Gitea requires a token for API access. Add GITEA_TOKEN as a GitHub "
                "repository secret, or pass --token locally."
            ) from error
        raise RuntimeError(
            f"Gitea API request failed with HTTP {error.code} for {base_url.rstrip('/')}{path}. {message}"
        ) from error


def collect_repos(base_url, username, token):
    repos = []
    if token:
        repos.extend(endpoint(base_url, "/api/v1/user/repos", token, required=False))
    repos.extend(endpoint(base_url, f"/api/v1/users/{username}/repos", token, required=not repos))

    unique = {}
    for repo in repos:
        unique[repo["full_name"]] = repo
    return list(unique.values())


def commit_author_matches(commit, username):
    lower_username = username.lower()
    for key in ("author", "committer"):
        identity = commit.get("commit", {}).get(key) or {}
        raw_user = commit.get(key) or {}
        candidates = [
            identity.get("name", ""),
            identity.get("email", ""),
            raw_user.get("login", "") if isinstance(raw_user, dict) else "",
            raw_user.get("username", "") if isinstance(raw_user, dict) else "",
            raw_user.get("full_name", "") if isinstance(raw_user, dict) else "",
        ]
        if any(lower_username in str(candidate).lower() for candidate in candidates if candidate):
            return True
    return False


def commit_date(commit):
    for key in ("author", "committer"):
        value = commit.get("commit", {}).get(key, {}).get("date")
        if value:
            return value[:10]
    return ""


def fetch_repo_commits(base_url, repo, username, token, start, end):
    owner = urllib.parse.quote(repo["owner"]["login"], safe="")
    name = urllib.parse.quote(repo["name"], safe="")
    path = f"/api/v1/repos/{owner}/{name}/commits"
    query = {
        "since": f"{start.isoformat()}T00:00:00Z",
        "until": f"{end.isoformat()}T23:59:59Z",
    }
    commits = endpoint(base_url, path, token, query, required=False)
    return [commit for commit in commits if commit_author_matches(commit, username)]


def streaks(daily):
    best = 0
    current = 0
    run = 0
    for item in daily:
        if item["count"] > 0:
            run += 1
            best = max(best, run)
        else:
            run = 0
    for item in reversed(daily):
        if item["count"] > 0:
            current += 1
        else:
            break
    return current, best


def build_activity(base_url, username, token, start, end):
    repos = collect_repos(base_url, username, token)
    daily_counts = Counter()
    repo_counts = Counter()
    repo_days = defaultdict(set)
    scanned = 0

    for repo in repos:
        commits = fetch_repo_commits(base_url, repo, username, token, start, end)
        scanned += 1
        if not commits:
            continue
        full_name = repo["full_name"]
        for commit in commits:
            day = commit_date(commit)
            if not day:
                continue
            daily_counts[day] += 1
            repo_counts[full_name] += 1
            repo_days[full_name].add(day)

    daily = [{"date": day.isoformat(), "count": daily_counts.get(day.isoformat(), 0)} for day in daterange(start, end)]
    current_streak, best_streak = streaks(daily)
    repositories = []
    repo_lookup = {repo["full_name"]: repo for repo in repos}
    for name, count in repo_counts.most_common(20):
        repo = repo_lookup.get(name, {})
        repositories.append(
            {
                "name": name,
                "url": repo.get("html_url", ""),
                "commits": count,
                "push_days": len(repo_days[name]),
                "private": bool(repo.get("private", False)),
            }
        )

    active_days = sum(1 for item in daily if item["count"] > 0)
    return {
        "username": username,
        "name": username,
        "source": "zone01_gitea_api",
        "base_url": base_url,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_commits": sum(daily_counts.values()),
        "total_contributions": sum(daily_counts.values()),
        "active_days": active_days,
        "push_days": sum(len(days) for days in repo_days.values()),
        "current_streak": current_streak,
        "best_streak": best_streak,
        "repositories_scanned": scanned,
        "repositories_with_commits": len(repo_counts),
        "daily": daily,
        "repositories": repositories,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch Zone01 Gitea commit activity.")
    parser.add_argument("--base-url", default=os.getenv("GITEA_BASE_URL", "https://platform.zone01.gr/git"))
    parser.add_argument("--username", default=os.getenv("GITEA_USERNAME", "kchatzian"))
    parser.add_argument("--token", default=os.getenv("GITEA_TOKEN", ""))
    parser.add_argument("--start-date", default=os.getenv("GITEA_ACTIVITY_START", default_start_date()))
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--output", default=str(DATA_PATH))
    args = parser.parse_args()

    if not args.token:
        raise SystemExit("GITEA_TOKEN is required because Zone01 Gitea repositories are private.")

    start = parse_date(args.start_date)
    end = parse_date(args.end_date)
    errors = []
    for candidate in candidate_base_urls(args.base_url, args.username):
        try:
            data = build_activity(candidate, args.username, args.token, start, end)
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(
                f"Wrote {output} with {data['total_commits']} commits from "
                f"{data['repositories_with_commits']} repositories"
            )
            return
        except Exception as error:
            errors.append(str(error))

    raise RuntimeError("Could not read Gitea activity. " + " ".join(errors))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
