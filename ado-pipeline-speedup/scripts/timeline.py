"""Print an Azure DevOps build timeline as an indented stage/job/task tree with durations.

Usage: curl -s -u ":$AZURE_DEVOPS_PAT" "https://dev.azure.com/<org>/<project>/_apis/build/builds/<id>/timeline?api-version=7.1" | python3 timeline.py [--min-seconds 3]
"""

import argparse
import json
import sys
from datetime import datetime


def parse_time(value: str | None) -> datetime | None:
    """Parse ADO's 7-digit-fraction timestamps."""
    if not value:
        return None
    value = value.rstrip("Z")
    if "." in value:
        head, fraction = value.split(".")
        value = f"{head}.{fraction[:6]}"
    return datetime.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--min-seconds", type=float, default=3.0, help="hide tasks shorter than this"
    )
    args = parser.parse_args()

    records = json.load(sys.stdin)["records"]
    children: dict[str | None, list[dict]] = {}
    for record in records:
        children.setdefault(record.get("parentId"), []).append(record)

    # Walk the tree in start order; gaps between a job's finish and the next job's start are agent waits.
    def walk(parent_id: str | None, depth: int) -> None:
        def start_key(record: dict) -> datetime:
            return parse_time(record.get("startTime")) or datetime.max

        for record in sorted(children.get(parent_id, []), key=start_key):
            start, finish = (
                parse_time(record.get("startTime")),
                parse_time(record.get("finishTime")),
            )
            seconds = (finish - start).total_seconds() if start and finish else None
            if record["type"] == "Task" and (
                seconds is None or seconds < args.min_seconds
            ):
                continue
            span = (
                f"{start:%H:%M:%S}-{finish:%H:%M:%S}"
                if start and finish
                else "skipped".ljust(17)
            )
            duration = f"{seconds:7.1f}s" if seconds is not None else "      -"
            print(
                f"{'  ' * depth}{record['type'][:5]:5} {duration}  {span}  {record.get('result')!s:10} {record['name']}"
            )
            walk(record["id"], depth + 1)

    walk(None, 0)


if __name__ == "__main__":
    main()
