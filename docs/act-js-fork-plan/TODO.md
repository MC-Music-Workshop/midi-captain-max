# act-js mocking enhancements — work queue

Each item is one Ralph iteration. Work top-to-bottom. Do **not** skip ahead.

## Phase 1 — `mockJobs` (issue #92)

- [ ] 01: Add `MockJob` and `MockJobs` types to `src/step-mocker/step-mocker.types.ts`. `MockJob.mockWith` is `string | Partial<GithubWorkflowJob>`. `MockJobs` is `Record<string, MockJob>`.
- [ ] 02: Add `mockJobs?: MockJobs` to `RunOpts` in `src/act/act.type.ts`.
- [ ] 03: Implement job replacement in `StepMocker` (new method `mockJobs(map)`). Preserve `needs:` and `if:`. Drop `uses:` / `with:` / `secrets:`. String shorthand → `{ steps: [{ run: <string> }] }`. Object form shallow-merges over `{ "runs-on": "ubuntu-latest", steps: [{ run: "true" }] }`. Deep-merge `env` and `outputs`. Throw on unknown jobId.
- [ ] 04: Wire `mockJobs` into `handleStepMocking` in `src/act/act.ts` to run **before** any step mocking.
- [ ] 05: Unit tests for `mockJobs`: string shorthand, object form, unknown job error, needs/if preservation, env/outputs deep-merge.
- [ ] 06: Integration test under `test/it/`: workflow with `jobs.build.uses: ./.github/workflows/reusable.yml`, run `act` with `mockJobs.build`, assert downstream job sees mocked outputs.

## Phase 2 — `mockNestedSteps` (issue #54, reusable workflows)

- [ ] 07: Add `MockNestedSteps` type (`Record<filePath, MockStep>`) to `src/step-mocker/step-mocker.types.ts`.
- [ ] 08: Add `mockNestedSteps?: MockNestedSteps` to `RunOpts`.
- [ ] 09: Path resolver: relative-to-cwd, reject absolute paths and `..`, error names the offending key. Implement as a small util used by both nested-step and composite-step paths.
- [ ] 10: For each entry in `mockNestedSteps`, instantiate a `StepMocker(filePath)` and apply its existing `mock()` with the per-file step map.
- [ ] 11: Wire `mockNestedSteps` into `handleStepMocking` **after** `mockJobs`. If a wrapper job is in `mockJobs` and its `uses:` target appears in `mockNestedSteps`, warn and skip.
- [ ] 12: Unit tests for `mockNestedSteps`: happy path, path validation rejection, file-not-found error, precedence (mockJobs wins).
- [ ] 13: Integration test: wrapper workflow → reusable workflow with three steps; mock the middle step; assert it ran the mock.

## Phase 3 — `mockCompositeSteps` (issue #54, composite actions)

- [ ] 14: Add `MockCompositeSteps` type (`Record<actionPath, MockStep[]>` — flat array, no jobId).
- [ ] 15: Add `mockCompositeSteps?: MockCompositeSteps` to `RunOpts`.
- [ ] 16: `StepMocker` shape detection: `runs.steps` (composite) vs `jobs.<id>.steps` (workflow). Route to the right mutation path. Refactor `locateStep` / `updateStep` / `addStep` to accept a `stepsRoot` reference rather than hard-coding `jobs[id].steps`.
- [ ] 17: Path resolver for composites: accept directory (look for `action.yml` then `action.yaml`) or full file path. Reuse the validator from item 09.
- [ ] 18: Wire `mockCompositeSteps` into `handleStepMocking` **after** `mockNestedSteps`. Same wrapper-job-wins precedence as nested steps.
- [ ] 19: Unit + integration tests for `mockCompositeSteps`: directory key, file key, action.yaml fallback, missing action error, mock applied inside a real composite invocation.

## Phase 4 — Hardening & release

- [ ] 20: Drop a sanitized real `emtn-actions` reusable workflow + its referenced composite action into `test/it/fixtures/emtn/`. Write an end-to-end test that exercises mockJobs + mockNestedSteps + mockCompositeSteps in one run. **Blocks on user supplying the fixture.**
- [ ] 21: Regression sweep: every existing `mockSteps` test is still green. No behavior change when new options absent. README / CHANGELOG updated with three new sections. `npm pack`; smoke-test the tarball against the fixture from item 20. Create `STOP` file at fork root when satisfied.
