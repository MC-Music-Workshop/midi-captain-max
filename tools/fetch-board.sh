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

echo "Wrote site/board.json:"
jq -r '.columns[] | "\(.name): \(.items | length) shown"' site/board.json
