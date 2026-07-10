#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "portfolio-projects.json"
README_PATH = ROOT / "README.md"

START = "<!-- portfolio-projects:start -->"
END = "<!-- portfolio-projects:end -->"


def project_link(project):
    url = project.get("repo_url", "").strip()
    name = markdown_cell(project["name"])
    return f"[{name}]({url})" if url else name


def markdown_cell(value):
    return str(value).replace("|", "\\|")


def render_section(data):
    projects = sorted(
        (
            project
            for project in data["projects"]
            if project.get("show_on_profile") and project.get("status") != "not-ready"
        ),
        key=lambda project: project.get("priority", 999),
    )

    lines = [
        "## Selected Projects",
        "",
        "| Project | Focus | Why it matters |",
        "| --- | --- | --- |",
    ]

    for project in projects:
        lines.append(
            "| "
            + " | ".join(
                [
                    project_link(project),
                    markdown_cell(project["focus"]),
                    markdown_cell(project["summary"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "These are curated from Zone01 work and selected for portfolio signal, not project count.",
        ]
    )
    return "\n".join(lines)


def replace_between_markers(content, generated):
    block = f"{START}\n{generated}\n{END}"
    if START in content and END in content:
        before = content.split(START, 1)[0].rstrip()
        after = content.split(END, 1)[1].lstrip()
        return f"{before}\n\n{block}\n\n{after}"

    marker = "## Portfolio Direction"
    if marker not in content:
        return content.rstrip() + "\n\n" + block + "\n"

    return content.replace(marker, block + "\n\n" + marker, 1)


def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    generated = render_section(data)
    README_PATH.write_text(
        replace_between_markers(README_PATH.read_text(encoding="utf-8"), generated),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
