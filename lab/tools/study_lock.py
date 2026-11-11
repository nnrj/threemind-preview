"""OS-released exclusive worker lock for a single study directory."""

import os
from pathlib import Path


def worker_lock(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stream = (directory / "worker.lock").open("a+b")
    if stream.seek(0, 2) == 0:
        stream.write(b"0")
        stream.flush()
    stream.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        stream.close()
        raise RuntimeError("another simulation worker holds this study lock") from error
    return stream  # closing the handle releases the lock, including after a crash
