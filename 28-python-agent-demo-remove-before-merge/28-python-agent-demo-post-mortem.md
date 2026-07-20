# Post-Mortem Report: Shepherd Task Pipeline for Python Demo (`28-python-agent-demo`)

**Report generated:** 2026-07-19  
**Period covered:** 2026-07-17 19:34 ET -> 2026-07-18 22:34 ET  
**Primary success batch:** `shepherd-tasks-20260718-1827` (tasks #34-#39)

## Table of Contents

- [Section 1: Executive Summary](#section-1-executive-summary)
- [Section 2: System Architecture](#section-2-system-architecture)
  - [2.1 Copilot Coding Agent (CCA)](#21-copilot-coding-agent-cca)
  - [2.2 Copilot Code Review Agent (CCRA)](#22-copilot-code-review-agent-ccra)
  - [2.3 Local Copilot CLI (Shepherd)](#23-local-copilot-cli-shepherd)
- [Section 3: Per-Task Metrics (Final Successful Batch)](#section-3-per-task-metrics-final-successful-batch)
- [Section 4: Aggregate Statistics](#section-4-aggregate-statistics)
- [Section 5: AI Credits and Token Usage](#section-5-ai-credits-and-token-usage)
- [Section 6: Wall-Clock Timeline](#section-6-wall-clock-timeline)
- [Section 7: What Failed Before the Final Run](#section-7-what-failed-before-the-final-run)
- [Section 8: Observations and Recommendations](#section-8-observations-and-recommendations)

---

## Section 1: Executive Summary

The shepherd pipeline ultimately succeeded on all target Python tasks (#34-#39) after three stabilization runs. The final batch (`shepherd-tasks-20260718-1827`) completed **6/6 tasks (100%)**, merged **PRs #44-#49**, and ended with `=== All tasks shepherded successfully ===` in `20260718-1826-job-logs.txt`.

| Metric | Value |
|--------|-------|
| Target tasks in final batch | 6 (#34-#39) |
| Completed/merged | 6/6 (100%) |
| Final batch elapsed time | ~4h 07m (18:27 -> 22:34 ET) |
| CCRA rounds (final batch) | 20 total |
| CCRA comments (final batch) | 30 total |
| Average time per task (session durations) | ~40m 57s |
| Idle-kill failures in final batch | 0 |
| Local CLI output tokens (final batch logs) | 136,022 |

Context: this run followed repeated failures in earlier batches (`20260717-1936`, `20260717-2022`, `20260718-1648`) caused by idle-session termination and missing initial Copilot review request.

---

## Section 2: System Architecture

### 2.1 Copilot Coding Agent (CCA)

CCA generated or updated draft PRs for task issues. In this campaign, it produced PRs #42-#49, with final successful shepherding focused on #44-#49.

### 2.2 Copilot Code Review Agent (CCRA)

CCRA (`copilot-pull-request-reviewer[bot]`) produced review rounds with "Comments generated" summaries. Final batch behavior ranged from zero-comment clean review (task #37) to long iterative convergence (task #39, 7 rounds).

### 2.3 Local Copilot CLI (Shepherd)

`copilot --yolo` ran the two shepherd skills and executed the local merge orchestration loop:

1. Move issue/PR through phase gates.
2. Request and poll CCRA review.
3. Apply/fix/reply/resolve review feedback.
4. Re-request review until clean.
5. Merge PR to `edburns/28-python-agent-demo`.

---

## Section 3: Per-Task Metrics (Final Successful Batch)

Batch: `shepherd-tasks-20260718-1827`  
Source logs: `phase1-task-*.md`, `phase2-task-*.md`, and `20260718-1826-job-logs.txt`.

| Issue | PR | Phase 1 | Phase 2 | Total | CCRA rounds | CCRA comments | Result |
|------:|---:|--------:|--------:|------:|------------:|--------------:|--------|
| 34 | 44 | skipped (PR existed) | 24m 17s | 24m 17s | 4 | 8 | merged |
| 35 | 45 | 14m 41s | 14m 23s | 29m 04s | 5 | 5 | merged |
| 36 | 46 | 39m 44s | 17m 47s | 57m 31s | 3 | 5 | merged |
| 37 | 47 | 14m 23s | 1m 26s | 15m 49s | 0 | 0 | merged |
| 38 | 48 | 10m 35s | 41m 11s | 51m 46s | 1 | 2 | merged |
| 39 | 49 | 27m 53s | 39m 20s | 1h 07m 13s | 7 | 10 | merged |

Notable per-task findings:

- **Issue #34**: Phase 1 skipped due to existing PR from prior run; still required 4 review rounds in phase 2.
- **Issue #35**: Recovered from transient local path errors (`Path does not exist`) and still converged.
- **Issue #37**: Fastest end-to-end task; merged with no CCRA comment rounds.
- **Issue #39**: Longest total duration and deepest review loop in final batch (7 rounds).

---

## Section 4: Aggregate Statistics

### 4.1 Final Batch (`20260718-1827`)

| Metric | Value |
|--------|-------|
| Tasks | 6 |
| Merged PRs | 6 |
| Total CCRA rounds | 20 |
| Total CCRA comments | 30 |
| Avg CCRA rounds/task | 3.33 |
| Avg comments/task | 5.0 |
| Avg comments/round | 1.5 |
| Tasks with zero CCRA comments | 1 (#37) |
| Longest task | #39 (1h 07m 13s) |
| Shortest task | #37 (15m 49s) |

### 4.2 Across All Four Referenced Shepherd Directories

| Directory | JSON sessions | Outcome |
|-----------|---------------|---------|
| `shepherd-tasks-20260717-1936` | 2 | failed (phase 2 left PR #42 open) |
| `shepherd-tasks-20260717-2022` | 1 | failed (phase 2 idle-kill behavior) |
| `shepherd-tasks-20260718-1648` | 5 (+ one empty phase2 JSON) | partial success (#41, #33 complete; #34 handed off) |
| `shepherd-tasks-20260718-1827` | 11 | full success (#34-#39 complete) |

---

## Section 5: AI Credits and Token Usage

### 5.1 Local Copilot CLI (from JSON logs)

| Scope | Output tokens |
|-------|---------------|
| Final success batch (`20260718-1827`) | 136,022 |
| All four referenced run directories combined | 186,132 |

### 5.2 CCA / CCRA credits

Direct credit/billing totals were not captured in these artifacts. This report therefore uses review rounds/comments and CLI token totals as the measurable proxy.

### 5.3 OTEL limitation

`20260718-1855-copilot-cli-otel-not-working.md` documents that OTEL file export does not flush when `copilot` is invoked via piped stdin (bug `copilot-agent-runtime#13047`), limiting observability fidelity for this campaign.

---

## Section 6: Wall-Clock Timeline

### 6.1 Batch timeline

| Batch | Window | Summary |
|------|--------|---------|
| `20260717-1936` | ~19:36-19:59 ET | First failure on issue #41 phase 2 (PR #42 remained open) |
| `20260717-2022` | ~20:23-20:26 ET | Retry failed; review arrived but session had gone idle |
| `20260718-1648` | ~16:49-18:09 ET | Stabilization run; #41 and #33 merged, #34 prepared |
| `20260718-1827` | ~18:27-22:34 ET | Final run; #34-#39 all merged |

### 6.2 Final successful run (`20260718-1827`)

- Start marker: `phase2-task-20260718-1827-34.*` (18:27 ET).
- End marker: `phase2-task-20260718-2155-39.*` with 39m 20s duration (ends ~22:34 ET).
- Top-level log confirms terminal success for all six tasks.

---

## Section 7: What Failed Before the Final Run

### 7.1 Missing initial Copilot review request

Earlier phase-2 logic assumed `gh pr ready` implicitly triggered Copilot review. It does not. This caused polling loops to wait on reviews that were never requested.  
Fix: explicit `gh pr edit $PR_NUMBER --add-reviewer "copilot-pull-request-reviewer"` in Step 1 of the phase-2 skill.

### 7.2 Idle-kill session behavior

In failed runs, phase-2 polling exceeded `initial_wait` and then the assistant emitted "I'll check back..." and went idle. Session logs show `assistant.idle` shortly before termination, while poll output continued in the background.

Fixes applied to skills:

1. Explicit "never go idle while waiting" directive.
2. Long blocking polls (`initial_wait >= 600`) for wait steps.
3. Ban on ending turn while relying on background poll completion.

### 7.3 Intermediate run evidence (`20260718-1648`)

- Demonstrated the fixes working: issue #41 merged with `Comments generated: 0`; issue #33 converged through 8 rounds to clean review then merged.
- Also exposed remaining friction (timeouts in polling strategy, handoff to next batch for issue #34).

---

## Section 8: Observations and Recommendations

### 8.1 What worked well

- The final batch reached **100% merge completion** for all target tasks.
- Review-loop convergence was robust even on deep cycles (#39 with 7 rounds).
- Idempotent "skip phase 1 if PR already exists" behavior enabled recovery and reruns.

### 8.2 What did not work well

- Idle/timeout interaction caused repeated early failures before hardening.
- Review-detection/polling logic remained noisy and complex, with repeated long polls.
- OTEL exporter bug removed expected telemetry for post-run diagnostics.

### 8.3 Recommendations

1. Keep explicit reviewer-request step in phase-2 skill as a non-optional invariant.
2. Keep idle-prevention directives in all shepherd skills; treat as runtime safety constraints.
3. Add explicit exit-code checks around critical branch-target operations (`gh pr edit --base`) in `shepherd-task.ps1`.
4. Record one top-level job log for every batch (not only the final successful one) to simplify forensic reconstruction.
5. Continue using CCRA round/comment counts as primary quality metric until OTEL flush issue is fixed.

### 8.4 Comparison to prior Java run (BRK206-01)

The Java post-mortem reported phase-2 sessions spanning 22 minutes to 10+ hours, with PR #43 converging in 7 rounds over 52 minutes. This Python campaign ultimately matched that convergence capability (e.g., #39 with 7 rounds) after runtime/skill hardening, but required additional stabilization due to idle-kill and review-request gaps discovered during early runs.
