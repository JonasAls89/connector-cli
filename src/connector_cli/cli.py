"""Command line entrypoint for connector-cli."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from connector_cli.config import ConfigError, load
from connector_cli.interfaces import ExecutionError
from connector_cli.runtime import Registry, default_registry, preview, run


def _positive_integer(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="connector-cli")
    sub = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("validate", "validate a connector file offline"),
        ("run", "acquire, transform, and deliver records"),
        ("preview", "read a live sample without writing to the configured sink"),
    ):
        cmd = sub.add_parser(command, help=help_text)
        cmd.add_argument("file", help="path to a *.connector.yml file")
        if command == "run":
            cmd.add_argument(
                "--overwrite", action="store_true", help="replace existing local output"
            )
        if command == "preview":
            cmd.add_argument(
                "--limit", type=_positive_integer, default=10, help="sample size (default: 10)"
            )
    return parser


def main(argv: Sequence[str] | None = None, *, registry: Registry | None = None) -> int:
    args = build_parser().parse_args(argv)
    adapters = default_registry() if registry is None else registry
    try:
        connector = load(args.file)
        adapters.validate(connector)
        if args.command == "validate":
            print(f"{args.file}: valid")
        elif args.command == "run":
            count = run(connector, registry=adapters, overwrite=args.overwrite)
            print(f"delivered {count} records")
        else:
            preview(connector, limit=args.limit, registry=adapters)
    except ConfigError as exc:
        for error in exc.errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    except ExecutionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError):
        print("error: cannot write command output", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
