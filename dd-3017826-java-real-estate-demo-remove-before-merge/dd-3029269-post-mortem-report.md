# Post-Mortem Report: Agentic Development of Epic #2

**Epic:** [Java demo implementation](https://github.com/edburns/Build26-BRK206-your-agent-anywhere-multiclient-multidevice-with-github-copilot-sdk/issues/2)  
**Report generated:** 2026-07-09  
**Period covered:** 2026-07-08 16:03 UTC → 2026-07-09 13:02 UTC  

---

## Section 1: Executive Summary

Epic #2 tasked a three-agent pipeline with implementing a complete Java EE 11 + OpenLiberty port of the BRK206 real-estate demo across 9 discrete sub-issues (sections 3.1–3.9 of the implementation plan). Two additional sub-issues were aborted before completion and excluded from this analysis.

| Metric | Value |
|--------|-------|
| Sub-issues attempted | 11 |
| Sub-issues completed (merged) | 9 |
| Sub-issues aborted | 2 (#3, #8) |
| Total PRs merged | 9 (PR #14–18, #21–24) |
| Total wall-clock time | ~21 hours (2026-07-08 16:03 – 2026-07-09 13:02 UTC) |
| Total lines added by CCA (across all PRs) | 7,453 |
| Total lines deleted | 124 |
| Total CCRA review rounds | 47 |
| Total inline review comments | 287 |
| Local CLI output tokens | 467,288 |
| Tasks hitting 8-round CCRA cap | 2 (issues #5, #6) |
| Manual interventions | 1 (abort of issue #8 / PR #19) |

All 9 non-aborted tasks resulted in merged PRs. No task required manual code fixes by the human developer.

---

## Section 2: System Architecture

The pipeline consisted of three collaborating agents:

### 2.1 Copilot Coding Agent (CCA)

The CCA performed the initial implementation of each issue. It ran on GitHub's infrastructure, triggered by assigning the issue to Copilot. For 8 of 9 tasks, the `shepherd-task-to-ready` skill (phase 1) monitored the CCA run, polled for PR creation and CI completion, and approved any pending workflow runs. Issue #13's CCA had already completed before the first shepherd batch started.

The CCA produced draft PRs targeting the `edburns/2-build-out-demo` base branch. Initial implementations ranged from 1 commit (issue #11) to 7 commits (issue #20) before any CCRA involvement.

### 2.2 Copilot Code Review Agent (CCRA)

The CCRA (`copilot-pull-request-reviewer[bot]`) reviewed each PR once it was marked "Ready for Review." It posted inline comments identifying bugs, missing requirements, style violations, and constraint violations. The CCRA ran on GitHub's infrastructure asynchronously, typically completing a review within 5–15 minutes of being requested.

### 2.3 Local Copilot CLI (Shepherd)

The local CLI (`copilot --yolo`) ran the `shepherd-task-from-ready-to-merged-to-base` skill (phase 2). For each CCRA review batch, it:

1. Fetched and read all open review comments
2. Applied each fix locally (via `edit`, `create`, or `powershell` tool calls in a worktree)
3. Made a single commit per batch and pushed to the head branch
4. Re-requested a CCRA review
5. Repeated until no comments remained or 8 rounds were reached
6. Merged the PR via `gh pr merge`

The local CLI ran in `--yolo` mode, autonomously approving all tool permission requests. Each phase-2 session was a single long-lived `copilot` process that polled GitHub for CCRA completion between rounds.

---

## Section 3: Per-Task Metrics

### Issue Legend

| Issue | Section | Title | PR |
|-------|---------|-------|----|
| #13 | 3.1 | Project scaffolding: Maven, server.xml, empty source dirs | #14 |
| #4 | 3.2 | Domain model & database seeding: JPA entities, Jakarta Data, JSON loader | #15 |
| #5 | 3.3 | Core agent infrastructure: Phase enum, Agent, AppState, CopilotClientProducer, tools | #16 |
| #6 | 3.4 | WebSocket push infrastructure: `f:websocket` for real-time UI | #17 |
| #7 | 3.5 | JSF pipeline view: static layout with PrimeFaces | #18 |
| #20 | 3.6 | Dynamic UI updates: WebSocket-driven re-render with CSS transitions | #21 |
| #9 | 3.7 | Agent detail view: side panel with session events, tool calls, report | #22 |
| #10 | 3.8 | End-to-end integration testing: full pipeline validation | #23 |
| #11 | 3.9 | Demo polish and README: error handling, auto-removal, docs | #24 |

---

### 3.1 — Issue #13 / PR #14: Project Scaffolding

**Phase 1 (CCA):** PR created at 2026-07-08 00:25 UTC — before the first shepherd batch. CCA created the Maven + OpenLiberty skeleton independently.

**Phase 2 (CCRA + Local CLI):** Shepherd batch `shepherd-tasks-20260708-1203`, session 22m 32s.

#### Throughput & Convergence

| Metric | Value |
|--------|-------|
| CCA initial commits | 2 |
| CCRA rounds | 1 |
| Local CLI fix commits | 1 |
| Total PR commits | 3 |
| 8-round cap hit? | No |

#### PR Stats

| Metric | Value |
|--------|-------|
| Additions | 143 |
| Deletions | 0 |
| Changed files | 7 |
| Inline CCRA comments | 2 |
| Merge time | 2026-07-08 16:25 UTC |
| Wall-clock (phase 2 only) | 22 min |

#### Assessment

The scaffolding task was the simplest of all sub-issues — a Maven POM, `server.xml`, and empty source directories. The CCA produced correct structure on the first try. The single CCRA round caught 2 minor issues (likely naming or packaging), resolved in 1 commit. The low comment count (2) and single review round indicate strong CCA accuracy for this well-bounded task. No constraint violations observed; the output correctly targeted EE 11 and OpenLiberty.

---

### 3.2 — Issue #4 / PR #15: Domain Model & Database Seeding

**Phase 1:** Shepherd batch `shepherd-tasks-20260708-1233` / `shepherd-tasks-20260708-1244`. A quick 13-second phase-1 run (20260708-1234) was aborted and restarted at 16:44 (20260708-1244), running 47 min. CCA produced PR #15 at 16:45 UTC.

**Phase 2:** Shepherd batch `shepherd-tasks-20260708-1340`, session 57m 46s.

#### Throughput & Convergence

| Metric | Value |
|--------|-------|
| CCA initial commits | 2 |
| CCRA rounds | 7 |
| Local CLI fix commits | 7 |
| Total PR commits | 9 |
| 8-round cap hit? | No (converged at round 7) |

#### PR Stats

| Metric | Value |
|--------|-------|
| Additions | 3,485 |
| Deletions | 1 |
| Changed files | 107 |
| Inline CCRA comments | 24 |
| Merge time | 2026-07-08 18:37 UTC |
| Wall-clock (phase 1 + 2) | ~2h 3min |

#### Assessment

This was the most code-intensive task (107 files, 3,485 additions) — the CCA seeded a full H2 database with JPA entities, a Jakarta Data repository, and a JSON loader. The 7 CCRA rounds reflect genuine complexity: the CCRA caught issues across multiple rounds without clear convergence until round 7, suggesting the initial implementation had several layered defects. The large file count (107 files — many likely generated JSON seed data) may have overwhelmed the CCRA's attention, contributing to sustained comment volume. The CCA correctly used Jakarta Data `@Repository` as required by constraints, with CCRA flagging correctness issues in the JPA mappings.

The aborted phase-1 attempt (13-second session, 94 tokens) was a script restart with no code impact.

---

### 3.3 — Issue #5 / PR #16: Core Agent Infrastructure

**Phase 1:** Shepherd batch `shepherd-tasks-20260708-1244`, session 19 min. CCA produced PR #16 at 18:38 UTC.

**Phase 2:** Shepherd batch `shepherd-tasks-20260708-1340`, session 71m 15s.

#### Throughput & Convergence

| Metric | Value |
|--------|-------|
| CCA initial commits | 2 |
| CCRA rounds | **8 (cap reached)** |
| Local CLI fix commits | 8 |
| Total PR commits | 10 |
| 8-round cap hit? | **Yes** |

#### PR Stats

| Metric | Value |
|--------|-------|
| Additions | 399 |
| Deletions | 0 |
| Changed files | 6 |
| Inline CCRA comments | 46 |
| Merge time | 2026-07-08 20:08 UTC |
| Wall-clock (phase 1 + 2) | ~1h 30min |

#### Assessment

The 8-round cap indicates the CCRA and local CLI did not reach a stable state within the allowed iterations. With 46 inline comments across 8 rounds, the average was ~5.75 comments per round — no meaningful convergence trend. This is the second-highest comment density per round after issues #7 and #20.

The core agent infrastructure task required implementing the `@CopilotTool` annotation API (a headline SDK feature) alongside CDI producers and state management. The complexity of interleaving Jakarta EE CDI lifecycle with Copilot SDK session management likely generated recurring CCRA concerns across rounds. Possible oscillation: CCRA may have introduced new comments on code touched in earlier rounds (a common sign of the CCRA re-evaluating context).

The task did merge at round 8, meaning some CCRA comments were likely unaddressed at merge time.

---

### 3.4 — Issue #6 / PR #17: WebSocket Push Infrastructure

**Phase 1:** Shepherd batch `shepherd-tasks-20260708-1244`, session 18 min. CCA produced PR #17 at 20:09 UTC.

**Phase 2:** Shepherd batch `shepherd-tasks-20260708-1340`, session 77m 42s.

#### Throughput & Convergence

| Metric | Value |
|--------|-------|
| CCA initial commits | 2 |
| CCRA rounds | **8 (cap reached)** |
| Local CLI fix commits | 8 |
| Total PR commits | 10 |
| 8-round cap hit? | **Yes** |

#### PR Stats

| Metric | Value |
|--------|-------|
| Additions | 145 |
| Deletions | 37 |
| Changed files | 4 |
| Inline CCRA comments | 32 |
| Merge time | 2026-07-08 21:45 UTC |
| Wall-clock (phase 1 + 2) | ~1h 35min |

#### Assessment

Notably, 37 deletions suggest the CCRA directed the local CLI to remove code (more than any other small-file task). Despite only 4 changed files, the CCRA generated 32 comments over 8 rounds — the highest comments-per-file ratio (8.0) of all tasks. WebSocket integration with JSF's `f:websocket` channel involves tight coupling between server-push semantics and CDI scopes, a notoriously finicky area in Jakarta EE 11. The CCRA likely kept catching scope and lifecycle violations that the local CLI fixed incompletely. Cap hit at 8 rounds; some comments likely unresolved at merge.

---

### 3.5 — Issue #7 / PR #18: JSF Pipeline View

**Phase 1:** Shepherd batch `shepherd-tasks-20260708-1244`, session 12 min. CCA produced PR #18 at 21:46 UTC.

**Phase 2:** Shepherd batch `shepherd-tasks-20260708-1340`, session 66m 42s.

#### Throughput & Convergence

| Metric | Value |
|--------|-------|
| CCA initial commits | 4 |
| CCRA rounds | 6 |
| Local CLI fix commits | 6 |
| Total PR commits | 10 |
| 8-round cap hit? | No (converged at round 6) |

#### PR Stats

| Metric | Value |
|--------|-------|
| Additions | 634 |
| Deletions | 29 |
| Changed files | 6 |
| Inline CCRA comments | 54 |
| Merge time | 2026-07-08 23:04 UTC |
| Wall-clock (phase 1 + 2) | ~1h 18min |

#### Assessment

The highest absolute comment count (54) of all tasks, yet this task converged without hitting the cap. The 4 initial CCA commits (vs. the typical 2) suggest the CCA iterated internally before marking the PR ready. PrimeFaces 15.0 JSF layout involves considerable boilerplate (XHTML, bean bindings, CSS), giving the CCRA many opportunities to comment. The convergence at round 6 (despite 54 comments) suggests the CCRA's concerns were genuinely resolvable — each round produced meaningful reduction, unlike the cap-hit tasks.

---

### 3.6 — Issue #20 / PR #21: Dynamic UI Updates

**Phase 1:** Shepherd batch `shepherd-tasks-20260708-1918`, session 31 min. CCA produced PR #21 at 23:19 UTC.

**Phase 2:** Shepherd batch `shepherd-tasks-20260708-1918`, session 93m 17s.

> **Note:** This issue replaced the aborted issue #8. The original CCA run for issue #8 (PR #19, 7,546 additions across 130 files) was manually aborted after 5 minutes because the scope far exceeded the task specification. Issue #20 was created as a replacement with a tighter prompt.

#### Throughput & Convergence

| Metric | Value |
|--------|-------|
| CCA initial commits | 7 |
| CCRA rounds | 5 |
| Local CLI fix commits | 5 |
| Total PR commits | 12 |
| 8-round cap hit? | No (converged at round 5) |

#### PR Stats

| Metric | Value |
|--------|-------|
| Additions | 1,149 |
| Deletions | 0 |
| Changed files | 11 |
| Inline CCRA comments | 72 |
| Merge time | 2026-07-09 01:23 UTC |
| Wall-clock (phase 1 + 2) | ~2h 4min |

#### Assessment

The highest total inline comment count (72) across all tasks, yet the fewest CCRA rounds of the UI tasks (5). This implies each CCRA round generated many comments but the local CLI addressed them effectively in bulk. The 7 initial CCA commits reflect the complexity of coordinating CSS transitions, WebSocket push events, and PrimeFaces re-render directives. No lines deleted suggests the CCA added net-new code only. Convergence in 5 rounds shows this replacement issue (with a tighter scope than #8) was better suited to agentic implementation.

The manual abort of issue #8 / PR #19 represents the single manual intervention in the entire epic, triggered by CCA scope creep (130 files vs. the expected ~10).

---

### 3.7 — Issue #9 / PR #22: Agent Detail View

**Phase 1:** Shepherd batch `shepherd-tasks-20260708-1918`, session 10 min. CCA produced PR #22 at 01:24 UTC (July 9).

**Phase 2:** Shepherd batch `shepherd-tasks-20260708-1918`, session **602m 53s** (10 hours 2 minutes).

#### Throughput & Convergence

| Metric | Value |
|--------|-------|
| CCA initial commits | 3 |
| CCRA rounds | 7 |
| Local CLI fix commits | 7 |
| Total PR commits | 10 |
| 8-round cap hit? | No (converged at round 7) |

#### PR Stats

| Metric | Value |
|--------|-------|
| Additions | 500 |
| Deletions | 37 |
| Changed files | 8 |
| Inline CCRA comments | 41 |
| Merge time | 2026-07-09 11:35 UTC |
| Wall-clock (phase 1 + 2) | ~10h 12min |

#### Assessment

The 602-minute phase-2 session is the single most extreme outlier in the dataset. The code work itself was modest (500 additions, 8 files, 7 rounds), but the session ran from 01:33 to 11:36 UTC — overnight. The elapsed time reflects **wall-clock wait time for asynchronous CCRA reviews**, not active processing. Each CCRA round took 20–60 minutes on GitHub's side, and with 7 rounds the session naturally spanned the night. Active Local CLI processing time was far shorter.

The session log shows the CLI correctly handling thread resolution, polling loops, and multiple re-review requests without human intervention. The task eventually converged and merged cleanly. This illustrates a systemic issue with the shepherd script: long-running overnight sessions consume a copilot CLI process for extended periods without benefit.

---

### 3.8 — Issue #10 / PR #23: End-to-End Integration Testing

**Phase 1:** Shepherd batch `shepherd-tasks-20260708-1918`, session 17 min. CCA produced PR #23 at 11:36 UTC.

**Phase 2:** Shepherd batch `shepherd-tasks-20260708-1918`, session 35m 1s.

#### Throughput & Convergence

| Metric | Value |
|--------|-------|
| CCA initial commits | 2 |
| CCRA rounds | 4 |
| Local CLI fix commits | 4 |
| Total PR commits | 6 |
| 8-round cap hit? | No (converged at round 4) |

#### PR Stats

| Metric | Value |
|--------|-------|
| Additions | 691 |
| Deletions | 14 |
| Changed files | 7 |
| Inline CCRA comments | 12 |
| Merge time | 2026-07-09 12:28 UTC |
| Wall-clock (phase 1 + 2) | ~52min |

#### Assessment

The lowest comment count (12) among the complex tasks, second only to the scaffolding task (#13). The CCA's test suite for pipeline validation was well-scoped and the CCRA converged quickly. The 4-round convergence with only 3 comments per round on average suggests the CCRA found genuinely discrete, resolvable issues without oscillation. The `FEATURE-VERIFICATION.md` artifact in the PR title suggests the CCA created documentation alongside unit tests.

---

### 3.9 — Issue #11 / PR #24: Demo Polish and README

**Phase 1:** Shepherd batch `shepherd-tasks-20260708-1918`, session 15 min. CCA produced PR #24 at 12:29 UTC.

**Phase 2:** Shepherd batch `shepherd-tasks-20260708-1918`, session 19m 5s.

#### Throughput & Convergence

| Metric | Value |
|--------|-------|
| CCA initial commits | 1 |
| CCRA rounds | 1 |
| Local CLI fix commits | 1 |
| Total PR commits | 2 |
| 8-round cap hit? | No |

#### PR Stats

| Metric | Value |
|--------|-------|
| Additions | 307 |
| Deletions | 6 |
| Changed files | 7 |
| Inline CCRA comments | 4 |
| Merge time | 2026-07-09 13:02 UTC |
| Wall-clock (phase 1 + 2) | ~34min |

#### Assessment

The fastest-completing complex task (34 minutes total). The polish/README task is inherently documentation-heavy, with the CCRA generating only 4 comments in a single round. This reflects the CCRA's strength on documentation: it caught real issues (likely missing sections or broken links) without over-commenting. The 1-round convergence and minimal deletions indicate the CCA produced near-final quality output for documentation tasks.

---

## Section 4: Aggregate Statistics

### 4.1 Summary Table

| Issue | PR | CCA commits | CCRA rounds | CLI commits | Comments | +Lines | −Lines | Cap? | Merged |
|-------|-----|-------------|-------------|-------------|----------|--------|--------|------|--------|
| #13 | #14 | 2 | 1 | 1 | 2 | 143 | 0 | — | 2026-07-08 16:25 |
| #4 | #15 | 2 | 7 | 7 | 24 | 3,485 | 1 | — | 2026-07-08 18:37 |
| #5 | #16 | 2 | **8** | 8 | 46 | 399 | 0 | ✓ | 2026-07-08 20:08 |
| #6 | #17 | 2 | **8** | 8 | 32 | 145 | 37 | ✓ | 2026-07-08 21:45 |
| #7 | #18 | 4 | 6 | 6 | 54 | 634 | 29 | — | 2026-07-08 23:04 |
| #20 | #21 | 7 | 5 | 5 | 72 | 1,149 | 0 | — | 2026-07-09 01:23 |
| #9 | #22 | 3 | 7 | 7 | 41 | 500 | 37 | — | 2026-07-09 11:35 |
| #10 | #23 | 2 | 4 | 4 | 12 | 691 | 14 | — | 2026-07-09 12:28 |
| #11 | #24 | 1 | 1 | 1 | 4 | 307 | 6 | — | 2026-07-09 13:02 |
| **Total** | | **25** | **47** | **47** | **287** | **7,453** | **124** | **2/9** | |

### 4.2 Aggregate Metrics

| Metric | Value |
|--------|-------|
| Total commits by CCA (initial) | 25 |
| Total fix commits by Local CLI | 47 |
| Total merged commits | 72 |
| Total CCRA review rounds | 47 |
| Average CCRA rounds per task | 5.2 |
| Median CCRA rounds per task | 6 |
| Tasks hitting 8-round cap | 2 (issues #5, #6) |
| Total CCRA comments generated | 287 |
| Average comments per task | 31.9 |
| Average comments per CCRA round | 6.1 |
| Tasks requiring manual intervention | 1 (issue #8 abort) |
| Total lines added | 7,453 |
| Total lines deleted | 124 |
| Net lines added | 7,329 |

### 4.3 Convergence Analysis

Convergence (successive CCRA rounds producing fewer comments) was observed in most non-cap tasks. Tasks hitting the cap (#5, #6) showed no clear downward trend — the comment count remained roughly flat across rounds, suggesting oscillation (CCRA re-flagging code touched in earlier rounds).

| Convergence pattern | Tasks |
|--------------------|-------|
| Fast convergence (1–2 rounds) | #13, #11 |
| Gradual convergence (3–5 rounds) | #10, #20 |
| Slow convergence (6–7 rounds) | #4, #7, #9 |
| No convergence (cap hit at 8) | #5, #6 |

---

## Section 5: AI Credits

### 5.1 Local Copilot CLI Token Usage

Token counts were parsed from `data.outputTokens` fields in all JSONL event logs. Input tokens were not recorded in the event stream (field absent = 0 in all files).

| File | Phase | Issue | Output Tokens |
|------|-------|-------|---------------|
| phase1-task-20260708-1234-4.json | 1 | #4 (aborted restart) | 94 |
| phase1-task-20260708-1244-4.json | 1 | #4 | 19,019 |
| phase1-task-20260708-1438-5.json | 1 | #5 | 10,886 |
| phase1-task-20260708-1609-6.json | 1 | #6 | 10,280 |
| phase1-task-20260708-1745-7.json | 1 | #7 | 5,099 |
| phase1-task-20260708-1904-8.json | 1 | #8 (aborted) | 3,119 |
| phase1-task-20260708-1918-20.json | 1 | #20 | 11,213 |
| phase1-task-20260708-2123-9.json | 1 | #9 | 5,777 |
| phase1-task-20260709-0736-10.json | 1 | #10 | 22,667 |
| phase1-task-20260709-0828-11.json | 1 | #11 | 9,561 |
| **Phase 1 subtotal** | | | **97,715** |
| phase2-task-20260708-1203-13.json | 2 | #13 | 4,644 |
| phase2-task-20260708-1332-4.json | 2 | #4 (aborted) | 0 |
| phase2-task-20260708-1340-4.json | 2 | #4 | 42,390 |
| phase2-task-20260708-1457-5.json | 2 | #5 | 54,463 |
| phase2-task-20260708-1628-6.json | 2 | #6 | 49,706 |
| phase2-task-20260708-1757-7.json | 2 | #7 | 56,398 |
| phase2-task-20260708-1950-20.json | 2 | #20 | 65,900 |
| phase2-task-20260708-2133-9.json | 2 | #9 | 69,517 |
| phase2-task-20260709-0753-10.json | 2 | #10 | 18,384 |
| phase2-task-20260709-0843-11.json | 2 | #11 | 8,171 |
| **Phase 2 subtotal** | | | **369,573** |
| **Grand total** | | | **467,288** |

> **Note:** Input tokens were not present in the event log (all values were 0). The `outputTokens` field on `assistant.message` events reflects only the local CLI's generation; CCA and CCRA tokens are tracked separately by GitHub billing.

### 5.2 CCA and CCRA Credits

CCA and CCRA credits are billed by GitHub based on coding agent runs and review rounds respectively. These cannot be directly queried from the repository API. Estimates:

- **CCA credits:** 9 implementations × ~1 coding agent run each (some tasks like #4 may have required multiple CCA runs) = **~9–11 coding agent runs**
- **CCRA credits:** 47 review rounds = **47 CCRA invocations**
- **Local CLI (copilot --yolo):** 20 shepherd sessions (10 phase-1 + 10 phase-2) consuming 467,288 output tokens

---

## Section 6: Wall-Clock Timeline

### 6.1 Overall

- **Start:** 2026-07-08 16:03:31 UTC (first event in `shepherd-tasks-20260708-1203`)
- **End:** 2026-07-09 13:02:40 UTC (last event in `shepherd-tasks-20260708-1918`)
- **Total elapsed:** 20 hours 59 minutes

### 6.2 Batch Timeline

| Batch directory | Start (UTC) | End (UTC) | Issues processed | Notes |
|----------------|-------------|-----------|-----------------|-------|
| `shepherd-tasks-20260708-1203` | 16:03 | 16:26 | #13 (phase 2) | First batch; issue #13 already ready |
| `shepherd-tasks-20260708-1233` | — | — | (empty) | Script directory created but no tasks run |
| `shepherd-tasks-20260708-1244` | 16:34 | 23:09 | #4 (ph1), #5 (ph1), #6 (ph1), #7 (ph1), #8 (ph1, aborted) | Aborted issue #8 ended this batch |
| `shepherd-tasks-20260708-1340` | 17:40 | 23:04 | #4 (ph2), #5 (ph2), #6 (ph2), #7 (ph2) | Longest single batch; 4 sequential phase-2 runs |
| `shepherd-tasks-20260708-1918` | 23:04 | 13:02+1d | #20 (ph1+2), #9 (ph1+2), #10 (ph1+2), #11 (ph1+2) | Ran overnight; issue #9 phase-2 ran 10+ hours |

### 6.3 Per-Issue Timeline

```
2026-07-08 UTC
00:00                                    12:00                              2026-07-09 UTC
|                                        |                                  |
·-- #13 CCA (overnight) --------merge(16:25)
                                         ·-- #4 ph1 ·-- #4 ph2 --------merge(18:37)
                                                     ·-- #5 ph1 ·-- #5 ph2 ----merge(20:08)
                                                                  ·-- #6 ph1 ·-- #6 ph2 --merge(21:45)
                                                                               ·-- #7 ph1 ·-- #7 ph2 --merge(23:04)
                                                                                            ·-- [ABORT #8]
                                                                                              ·-- #20 ph1+ph2 --------merge(01:23+1d)
                                                                                                               ·-- #9 ph1+ph2 (overnight!) ------merge(11:35+1d)
                                                                                                                                              ·-- #10 ph1+ph2 --merge(12:28+1d)
                                                                                                                                                               ·-- #11 ph1+ph2 --merge(13:02+1d)
```

### 6.4 Notable Events

| Time (UTC) | Event |
|-----------|-------|
| 2026-07-08 00:25 | PR #14 created by CCA (pre-batch) |
| 2026-07-08 16:03 | First shepherd batch starts (issue #13 phase 2) |
| 2026-07-08 16:25 | PR #14 merged — issue #13 complete |
| 2026-07-08 16:34 | Phase-1 for issue #4 aborts after 13 seconds (script restart) |
| 2026-07-08 23:04 | Phase-1 for issue #8 manually aborted at 5 min; PR #19 closed |
| 2026-07-08 23:05 | PR #19 (7,546 additions, 130 files) created then immediately closed |
| 2026-07-08 23:09 | Issue #8 aborted; issue #20 created as replacement |
| 2026-07-08 23:19 | New CCA started on replacement issue #20 |
| 2026-07-09 01:23 | PR #21 merged — issue #20 complete |
| 2026-07-09 01:33 | Phase-2 for issue #9 starts (10-hour overnight session begins) |
| 2026-07-09 11:35 | PR #22 merged — issue #9 finally complete after 10h of CCRA wait |
| 2026-07-09 13:02 | PR #24 merged — epic complete |

---

## Section 7: Observations and Recommendations

### 7.1 What Worked Well

**1. End-to-end automation was robust.** All 9 tasks completed without human code intervention. The shepherd pipeline reliably handled PR creation, CI approval, CCRA polling, fix application, commit, and merge across a 21-hour period.

**2. Simple and documentation-heavy tasks benefited most.** Issues #13 (scaffolding, 1 round), #11 (README, 1 round), and #10 (testing, 4 rounds) had the lowest comment counts and fastest wall-clock times. CCA is highly effective when the task has clear, bounded scope.

**3. The abort-and-replace pattern worked for scope creep.** When CCA over-produced for issue #8 (130 files instead of ~10), manual abort and task replacement with a tighter specification (#20) resulted in a correct 11-file implementation that converged in 5 CCRA rounds. This escalation path was effective.

**4. The local CLI applied CCRA comments accurately.** Across 47 rounds and 287 comments, the pipeline produced mergeable code without compilation failures appearing in the logs. The `model.call_failure=1` events seen in issues #5, #6, #7 (phase 2 JSONL) did not result in task failure — the CLI recovered automatically.

**5. Sequential batching of phase-1 and phase-2 worked correctly.** The handoff between shepherd-to-ready (phase 1) and ready-to-merged (phase 2) was seamless; the CCA branch was ready for CCRA as soon as phase 1 completed.

### 7.2 What Didn't Work Well

**1. Two tasks hit the 8-round CCRA cap without convergence.** Issues #5 (core agent) and #6 (WebSocket push) reached 8 rounds with no sign of comment reduction. These tasks likely had CCRA oscillation — fixing one concern caused the CCRA to re-flag related code in the next round. The 8-round hard cap forced merge with potentially unresolved issues.

**2. Issue #8 CCA scope creep.** The CCA interpreted the dynamic UI task too broadly, producing 130 changed files (PR #19). The original issue scope called for approximately 10 files. This was the only manual intervention required in the entire epic, but it cost ~1 hour of clock time. Better issue scoping (explicit file count guidance) or a pre-merge diff check against expected file count would have caught this before PR creation.

**3. Overnight CCRA wait inflated issue #9 wall-clock time to 10+ hours.** The shepherd CLI held a single process open for 10 hours because each CCRA round took 20–60 minutes asynchronously. The pipeline is sequentially blocked on GitHub CCRA review times.

**4. The `shepherd-tasks-20260708-1233` batch directory was created but contained no tasks.** This indicates a failed script start or directory pre-creation without a corresponding run. Minor but worth noting for script reliability.

**5. Input tokens were not recorded.** The JSONL event logs contain `outputTokens` only; `inputTokens` was absent in all 20 files. This prevents accurate cost accounting for the local CLI. The true credit usage is higher than the output-token figures suggest.

**6. Phase-2 batch `shepherd-tasks-20260708-1340` ran 4 tasks sequentially rather than in parallel.** Tasks #4, #5, #6, #7 were shepherded one at a time. Given these were independent issues building on an ordered dependency chain, some parallelism was possible (though serial order was architecturally safer given each PR merged into the base branch for the next).

### 7.3 Recommendations

#### For the CCA (Copilot Coding Agent)

**R1: Add explicit file-count bounds to issue bodies.** Include a `### Expected deliverables` section listing the 3–5 expected new/modified files. The CCA uses the issue body as its primary specification; bounding the output prevents scope creep (cf. issue #8 → 130 files).

**R2: Require the CCA to self-validate against issue constraints before creating the PR.** For this project, constraints include "use `@CopilotTool` annotation API" and "use Jakarta Data `@Repository`". A brief self-check step (grep for prohibited patterns) before the final commit would reduce CCRA round counts.

**R3: Break large tasks into smaller sub-tasks.** Issue #4 (domain model + seeding) generated 107 changed files, which is far too large for accurate CCRA review. Splitting into "JPA entities" and "seed data" sub-tasks would improve review signal quality.

#### For the CCRA (Copilot Code Review Agent)

**R4: Track comment IDs across rounds to detect oscillation.** If the CCRA flags a specific location that was already flagged and supposedly fixed in a prior round, flag it as an escalation rather than a re-comment. The shepherd script could compare new comment bodies against the resolved comment set.

**R5: Categorize comments by severity in a structured format.** The CCRA comments appeared as free-text in review threads; post-processing required manual categorization. A structured `<!-- severity: HIGH -->` annotation in CCRA comments would enable the shepherd to dismiss low-severity comments (style nits) after round 3 and focus remaining rounds on HIGH/MEDIUM severity only.

**R6: Raise or make the round cap adaptive.** The 8-round cap forced merge with unresolved issues for #5 and #6. An adaptive cap — e.g., merge when comment count drops below N or plateaus for 2 consecutive rounds — would be more accurate. Alternatively, raise to 12 rounds for complex tasks while keeping 4 rounds for small tasks.

#### For the Local Copilot CLI Shepherd

**R7: Add asynchronous CCRA polling with process sleep.** Rather than blocking a copilot CLI process for up to 10 hours (issue #9), the shepherd should save state to disk and re-launch between CCRA rounds. This would free the CLI process during the 20–60 minute CCRA review windows.

**R8: Implement a pre-merge diff validation step.** Before merging, the shepherd should verify the final diff against a minimum-viability checklist derived from the issue body (e.g., required class names, required annotations). This catches cases where the 8-round cap forced a merge of incomplete work.

**R9: Dismiss CCRA comments explicitly before re-requesting review.** The current pattern leaves resolved threads "open" in GitHub's UI. Explicit thread resolution (via `gh api`) before each re-review request would give the CCRA a cleaner context and reduce the chance of re-flagging already-addressed comments.

**R10: Log input token counts.** The JSONL event stream should include `inputTokens` alongside `outputTokens` on `assistant.message` events to enable accurate cost accounting.

#### For the Shepherd Orchestration Script

**R11: Detect and reject scope-creep PRs before starting phase 2.** After CCA creates the PR, the shepherd should check `changedFiles` against the expected range. If `changedFiles > threshold` (e.g., 20 for typical sub-issues), abort phase 1 and alert for human review rather than proceeding to the expensive CCRA loop.

**R12: Run issues in parallel where the dependency graph allows.** Issues #10 and #11 could have run in parallel (neither depends on the other). A dependency-aware scheduler would reduce total wall-clock time.

**R13: Record batch start/end events in a structured log.** The empty `shepherd-tasks-20260708-1233` directory and the abrupt phase-1 restart for issue #4 suggest the orchestration script lacked adequate state tracking. A persistent run manifest (JSON) recording issue→PR→phase→status would enable safe restart without re-doing completed work.

### 7.4 Patterns Observed

- **Simple, well-bounded tasks converge fastest.** Scaffolding, documentation, and testing tasks (1–4 rounds) had the lowest defect density in CCA output.
- **Infrastructure/plumbing tasks drive the highest CCRA comment counts.** WebSocket, CDI, and JSF bean wiring (issues #5, #6, #7) generated the highest comments-per-file ratios because these areas involve subtle lifecycle constraints that are hard to get right in one pass.
- **Large file count impairs CCRA signal quality.** Issue #4 (107 files) had 24 comments over 7 rounds; the CCRA likely could not deeply review all 107 files in each pass, leading to incomplete but persistent feedback.
- **CCRA reviews under overnight conditions have unpredictable latency.** Issue #9's 10-hour session was not unusually complex — the long duration was purely an artifact of 7 asynchronous CCRA review cycles during low-traffic hours. Planning for overnight execution should include asynchronous shepherd checkpointing.
- **The three-agent pipeline is viable for complex greenfield development** but needs tooling improvements (scope guards, adaptive round caps, async state persistence) to operate reliably at scale without human oversight.
