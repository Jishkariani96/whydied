import argparse

from whydied import __version__
from whydied.models import ExitTermination, SignalTermination
from whydied.runner import run_process


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whydied",
        description="Linux killed your process. Find out why.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="child command to run after --",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    command = args.command
    if command and command[0] == "--":
        command = command[1:]

    if not command:
        parser.error("child command is required; use: whydied -- <command> [args...]")

    result = run_process(command)

    print(f"PID: {result.pid}")
    print(f"Runtime: {result.runtime_seconds:.2f}s")
    print(f"Return code: {result.returncode}")

    if isinstance(result.termination, ExitTermination):
        print(f"Termination: exit {result.termination.code}")
    elif isinstance(result.termination, SignalTermination):
        print(f"Termination: {result.termination.name} ({result.termination.number})")
