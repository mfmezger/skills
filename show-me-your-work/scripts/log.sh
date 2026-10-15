#!/usr/bin/env bash
# Append one entry to a show-me-your-work decision log (Markdown).
# Usage: log.sh <logfile.md> <phase> <decision> <why> <evidence> <result> [details]
set -euo pipefail

if [ "$#" -lt 6 ] || [ "$#" -gt 7 ]; then
	printf 'usage: log.sh <logfile.md> <phase> <decision> <why> <evidence> <result> [details]\n' >&2
	exit 1
fi

logfile="$1"
shift

logdir="$(dirname "$logfile")"
if [ -n "$logdir" ] && [ "$logdir" != "." ] && [ ! -d "$logdir" ]; then
	mkdir -p "$logdir"
fi

# Use `>>` here, never `>`. A network mount can fail this test for a log
# that exists. Then the cost is one stray title line, not the entries.
if [ ! -s "$logfile" ]; then
	printf '# Decision log: %s\n' "$(basename "$logfile" .md)" >> "$logfile"
fi

# Fields stay on one line so every entry keeps the same shape; multi-line
# material goes into the optional details block.
one_line() {
	printf '%s' "$1" | tr '\r\n\t' '   '
}

ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
{
	printf '\n## %s · %s\n\n' "$ts" "$(one_line "$1")"
	printf -- '- **Decision:** %s\n' "$(one_line "$2")"
	printf -- '- **Why:** %s\n' "$(one_line "$3")"
	printf -- '- **Evidence:** %s\n' "$(one_line "$4")"
	printf -- '- **Result:** %s\n' "$(one_line "$5")"
	if [ "$#" -eq 6 ] && [ -n "$6" ]; then
		fence='```'
		case "$6" in *'```'*) fence='~~~~' ;; esac
		printf '\n%stext\n%s\n%s\n' "$fence" "$6" "$fence"
	fi
} >> "$logfile"
