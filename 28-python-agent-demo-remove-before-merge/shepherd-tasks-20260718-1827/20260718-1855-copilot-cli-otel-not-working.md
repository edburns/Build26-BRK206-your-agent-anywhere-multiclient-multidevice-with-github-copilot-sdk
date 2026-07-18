# Bug: OTEL file exporter never flushes when `copilot` is invoked via piped stdin

## Summary

When `copilot --yolo` is invoked with a prompt piped to stdin (without `-p`), the OpenTelemetry file exporter is initialized successfully but never flushes spans to disk on shutdown. The OTEL `.jsonl` file is never created. The same configuration works correctly when using `-p` (non-interactive prompt mode).

## Version

```
copilot 1.0.72-1
Node.js v24.16.0
Windows 11 (also likely affects Linux/macOS — untested)
```

## Reproducer

### ✅ Works: `-p` flag (non-interactive prompt mode)

```powershell
$env:COPILOT_OTEL_FILE_EXPORTER_PATH = "C:\temp\otel-test-works.jsonl"
copilot -p "what is 2+2" --yolo --output-format json 2>&1 | Out-Null
Remove-Item Env:\COPILOT_OTEL_FILE_EXPORTER_PATH
Test-Path "C:\temp\otel-test-works.jsonl"  # True — file created, ~17KB
```

### ❌ Broken: piped stdin (interactive mode with stdin EOF)

```powershell
$env:COPILOT_OTEL_FILE_EXPORTER_PATH = "C:\temp\otel-test-broken.jsonl"
"what is 2+2" | copilot --yolo --output-format json > $null
Remove-Item Env:\COPILOT_OTEL_FILE_EXPORTER_PATH
Test-Path "C:\temp\otel-test-broken.jsonl"  # False — file never created
```

### Bash equivalent

```bash
# Works
COPILOT_OTEL_FILE_EXPORTER_PATH=/tmp/otel-works.jsonl copilot -p "what is 2+2" --yolo --output-format json > /dev/null 2>&1
ls -la /tmp/otel-works.jsonl  # exists

# Broken
COPILOT_OTEL_FILE_EXPORTER_PATH=/tmp/otel-broken.jsonl sh -c 'echo "what is 2+2" | copilot --yolo --output-format json > /dev/null'
ls -la /tmp/otel-broken.jsonl  # does not exist
```

## Diagnostic Evidence

### Process log confirms OTEL is enabled

From `~/.copilot/logs/process-1784413641486-14644.log` (the piped-stdin invocation):

```
2026-07-18T22:27:22.134Z [INFO] OpenTelemetry enabled: exporter=file, source=github.copilot
```

OTEL initializes correctly. The env var is read and the file exporter is selected.

### Shutdown sequence has no OTEL flush

The same log's shutdown sequence:

```
2026-07-18T22:51:40.526Z [DEBUG] [shutdown] Completed dispose: M6 (27ms)
2026-07-18T22:51:40.785Z [DEBUG] [shutdown] Completed dispose: a6 (286ms)
2026-07-18T22:51:40.787Z [DEBUG] [shutdown] Completed dispose: closeSessionStore (2ms)
2026-07-18T22:51:40.788Z [DEBUG] [shutdown] Completed dispose: logger (1ms)
2026-07-18T22:51:40.788Z [DEBUG] [shutdown] Shutdown complete
```

There is **no OTEL exporter dispose/flush step** in the shutdown sequence. The spans collected in memory are never written to disk. No error is logged.

### Other session artifacts ARE written

The same invocation successfully writes:
- `--share` markdown file (144KB) ✅
- `--output-format json` stdout capture (2.8MB) ✅
- Session store updates ✅

Only the OTEL file exporter output is missing.

## Impact

This blocks using `COPILOT_OTEL_FILE_EXPORTER_PATH` for offline/CI observability in any pipeline that invokes `copilot` via piped stdin — which is the standard pattern for orchestration scripts like:

```powershell
$prompt | copilot --yolo --output-format json --share $sharePath > $jsonPath
```

This is the invocation pattern used by the shepherd-task orchestration scripts that drive multi-issue agentic workflows (assign → PR → review → merge).

## Expected Behavior

The OTEL file exporter should flush all buffered spans to the specified file path during the shutdown sequence, regardless of whether the session was started via `-p` or piped stdin.

## Suggested Investigation

1. The `-p` code path likely calls an explicit OTEL shutdown/flush. The piped-stdin (interactive mode with EOF) shutdown path likely skips it.
2. Look for the dispose/shutdown handler that calls the Rust OTEL file exporter's flush — it's probably registered in the `-p` path but not in the interactive-mode graceful-exit path.
3. The shutdown dispose chain (`M6` → `a6` → `closeSessionStore` → `logger`) should include an OTEL exporter flush step before `logger` dispose.
