# Execution Plan: UI-Independent Workflow Orchestration

Date: 2026-09-16

## Status

Completed

## Outcome

CLI and WebUI execute video-translation jobs through one Qt-free runner with typed events, cooperative cancellation, structured failures, and explicit outputs.

## Context

The direct stage sequences in `cli.py` and `webui.py` duplicate the conditional routing owned by `TransCreate` and the desktop workers. `TransCreate` also sends presentation messages through global Qt-backed state and may delete output directories during construction.

## Scope

In scope:

- One noninteractive video-task runner and CLI/WebUI adapters.
- Validation before task construction, semantic events, cancellation, structured results, and focused tests.

Out of scope:

- Desktop interactive checkpoints, batch scheduling, retry policy, durable jobs, and restart recovery.

## Approach

Add a small typed runner interface, inject its event/cancellation dependencies into `BaseCon`, centralize conditional stage routing, then replace the CLI and WebUI stage lists. Keep Qt delivery as the existing fallback for desktop callers.

## Risks And Recovery

- Preserve desktop behavior by making injected dependencies optional.
- Never recursively clear a caller-selected output directory; only a normalized task cache may be cleared.
- Recovery is reverting the runner adapters and optional `BaseCon` fields independently.

## Progress

- [x] Inspect current CLI, WebUI, desktop routing, signaling, output, and cancellation behavior.
- [x] Implement the runner and Qt-free injected task dependencies.
- [x] Migrate CLI and WebUI.
- [x] Add focused tests and run validation.

## Decisions

- 2026-09-16: First milestone is in-process and noninteractive; desktop checkpoints, batching, and retry remain unchanged.
- 2026-09-16: `clear_cache` clears only the normalized cache directory, never the configured output directory.

## Validation

- Focused proof: `tests/test_orchestrator.py` passed.
- Integration or end-to-end proof: 172 affected tests passed, including CLI, WebUI, task configuration, output, and error regressions.
- Repository-required checks: Python compilation, Qt-free import, and `git diff --check` passed. Full pytest collection remains blocked by the pre-existing missing `videotrans.task.job._get_type_name`; Ruff is configured but not installed in this environment.

## Result

CLI and WebUI now share a typed, Qt-free single-task runner. It validates before construction, owns conditional routing, emits semantic events, supports cooperative cancellation, returns structured failures and explicit outputs, and restricts recursive cleanup to the application temp directory. Desktop batch and interactive checkpoint flows remain unchanged.
