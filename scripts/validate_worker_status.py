#!/usr/bin/env python3
"""Validate a private worker feed without writing, publishing or printing its data."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

TEAM_IDS = {"backend", "frontend", "pemeriksa", "cms", "kontenseo", "marketing", "rilis", "pemantau"}
STATUSES = {"working", "waiting", "done", "blocked", "unassigned", "unknown"}
FORBIDDEN_TEXT = re.compile(
    r"(?:https?://|[A-Za-z]:[\\/]|/(?:workspace|home|tmp|etc|var)/|"
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[ -]?){10,}|"
    r"(?:gh[pousr]_|github_pat_|sk-proj-)[A-Za-z0-9_-]+)", re.I
)


def fields(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"{label}: unexpected or missing fields")


def text(value, label, limit=500):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(char) < 32 for char in value) or FORBIDDEN_TEXT.search(value)):
        raise ValueError(f"{label}: use a short, curated public summary")


def timestamp(value, label, now, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError(f"{label}: UTC timestamp required")
    parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if parsed.timestamp() > now.timestamp() + 60:
        raise ValueError(f"{label}: future source time")
    return parsed


def evidence_url(value):
    if not isinstance(value, str) or len(value) > 220:
        raise ValueError("evidence: invalid URL")
    url = urlsplit(value)
    if (url.scheme != "https" or url.netloc != "github.com" or url.query or url.fragment
            or not re.fullmatch(r"/erwin071996/rumahwebhous/(?:pull/\d+|commit/[0-9a-f]{40}|actions/runs/\d+(?:/job/\d+)?)", url.path)):
        raise ValueError("evidence: only this repository's canonical evidence URLs are allowed")


def validate_feed(feed, now=None):
    now = now or datetime.now(timezone.utc)
    fields(feed, {"schemaVersion", "updatedAt", "staleAfterSeconds", "refreshIntervalMs", "sourceMode", "release", "teams"}, "feed")
    if (type(feed["schemaVersion"]) is not int or feed["schemaVersion"] != 1 or feed["staleAfterSeconds"] != 900
            or feed["refreshIntervalMs"] != 3000 or feed["sourceMode"] != "report-driven"):
        raise ValueError("feed: unsupported contract")
    updated = timestamp(feed["updatedAt"], "updatedAt", now, True)
    release = feed["release"]
    fields(release, {"label", "stage", "sha", "prUrl", "summary", "observedAt"}, "release")
    text(release["label"], "release label", 80)
    text(release["summary"], "release summary")
    if release["stage"] not in {"draft", "tested", "live", "unknown"}:
        raise ValueError("release: invalid stage")
    if release["sha"] is not None and (not isinstance(release["sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", release["sha"])):
        raise ValueError("release: invalid SHA")
    if release["prUrl"] is not None:
        evidence_url(release["prUrl"])
    observed = timestamp(release["observedAt"], "release observedAt", now, True)
    if observed and (updated is None or observed > updated):
        raise ValueError("release: observedAt is newer than feed")
    if updated is None and (release["stage"] != "unknown" or release["sha"] is not None or release["prUrl"] is not None):
        raise ValueError("release: missing feed time requires an empty unknown release")
    teams = feed["teams"]
    if not isinstance(teams, list) or len(teams) != 8:
        raise ValueError("feed: exactly eight teams required")
    ids = []
    for team in teams:
        fields(team, {"id", "name", "status", "summary", "nextStep", "waitingFor", "observedAt", "evidence"}, "team")
        if team["id"] not in TEAM_IDS or team["status"] not in STATUSES:
            raise ValueError("team: unsupported identity or status")
        ids.append(team["id"])
        for key, limit in (("name", 80), ("summary", 500), ("nextStep", 300)):
            text(team[key], key, limit)
        if team["waitingFor"] is not None:
            text(team["waitingFor"], "waitingFor", 100)
        observed = timestamp(team["observedAt"], "team observedAt", now, True)
        if observed and (updated is None or observed > updated):
            raise ValueError("team: observedAt is newer than feed")
        if team["status"] != "unknown" and (observed is None or updated is None):
            raise ValueError("team: known status needs a source observation")
        if not isinstance(team["evidence"], list) or len(team["evidence"]) > 5:
            raise ValueError("team: at most five evidence links")
        if team["status"] in {"working", "done"} and not team["evidence"]:
            raise ValueError("team: this status requires evidence")
        for item in team["evidence"]:
            fields(item, {"label", "url"}, "evidence")
            text(item["label"], "evidence label", 80)
            evidence_url(item["url"])
    if set(ids) != TEAM_IDS or len(set(ids)) != 8:
        raise ValueError("feed: missing or duplicate team")
    return feed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", type=Path, required=True, help="Validate only; real input stays outside the repository")
    args = parser.parse_args()
    try:
        if args.check.stat().st_size > 24000:
            parser.error("feed exceeds 24 KB")
        validate_feed(json.loads(args.check.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        parser.error("feed invalid or unreadable; details withheld")
    print("Feed valid. No data printed, source write or publication performed.")


if __name__ == "__main__":
    main()
