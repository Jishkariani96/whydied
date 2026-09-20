import argparse

from whydied import __version__
from whydied.inspect import inspect_process
from whydied.report import format_report


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

    try:
        inspection = inspect_process(command)
    except OSError as exc:
        parser.error(f"failed to start child process {command[0]!r}: {exc}")

    print(format_report(inspection))
