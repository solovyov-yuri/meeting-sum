from __future__ import annotations

import os
import tempfile
from pathlib import Path


def write_text_atomic(path: Path, text: str) -> None:
    """Write text to path atomically via a unique tmp file + rename.

    A unique filename in the same directory ensures the rename is on the same
    filesystem (required for atomic replace) and avoids collisions when multiple
    outputs are written concurrently.
    """
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as f:
            tmp = Path(f.name)
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)
    except Exception:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
        raise
