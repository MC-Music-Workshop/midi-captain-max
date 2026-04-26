# act-js fork — Ralph loop plan

Goal: extend `@kie/act-js` with three new mocking capabilities to make `emtn-actions`
testable end-to-end without invoking real GitHub Actions runners.

| Capability | Issue | Shape |
|---|---|---|
| `mockJobs` | [#92](https://github.com/kiegroup/act-js/issues/92) | Replace a wrapper job (`uses: ./...`) with a synthetic stub |
| `mockNestedSteps` | [#54](https://github.com/kiegroup/act-js/issues/54) (reusable half) | Mock steps inside a referenced reusable workflow file |
| `mockCompositeSteps` | [#54](https://github.com/kiegroup/act-js/issues/54) (composite half) | Mock steps inside a referenced composite action's `action.yml` |

Strategy: fork-only (no upstream PR), develop with a Ralph loop driven by Claude Code
on the Web's `/loop` skill, exit when `TODO.md` is fully checked and `npm test` is
green.

## API at the end state

```ts
await act.runJob("deploy", {
  mockJobs: {
    lint: { mockWith: "echo skipped" },
    build: {
      mockWith: {
        outputs: { version: "1.2.3" },
        steps:   [{ run: "echo mocked build" }],
      },
    },
  },
  mockNestedSteps: {
    "./.github/workflows/build-reusable.yml": {
      build: [{ name: "compile", mockWith: "echo stubbed" }],
    },
  },
  mockCompositeSteps: {
    "./.github/actions/setup": [
      { id: "install-tools", mockWith: "echo mocked" },
    ],
  },
});
```

## Bootstrap (do once, by hand)

1. Fork `kiegroup/act-js` to your GitHub account/org.
2. Clone the fork locally **and** open it in Claude Code on the Web.
3. From this midi-captain-max repo, copy these files into the fork's root:
   - `docs/act-js-fork-plan/RALPH.md` → `RALPH.md`
   - `docs/act-js-fork-plan/TODO.md`  → `TODO.md`
4. In the fork: `git checkout -b feat/mock-jobs-and-nested`
5. In the fork: `npm ci && npm test` — confirm baseline is green before the loop starts.
6. Commit `RALPH.md` and `TODO.md` to the feature branch and push.

## Run the loop (Claude Code on the Web)

Open the fork in Claude Code on the Web, then in a session:

```
/loop 15m read RALPH.md and execute exactly one unchecked item from TODO.md
```

15-minute interval is a starting point — adjust based on how long iterations take.
Each iteration is a fresh session; state lives in `TODO.md` (committed) and the git
history. Iterations are idempotent: re-running an item that's already done is a
no-op (the agent verifies state before mutating).

## Stop conditions

- `TODO.md` has zero unchecked items
- `npm test` green
- A `STOP` file exists at fork root (your manual gate before `npm pack`)

When all three hold, the loop's prompt instructs the agent to report and exit.

## Step 20 (real fixture) — needs you

Item 20 of `TODO.md` requires a real reusable workflow + composite action from
`emtn-actions`, sanitized and dropped into `test/it/fixtures/emtn/`. Until you
provide one, item 20 stays unchecked and the loop will idle on it. To unblock:
copy a representative reusable workflow (one that calls a composite action) into
the fixture directory, redact secrets/org names, commit. The next iteration
picks it up.
