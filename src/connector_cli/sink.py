"""Atomic, explicitly overwritable local publication."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

from connector_cli.config import Sink
from connector_cli.interfaces import ExecutionError


class LocalSink:
    def __init__(self, config: Sink) -> None:
        self.path = Path(config.path)

    def write(self, chunks: Iterable[str], *, overwrite: bool = False) -> None:
        path = self.path
        temporary: Path | None = None
        try:
            if not overwrite and (path.exists() or path.is_symlink()):
                raise FileExistsError
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as output:
                temporary = Path(output.name)
                for chunk in chunks:
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if overwrite:
                os.replace(temporary, path)
                temporary = None
            else:
                # Linking publishes atomically without a check-then-replace race.
                os.link(temporary, path)
        except FileExistsError:
            raise ExecutionError(
                "sink: destination exists; use --overwrite to replace it"
            ) from None
        except (OSError, UnicodeError):
            raise ExecutionError("sink: cannot write or publish local output") from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    raise ExecutionError("sink: could not remove temporary output") from None
