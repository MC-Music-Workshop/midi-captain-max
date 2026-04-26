# RALPH — act-js mocking enhancements

You are extending `@kie/act-js` with whole-job mocking and nested-workflow / composite
step mocking. This file is the persistent driver; it is read at the start of every
iteration. The work queue is `TODO.md` at the same directory.

## Iteration protocol

1. Read `TODO.md`. Pick the **topmost unchecked** item. If there are none, write a
   one-line summary to stdout and stop.
2. Read these files in full before editing:
   - `src/step-mocker/step-mocker.ts`
   - `src/step-mocker/step-mocker.types.ts`
   - `src/act/act.ts`
   - `src/act/act.type.ts`
3. Verify the item is not already done (idempotency check — types may already exist,
   tests may already pass). If already done, just check the box and commit the
   `TODO.md` change with message `ralph: <id> already done`.
4. Implement **only** that item. No drive-by refactors. No new files unless the
   item explicitly requires one.
5. Run `npm run lint && npm test`. If red, fix before committing. Do not commit a
   red tree.
6. Check the box in `TODO.md`. Commit with `ralph: <id> <one-line summary>`.
7. `git push origin feat/mock-jobs-and-nested`.
8. Stop. The next iteration is a fresh session.

## Scope (hard boundary)

In scope:
- `mockJobs`  — replace a job whose body is `uses: ./...` with a synthetic stub
- `mockNestedSteps`  — mock steps inside reusable workflows (`uses: ./.github/workflows/*.y{a,}ml`)
- `mockCompositeSteps`  — mock steps inside composite actions (`uses: ./.github/actions/*`)

Out of scope:
- Copy-on-write protection of the working tree (callers use `@kie/mock-github`)
- Recursing into nested files' own `uses:` (one level only)
- Upstream PR — this is a fork. Do not open PRs against `kiegroup/act-js`.
- Anything not in `TODO.md`.

## Design invariants

These are non-negotiable. The loop must not violate them.

**Order in `handleStepMocking`:** mockJobs → mockNestedSteps → mockCompositeSteps → mockSteps.
Earlier passes mutate the YAML on disk; later passes see the mutated state.

**`mockJobs`:**
- Preserve `needs:` and `if:` on the replaced job.
- Drop `uses:`, `with:`, `secrets:`.
- String shorthand: `mockWith: "echo x"` → `{ steps: [{ run: "echo x" }] }`.
- Object form: shallow-merge over `{ "runs-on": "ubuntu-latest", steps: [{ run: "true" }] }`.
- Deep-merge `env` and `outputs`.
- Throw with a clear message if a `jobId` doesn't exist in the workflow.

**`mockNestedSteps`:**
- Keys are workflow file paths **relative to cwd**.
- Reject absolute paths and any path containing `..`. Error message names the offending key.
- Value shape mirrors `mockSteps`: `Record<jobId, MockStep[]>` per file.
- Does **not** recurse — mock the named file only.
- Throw with a clear message if the file doesn't exist or doesn't parse.

**`mockCompositeSteps`:**
- Keys may be either an action directory (`./.github/actions/setup`) or a full file
  path (`./.github/actions/setup/action.yml`). For directories, look for `action.yml`
  then `action.yaml`. Reject if neither exists.
- Path validation rules same as `mockNestedSteps`.
- Composite YAML shape is `runs.steps` (flat array, no job dimension).
- Value shape: `MockStep[]` (no jobId key — composites don't have jobs).
- StepMocker must detect file shape (`jobs.<id>.steps` vs `runs.steps`) and route to
  the right mutation path.

**Precedence:**
- If a wrapper job is in `mockJobs` AND its `uses:` target is in `mockNestedSteps`
  or `mockCompositeSteps`, log a warning and skip the nested mock. The wrapper job
  is replaced; the nested file won't run.

**Existing behavior:**
- All existing `mockSteps` tests must remain green. No behavior change when the new
  options are absent.

## Conventions

- TypeScript strict mode; match existing code style.
- Test file naming: `*.test.ts` under `test/unit/` and `test/it/`.
- Commit messages: `ralph: <NN> <summary>`. One commit per iteration.
- Branch: `feat/mock-jobs-and-nested`. Do not push to other branches.
- Never run `git push --force`, `git reset --hard`, or `npm test -- --no-verify`.
