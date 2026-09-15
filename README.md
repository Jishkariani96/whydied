# whydied

**Linux killed your process. Find out why.**

`whydied` is a Linux CLI tool that runs a child process, observes how it exits, and explains the result using available process and kernel evidence.

The core rule is simple:

> Never present an inference as a fact.

A `SIGKILL` alone does not prove that Linux's OOM killer terminated a process. `whydied` is designed to distinguish observed facts from inferred causes and report uncertainty when the available evidence is incomplete.

## Status

`whydied` is currently under development.

Currently implemented:

- running a child command
- tracking PID and runtime
- sampling process information from `/proc`
- tracking RSS and peak RSS
- decoding process termination as an exit code or signal
- collecting bounded Linux kernel messages through `journalctl`
- preserving the difference between readable empty kernel logs and unavailable kernel evidence
- parsing explicit kernel OOM victim messages shaped like `Killed process <PID> (<name>)`
- conservatively diagnosing OOM kills only when process termination and kernel evidence agree

Still planned before the first release:

- final human-readable reports
- JSON output
- richer user-facing diagnosis explanations

Linux only.

## Current CLI behavior

The CLI already runs the complete inspection workflow internally:

```text
cli -> inspect -> runner / kernel / diagnose
```

For now, the CLI still prints only process facts:

```text
PID: ...
Runtime: ...s
Return code: ...
Termination: ...
```

Diagnosis and kernel-evidence reporting are intentionally not exposed yet; that belongs to the upcoming reporting layer.

## Diagnosis policy

`whydied` keeps observed facts separate from inferred causes.

An OOM diagnosis is made only when both are true:

1. the child process was observed terminating by `SIGKILL`
2. collected kernel evidence contains an explicit OOM victim event for the same PID

If kernel evidence is unavailable, or if no matching OOM victim event is found, the cause remains unknown. A `SIGKILL` by itself is never treated as proof of OOM.

## Development

Requires Python 3.11+.

Create a virtual environment and install the project with development dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run linting:

```bash
ruff check .
```

Run formatting:

```bash
ruff format .
```

## License

MIT