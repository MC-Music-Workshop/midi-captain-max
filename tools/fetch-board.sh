#!/usr/bin/env bash
# Generate site/board.json from the public MIDI Captain MAX GitHub project
# (https://github.com/orgs/MC-Music-Workshop/projects/1). Run locally or in CI
# with a token that can read org projects. The site renders this snapshot;
# the Pages workflow refreshes it on each deploy and on a daily cron.
set -euo pipefail

cd "$(dirname "$0")/.."

# Paginate through all project items; each node carries its Status column
# name plus the underlying issue/PR content.
gh api graphql --paginate -f query='
query($endCursor: String) {
  organization(login: "MC-Music-Workshop") {
    projectV2(number: 1) {
      items(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
          content {
            ... on Issue { title number url updatedAt }
            ... on PullRequest { title number url updatedAt }
            ... on DraftIssue { title updatedAt }
          }
        }
      }
    }
  }
}' --jq '.data.organization.projectV2.items.nodes[]' |
jq -s --arg date "$(date -u +%Y-%m-%d)" '
  map({status: (.fieldValueByName.name // "none")} + (.content // {}))
  | map(select(.title != null))
  | sort_by(.updatedAt) | reverse
  | . as $items
  | {
      updated: $date,
      columns: (
        ["In Design", "Ready", "In progress", "In review", "Done"]
        | map(. as $col | {
            name: $col,
            items: ([$items[] | select(.status == $col)] | .[:4]
                    | map({title, number, url}))
          })
      )
    }
' > site/board.json

# Inline the same snapshot into index.html (#board-data) so the board renders
# without a fetch, e.g. when the file is opened directly from disk.
python3 - <<'PY'
import json, re

snapshot = json.dumps(json.load(open('site/board.json')))
html = open('site/index.html').read()
html, n = re.subn(
  r'(<script id="board-data" type="application/json">\n).*?(\n</script>)',
  lambda m: m.group(1) + snapshot + m.group(2),
  html, count=1, flags=re.S)
assert n == 1, 'board-data block not found in site/index.html'
open('site/index.html', 'w').write(html)
PY

echo "Wrote site/board.json (inlined into site/index.html):"
jq -r '.columns[] | "\(.name): \(.items | length) shown"' site/board.json
