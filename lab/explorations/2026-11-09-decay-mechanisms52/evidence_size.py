"""Exact logical-byte accounting using one cached stat per directory entry.

Every directory entry is counted, including each hard link, just as the old
Path.rglob/is_file/stat expression. Reparse points are rejected explicitly;
these study trees contain no links that should be followed elsewhere.
"""
import os
import stat


def logical_bytes(root):
    pending=[os.fspath(root)];total=0;files=0
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                info=entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise ValueError('evidence reparse point requires review: '+entry.path)
                if stat.S_ISDIR(info.st_mode):pending.append(entry.path)
                elif stat.S_ISREG(info.st_mode):total+=info.st_size;files+=1
                else:raise ValueError('unsupported evidence entry: '+entry.path)
    return dict(logical_bytes=total,files=files)
