# whydied

**Evidence-based process termination diagnostics for Linux.**

`whydied` runs a command, observes how it terminates, samples its memory use, and
uses available kernel evidence to explain the result. It preserves the child's
standard input, output, and error streams and propagates a shell-compatible exit
status.

The core rule is:

> Never present an inference as a fact.

`whydied` is Linux-only and requires Python 3.11 or newer.

## Installation from source

```bash
git clone https://github.com/Jishkariani96/whydied.git
cd whydied
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

For an editable development installation, use `python -m pip install -e
".[dev]"` instead.

## Usage

```text
whydied -- <command> [args...]
```

The `--` separates whydied's arguments from the child command. Child
stdin/stdout/stderr are inherited unchanged.

```bash
whydied -- python -c 'print("hello")'
whydied -- ./my-program --verbose
```

## Example reports

PIDs, runtimes, and memory values vary by run. Memory can be unavailable for a
process that exits before it can be sampled.

### Clean exit

```text
Process:
  PID: 24101
  Runtime: 0.05s
  Return code: 0
  Termination: exit 0

Diagnosis:
  Cause: clean exit

Memory:
  RSS: 8.42 MiB
  Peak RSS: 8.42 MiB
  Peak swap: 0.00 MiB
```

### Non-zero exit

```text
Process:
  PID: 24118
  Runtime: 0.05s
  Return code: 7
  Termination: exit 7

Diagnosis:
  Cause: non-zero exit
  Detail: process exited with non-zero status 7

Memory:
  RSS: 8.51 MiB
  Peak RSS: 8.51 MiB
  Peak swap: 0.00 MiB
```

### Signal termination

```text
Process:
  PID: 24132
  Runtime: 0.05s
  Return code: -15
  Termination: SIGTERM (15)

Diagnosis:
  Cause: signal termination
  Detail: process received SIGTERM (termination request)

Memory:
  RSS: 1.71 MiB
  Peak RSS: 1.71 MiB
  Peak swap: 0.00 MiB
```

The report also provides human-readable explanations for common terminations
such as `SIGABRT` and `SIGSEGV`.

### Confirmed OOM kill

```text
Process:
  PID: 24203
  Runtime: 3.47s
  Return code: -9
  Termination: SIGKILL (9)

Diagnosis:
  Cause: OOM kill
  Detail: process received SIGKILL
  Kernel evidence: matching OOM victim found

Memory:
  RSS: 912.00 MiB
  Peak RSS: 1018.34 MiB
  Peak swap: 64.00 MiB
```

## Diagnosis policy

`whydied` separates observed termination facts from conclusions about cause. It
classifies a run as one of:

- **clean exit**: the child exited with status 0
- **non-zero exit**: the child exited with a non-zero status
- **signal termination**: the child was terminated by a signal other than
  `SIGKILL`
- **OOM kill**: the child received `SIGKILL`, the kernel journal names the same
  PID as an OOM victim, and whydied verified that it is running in the initial
  PID namespace
- **unknown**: the child received `SIGKILL`, but the evidence needed to identify
  its cause is missing or unavailable

A `SIGKILL` alone does **not** prove an OOM kill. It may come from a user, a
service manager, a resource controller, or another source. `whydied` confirms
OOM only when the observed `SIGKILL` and an explicit matching kernel OOM victim
PID agree and the PIDs are known to come from the initial PID namespace.

Before starting the child, `whydied` captures a kernel journal cursor and later
examines events after it. The cursor excludes earlier evidence, but post-exit
collection and retries can extend the evidence window briefly beyond child
termination. If journal evidence cannot be read, no matching victim exists, or
PID comparability cannot be established, the diagnosis remains unknown instead
of claiming OOM.

## Memory fields

Memory data is sampled from `/proc/<pid>/status` while the child runs and is
reported in MiB:

- **RSS**: resident memory in the latest observed sample (`VmRSS`)
- **Peak RSS**: the process's resident high-water mark (`VmHWM`)
- **Peak swap**: the highest sampled swapped-memory value (`VmSwap`)

Individual fields, or the entire memory section, may be unavailable when the
kernel does not expose them or the process exits before sampling.

## Exit status

After printing the report, `whydied` exits using wrapper-friendly semantics:

- a normally exiting child propagates its exit code
- a signal-terminated child maps to `128 + signal number` (for example,
  `SIGTERM` becomes 143)
- a missing command or child launch failure exits 2 with a concise error
- Ctrl+C exits 130 without a whydied traceback

Ctrl+C and other terminal interaction retain the existing process group and
standard streams, so the terminal delivers signals naturally to both whydied
and its child.

## Limitations

- Linux and `/proc` are required.
- Kernel OOM correlation depends on `journalctl`, permission to read the kernel
  journal, and retention of the relevant event.
- Memory is sampled, so very short-lived processes may have no memory data and
  transient values can be missed.
- OOM confirmation is disabled outside the initial PID namespace, or when the
  PID namespace cannot be verified. v0.1.0 does not translate container-local
  PIDs to host PIDs.
- OOM confirmation matches the direct child's PID; it does not diagnose an OOM
  kill of an unrelated process or descendant as the child's OOM kill.
- A cause can remain unknown when the available evidence is insufficient.

Machine-readable JSON output is possible future work; it is not part of
v0.1.0.

## Development

Install development dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the release checks:

```bash
pytest
ruff check .
ruff format --check .
git diff --check
```

## License

Licensed under the MIT License. See [LICENSE](LICENSE).
