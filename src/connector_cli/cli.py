"""Command line entrypoint for connector-cli."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from connector_cli.config import ConfigError, load


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="connector-cli")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate a connector file")
    validate.add_argument("file", help="path to a *.connector.yml file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        try:
            load(args.file)
        except ConfigError as exc:
            for error in exc.errors:
                print(f"error: {error}", file=sys.stderr)
            return 1
        print(f"{args.file}: valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
