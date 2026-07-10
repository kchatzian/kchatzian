#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "github-activity.json"
ZONE01_PATH = ROOT / "data" / "zone01.json"


def iso_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def default_start_date():
    if ZONE01_PATH.exists():
        data = json.loads(ZONE01_PATH.read_text(encoding="utf-8"))
        if data.get("joined_at"):
            return data["joined_at"]
    return "2026-01-07"


def daterange(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


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


def fetch_graphql(username, token, start, end):
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        login
        name
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
          commitContributionsByRepository(maxRepositories: 20) {
            repository {
              nameWithOwner
              url
            }
            contributions {
              totalCount
            }
          }
        }
      }
    }
    """
    payload = json.dumps(
        {
            "query": query,
            "variables": {
                "login": username,
                "from": f"{start.isoformat()}T00:00:00Z",
                "to": f"{end.isoformat()}T23:59:59Z",
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "kchatzian-profile-activity",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub GraphQL failed with HTTP {exc.code}: {body}") from exc

    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"]))

    user = result["data"]["user"]
    if not user:
        raise RuntimeError(f"GitHub user not found: {username}")

    collection = user["contributionsCollection"]
    counts = {}
    for week in collection["contributionCalendar"]["weeks"]:
        for day in week["contributionDays"]:
            counts[day["date"]] = int(day["contributionCount"])

    daily = [{"date": day.isoformat(), "count": counts.get(day.isoformat(), 0)} for day in daterange(start, end)]
    current_streak, best_streak = streaks(daily)
    repos = sorted(
        [
            {
                "name": item["repository"]["nameWithOwner"],
                "url": item["repository"]["url"],
                "commits": int(item["contributions"]["totalCount"]),
            }
            for item in collection["commitContributionsByRepository"]
        ],
        key=lambda item: item["commits"],
        reverse=True,
    )

    total_commits = int(collection["totalCommitContributions"])
    total_contributions = int(collection["contributionCalendar"]["totalContributions"])
    active_days = sum(1 for item in daily if item["count"] > 0)
    return {
        "username": user["login"],
        "name": user.get("name") or user["login"],
        "source": "github_graphql",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_commits": total_commits,
        "total_contributions": total_contributions,
        "restricted_contributions": int(collection["restrictedContributionsCount"]),
        "active_days": active_days,
        "current_streak": current_streak,
        "best_streak": best_streak,
        "daily": daily,
        "repositories": repos,
    }


def fetch_from_local_git(username, start, end):
    command = [
        "git",
        "log",
        "--all",
        "--date=short",
        "--pretty=format:%ad",
        f"--since={start.isoformat()}",
        f"--until={end.isoformat()} 23:59:59",
    ]
    output = subprocess.check_output(command, cwd=ROOT, text=True)
    counts = Counter(line.strip() for line in output.splitlines() if line.strip())
    daily = [{"date": day.isoformat(), "count": counts.get(day.isoformat(), 0)} for day in daterange(start, end)]
    current_streak, best_streak = streaks(daily)
    total = sum(item["count"] for item in daily)
    return {
        "username": username,
        "name": username,
        "source": "local_git_preview",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_commits": total,
        "total_contributions": total,
        "restricted_contributions": 0,
        "active_days": sum(1 for item in daily if item["count"] > 0),
        "current_streak": current_streak,
        "best_streak": best_streak,
        "daily": daily,
        "repositories": [{"name": "kchatzian/kchatzian", "url": "https://github.com/kchatzian/kchatzian", "commits": total}],
    }


def fetch_public_commit_search(username, start, end):
    counts = Counter()
    repos = Counter()
    page = 1
    total_count = 0
    while True:
        query = f"author:{username} committer-date:{start.isoformat()}..{end.isoformat()}"
        url = (
            "https://api.github.com/search/commits?"
            + urllib.parse.urlencode({"q": query, "per_page": "100", "page": str(page)})
        )
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github.cloak-preview+json",
                "User-Agent": "kchatzian-profile-activity",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if page == 1:
            total_count = int(payload.get("total_count", 0))
        items = payload.get("items", [])
        if not items:
            break
        for item in items:
            commit_date = item.get("commit", {}).get("author", {}).get("date", "")[:10]
            if commit_date:
                counts[commit_date] += 1
            repo_name = item.get("repository", {}).get("full_name")
            if repo_name:
                repos[repo_name] += 1
        if len(items) < 100 or page >= 10:
            break
        page += 1

    daily = [{"date": day.isoformat(), "count": counts.get(day.isoformat(), 0)} for day in daterange(start, end)]
    current_streak, best_streak = streaks(daily)
    repo_items = [
        {
            "name": name,
            "url": f"https://github.com/{name}",
            "commits": count,
        }
        for name, count in repos.most_common(20)
    ]
    total = sum(item["count"] for item in daily)
    return {
        "username": username,
        "name": username,
        "source": "github_public_search",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "total_commits": total,
        "total_contributions": total,
        "restricted_contributions": 0,
        "active_days": sum(1 for item in daily if item["count"] > 0),
        "current_streak": current_streak,
        "best_streak": best_streak,
        "daily": daily,
        "repositories": repo_items,
        "search_total_count": total_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch GitHub contribution activity for the profile README.")
    parser.add_argument("--username", default=os.getenv("GITHUB_USERNAME", "kchatzian"))
    parser.add_argument("--start-date", default=os.getenv("GITHUB_ACTIVITY_START", default_start_date()))
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"))
    parser.add_argument("--output", default=str(DATA_PATH))
    parser.add_argument("--allow-local-preview", action="store_true")
    args = parser.parse_args()

    start = iso_date(args.start_date)
    end = iso_date(args.end_date)
    if start > end:
        raise SystemExit("start date cannot be after end date")

    if args.token:
        data = fetch_graphql(args.username, args.token, start, end)
    else:
        try:
            data = fetch_public_commit_search(args.username, start, end)
        except Exception:
            if not args.allow_local_preview:
                raise
            data = fetch_from_local_git(args.username, start, end)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
