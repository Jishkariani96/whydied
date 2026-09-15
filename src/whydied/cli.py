import argparse

from whydied import __version__
from whydied.inspect import inspect_process
from whydied.models import ExitTermination, SignalTermination


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

    inspection = inspect_process(command)
    process = inspection.process

    print(f"PID: {process.pid}")
    print(f"Runtime: {process.runtime_seconds:.2f}s")
    print(f"Return code: {process.returncode}")

    if isinstance(process.termination, ExitTermination):
        print(f"Termination: exit {process.termination.code}")
    elif isinstance(process.termination, SignalTermination):
        print(f"Termination: {process.termination.name} ({process.termination.number})")
