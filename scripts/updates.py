#!/usr/bin/env python3
"""Project-activity report for the portfolio site.

Nothing is published until a person approves it:

    python scripts/updates.py draft     # read GitHub activity, write a local draft, print it
    python scripts/updates.py approve   # publish the draft as-is (updates/data.json + updates/index.html)
    python scripts/updates.py render    # rebuild updates/index.html from approved data only

The draft never contains commit text. Each commit message is only matched against a fixed
list of categories, and the report uses the category's own wording. Only repositories listed
in updates/config.json are read, and each is shown under the public title given there.
The draft lives in updates/.draft/ (git-ignored), so it stays on this machine until approved.
"""
import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPDATES = ROOT / "updates"
CONFIG = UPDATES / "config.json"
DATA = UPDATES / "data.json"
POSTS = UPDATES / "posts.json"
DRAFT = UPDATES / ".draft" / "draft.json"
PAGE = UPDATES / "index.html"

# (public wording, pattern). A commit can match several; the wording is fixed here, never taken from a commit.
CATEGORIES = [
    ("new features", r"\b(add|adds|added|new|implement|implemented|build|built|create|created|introduce|support)\b"),
    ("bug fixes", r"\b(fix|fixes|fixed|bug|repair|correct|patch|resolve|resolved)\b"),
    ("more tests", r"\b(test|tests|testing|coverage)\b"),
    ("documentation", r"\b(doc|docs|readme|guide|notes|document)\b"),
    ("interface and layout work", r"\b(ui|css|style|styles|layout|design|page|dashboard|theme|responsive)\b"),
    ("evaluation runs and reports", r"\b(eval|evaluation|report|reports|cycle|benchmark|experiment)\b"),
    ("security hardening", r"\b(security|harden|auth|validation|sanitize)\b"),
    ("cleanup and refactoring", r"\b(refactor|clean|cleanup|rename|remove|tidy|simplify)\b"),
    ("performance", r"\b(speed|perf|performance|optimize|faster)\b"),
]
FALLBACK = "general improvements"


def find_gh():
    return shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def window_start(config, posts, data):
    """The report covers everything since the newest of: the configured start, the last blog post, the last approved report."""
    candidates = [parse_time(config["start"] + "T00:00:00Z")]
    candidates += [parse_time(p["date"] + "T00:00:00Z") for p in posts]
    candidates += [parse_time(period["end"]) for period in data["periods"]]
    return max(candidates)


def categorize(message):
    """Map one commit message to public wording. Returns only phrases from CATEGORIES, never the message."""
    text = message.lower()
    hits = [label for label, pattern in CATEGORIES if re.search(pattern, text)]
    return hits or [FALLBACK]


def summarize(messages):
    """One generic sentence from all commit messages in a project. Contains no commit text."""
    tally = Counter(label for message in messages for label in categorize(message))
    top = [label for label, _ in tally.most_common(3)]
    if not top:
        return ""
    if len(top) == 1:
        body = top[0]
    else:
        body = ", ".join(top[:-1]) + " and " + top[-1]
    return "Work on " + body + "."


def fetch_commits(repo, since):
    jq = ".[] | [.commit.author.date, (.commit.message | split(\"\\n\")[0])] | @json"
    result = subprocess.run(
        [find_gh(), "api", f"repos/{repo}/commits?since={stamp(since)}&per_page=100", "--paginate", "--jq", jq],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        raise SystemExit(f"Could not read {repo}: {result.stderr.strip()}")
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def build_projects(config, since, fetch=fetch_commits):
    projects = []
    for entry in config["projects"]:
        commits = fetch(entry["repo"], since)
        if not commits:
            continue
        days = {date[:10] for date, _ in commits}
        projects.append({
            "title": entry["title"],
            "commits": len(commits),
            "activeDays": len(days),
            "summary": summarize([message for _, message in commits]),
        })
    return projects


def command_draft(_args):
    config = load_json(CONFIG, None)
    if config is None:
        raise SystemExit("updates/config.json is missing")
    since = window_start(config, load_json(POSTS, []), load_json(DATA, {"periods": []}))
    now = datetime.now(timezone.utc)
    projects = build_projects(config, since)
    if not projects:
        print(f"No activity since {since:%Y-%m-%d}. Nothing to draft.")
        if DRAFT.exists():
            DRAFT.unlink()
        return
    draft = {"start": stamp(since), "end": stamp(now), "projects": projects}
    write_json(DRAFT, draft)
    print(f"DRAFT (not published). {since:%b %d} to {now:%b %d, %Y}\n")
    for p in projects:
        print(f"  {p['title']}: {p['commits']} {'commit' if p['commits'] == 1 else 'commits'} on {p['activeDays']} {'day' if p['activeDays'] == 1 else 'days'}. {p['summary']}")
    print(f"\nEdit {DRAFT.relative_to(ROOT)} to change any wording, then run: python scripts/updates.py approve")


def command_approve(_args):
    draft = load_json(DRAFT, None)
    if draft is None:
        raise SystemExit("No draft to approve. Run: python scripts/updates.py draft")
    data = load_json(DATA, {"periods": []})
    draft["approved"] = stamp(datetime.now(timezone.utc))
    data["periods"].append(draft)
    write_json(DATA, data)
    DRAFT.unlink()
    render()
    print("Approved and published to updates/index.html. Commit and push to put it live.")


def day_label(text):
    moment = parse_time(text)
    return f"{moment:%b} {moment.day}"


def render():
    data = load_json(DATA, {"periods": []})
    cards = []
    for period in reversed(data["periods"]):
        total = sum(p["commits"] for p in period["projects"])
        items = "\n".join(
            f"          <li><strong>{html.escape(p['title'])}</strong>: {p['commits']} "
            f"{'commit' if p['commits'] == 1 else 'commits'} on {p['activeDays']} "
            f"{'day' if p['activeDays'] == 1 else 'days'}. {html.escape(p['summary'])}</li>"
            for p in period["projects"]
        )
        span = f"{day_label(period['start'])} to {day_label(period['end'])}, {parse_time(period['end']).year}"
        cards.append(
            f"""      <article class="project">
        <div class="meta">{span}</div>
        <h3>{total} {'commit' if total == 1 else 'commits'} across {len(period['projects'])} {'project' if len(period['projects']) == 1 else 'projects'}</h3>
        <ul>
{items}
        </ul>
      </article>"""
        )
    body = "\n\n".join(cards) if cards else "      <p>The first report will appear here.</p>"
    intro = (
        "A plain summary of what I have worked on since my last post or report. "
        "Several projects are private because they hold coursework or personal data, so this page shows how much happened and what kind of work it was, not the details."
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Project updates | William McNulty</title>
<meta name="description" content="A running summary of activity across William McNulty's projects, including private ones.">
<link rel="stylesheet" href="../styles.css?v=6">
</head>
<body>
  <header class="topbar">
    <div class="wrap">
      <strong><a href="../" style="color:inherit;text-decoration:none">William McNulty</a></strong>
      <nav aria-label="Sections">
        <a href="../#projects">Projects</a>
        <a href="../#background">Background</a>
        <a href="../#beyond">Beyond the code</a>
        <a href="./">Updates</a>
        <a href="../#contact">Contact</a>
      </nav>
    </div>
  </header>

  <main class="wrap">
    <section aria-labelledby="updates-h">
      <h2 id="updates-h">Project updates</h2>
      <p>{intro}</p>
{body}
    </section>
  </main>

  <footer>
    <div class="wrap">Plain HTML and CSS, no trackers. Each report is reviewed by me before it is published.</div>
  </footer>
</body>
</html>
"""
    PAGE.write_text(page, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("draft").set_defaults(run=command_draft)
    sub.add_parser("approve").set_defaults(run=command_approve)
    sub.add_parser("render").set_defaults(run=lambda _a: (render(), print("Rebuilt updates/index.html")))
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    sys.exit(main())
