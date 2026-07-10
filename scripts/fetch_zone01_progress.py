#!/usr/bin/env python3
import base64
import argparse
import json
import os
import shutil
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "zone01.json"
GRAPHQL_URL = "https://platform.zone01.gr/api/graphql-engine/v1/graphql"
REFRESH_URL = "https://platform.zone01.gr/api/auth/refresh"
DEFAULT_FIREFOX_STORAGE = (
    Path.home()
    / "snap/firefox/common/.mozilla/firefox/zcaxwznc.default/storage/default/"
    / "https+++platform.zone01.gr/ls/data.sqlite"
)
FIREFOX_STORAGE_GLOB = "*/storage/default/https+++platform.zone01.gr/ls/data.sqlite"
FIREFOX_PROFILE_ROOTS = (
    Path.home() / "snap/firefox/common/.mozilla/firefox",
    Path.home() / ".mozilla/firefox",
)


def snappy_decompress(data: bytes) -> bytes:
    index = 0
    shift = 0
    expected_length = 0

    while True:
        byte = data[index]
        index += 1
        expected_length |= (byte & 0x7F) << shift
        if byte < 128:
            break
        shift += 7

    output = bytearray()
    while index < len(data):
        tag = data[index]
        index += 1
        tag_type = tag & 0x03

        if tag_type == 0:
            length = tag >> 2
            if length < 60:
                length += 1
            else:
                length_size = length - 59
                length = int.from_bytes(data[index : index + length_size], "little") + 1
                index += length_size
            output.extend(data[index : index + length])
            index += length
            continue

        if tag_type == 1:
            length = ((tag >> 2) & 0x7) + 4
            offset = ((tag & 0xE0) << 3) | data[index]
            index += 1
        elif tag_type == 2:
            length = (tag >> 2) + 1
            offset = int.from_bytes(data[index : index + 2], "little")
            index += 2
        else:
            length = (tag >> 2) + 1
            offset = int.from_bytes(data[index : index + 4], "little")
            index += 4

        for _ in range(length):
            output.append(output[-offset])

    if len(output) != expected_length:
        raise ValueError("Could not decode Firefox localStorage value")

    return bytes(output)


def decode_jwt_payload(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * ((4 - len(payload) % 4) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def read_firefox_token() -> str:
    storage_path = find_firefox_storage()
    if not storage_path.exists():
        raise FileNotFoundError(f"Firefox Zone01 localStorage not found: {storage_path}")

    snapshot = Path("/tmp/zone01-localstorage.sqlite")
    shutil.copy2(storage_path, snapshot)

    with sqlite3.connect(snapshot) as connection:
        row = connection.execute(
            "select value, compression_type from data where key='hasura-jwt-token'"
        ).fetchone()

    if not row:
        raise RuntimeError("Zone01 token not found in Firefox localStorage")

    value, compression_type = row
    if compression_type == 1:
        return snappy_decompress(value).decode("utf-8")
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def find_firefox_storage() -> Path:
    configured = os.environ.get("ZONE01_FIREFOX_STORAGE", "").strip()
    if configured:
        return Path(configured).expanduser()

    if DEFAULT_FIREFOX_STORAGE.exists():
        return DEFAULT_FIREFOX_STORAGE

    matches = []
    for profile_root in FIREFOX_PROFILE_ROOTS:
        if profile_root.exists():
            matches.extend(profile_root.glob(FIREFOX_STORAGE_GLOB))

    if matches:
        return max(matches, key=lambda path: path.stat().st_mtime)

    return DEFAULT_FIREFOX_STORAGE


def get_token() -> str:
    token = os.environ.get("ZONE01_JWT", "").strip()
    return token or read_firefox_token()


def refresh_token(token: str) -> str:
    request = urllib.request.Request(
        REFRESH_URL,
        headers={"x-jwt-token": token},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            refreshed = response.read().decode("utf-8").strip()
    except urllib.error.HTTPError:
        return token

    if refreshed.startswith('"') and refreshed.endswith('"'):
        refreshed = json.loads(refreshed)

    return refreshed or token


def graphql(token: str, query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "x-hasura-role": "user",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Zone01 GraphQL failed: HTTP {error.code}: {message}") from error

    if result.get("errors"):
        raise RuntimeError(f"Zone01 GraphQL errors: {result['errors']}")

    return result["data"]


USER_QUERY = """
query user($userId: Int!) {
  user: user_by_pk(id: $userId) {
    id
    login
    campus
    firstName
    lastName
    transactions(
      order_by: [{ type: desc }, { amount: desc }]
      distinct_on: [type]
      where: { userId: { _eq: $userId }, type: { _like: "skill_%" } }
    ) {
      type
      amount
    }
    recentSkill: transactions(
      limit: 1
      order_by: { createdAt: desc }
      where: { userId: { _eq: $userId }, type: { _like: "skill_%" } }
    ) {
      type
      amount
      createdAt
    }
  }
}
"""

ROOT_EVENTS_QUERY = """
query rootEvents($userId: Int!, $campus: String!) {
  event(
    where: {
      campus: { _eq: $campus }
      usersRelation: { userId: { _eq: $userId } }
      object: { type: { _in: ["module", "piscine"] } }
    }
  ) {
    id
    path
    startAt
    endAt
    object { type }
    usersRelation(where: { userId: { _eq: $userId }} limit: 1) {
      createdAt
    }
  }
}
"""

ROOT_EVENT_DETAILS_QUERY = """
query rootEventDetails($userId: Int!, $rootEventId: Int!) {
  xp: transaction_aggregate(
    where: {
      userId: { _eq: $userId }
      type: { _eq: "xp" }
      eventId: { _eq: $rootEventId }
    }
  ) { aggregate { sum { amount } } }
  level: transaction(
    limit: 1
    order_by: { amount: desc }
    where: {
      userId: { _eq: $userId }
      type: { _eq: "level" }
      eventId: { _eq: $rootEventId }
    }
  ) { amount }
}
"""


def format_xp(value: float) -> str:
    if value >= 1000:
        return f"{round(value / 1000)} kB"
    return f"{round(value)} B"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refreshed-token-path",
        help="Write the refreshed Zone01 JWT to this path for secret rotation.",
    )
    args = parser.parse_args()

    token = refresh_token(get_token())
    if args.refreshed_token_path:
        token_path = Path(args.refreshed_token_path)
        token_path.write_text(token, encoding="utf-8")
        token_path.chmod(0o600)

    payload = decode_jwt_payload(token)
    user_id = int(payload["sub"])

    user = graphql(token, USER_QUERY, {"userId": user_id})["user"]
    root_events = graphql(
        token, ROOT_EVENTS_QUERY, {"userId": user_id, "campus": user["campus"]}
    )["event"]

    root_event = next(
        (event for event in root_events if event["path"].endswith("/div-01")),
        root_events[0],
    )
    details = graphql(
        token,
        ROOT_EVENT_DETAILS_QUERY,
        {"userId": user_id, "rootEventId": root_event["id"]},
    )

    skills = {
        item["type"].removeprefix("skill_"): item["amount"]
        for item in user["transactions"]
    }
    recent_skill = (
        user["recentSkill"][0]["type"].removeprefix("skill_")
        if user["recentSkill"]
        else "go"
    )

    current = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    current.update(
        {
            "student": user["login"],
            "campus": f"Zone01 {user['campus'].title()}",
            "program": "Java Full-Stack",
            "module": f"#{root_event['id']}",
            "status": "In progress",
            "level": int(details["level"][0]["amount"] if details["level"] else 0),
            "checkpoint_level": int(skills.get("prog", 0)),
            "last_skill": recent_skill.replace("-", " ").title(),
            "cohort": current.get("cohort", "Cohort 2.2"),
            "joined_at": (
                root_event["usersRelation"][0]["createdAt"][:10]
                if root_event["usersRelation"]
                else current.get("joined_at", "")
            ),
            "xp": format_xp(details["xp"]["aggregate"]["sum"]["amount"] or 0),
            "skills": skills,
            "updated_at": datetime.now(timezone.utc).date().isoformat(),
        }
    )

    DATA_PATH.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {DATA_PATH.relative_to(ROOT)} for {user['login']}")


if __name__ == "__main__":
    main()
