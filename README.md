# whydied

**Linux killed your process. Find out why.**

`whydied` is a Linux CLI tool that runs a child process, observes how it exits, and explains the result using available process and kernel evidence.

The core rule is simple:

> Never present an inference as a fact.

A `SIGKILL` alone does not prove that Linux's OOM killer terminated a process. `whydied` is designed to distinguish observed facts from inferred causes and report uncertainty when the available evidence is incomplete.

## Status

`whydied` is currently under development.

The first release will focus on:

- running a child command
- tracking PID and runtime
- sampling process information from `/proc`
- tracking RSS and peak RSS
- decoding common termination signals
- correlating `SIGKILL` with available Linux OOM evidence
- human-readable reports
- JSON output

Linux only.

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