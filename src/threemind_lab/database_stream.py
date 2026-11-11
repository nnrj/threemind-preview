"""Bounded PostgreSQL result streams with explicit early-exit cleanup."""

from contextlib import closing, contextmanager

import psycopg


@contextmanager
def closing_iterator(values):
    iterator = iter(values)
    try:
        yield iterator
    finally:
        close = getattr(iterator, "close", None)
        if close is not None:
            close()


def stream_rows(connection, query, params, *, batch=8):
    # libpq chunk mode avoids a FETCH round trip for every small batch. Older
    # libpq versions retain bounded memory through single-row mode. The stream
    # exclusively owns this connection until consumed/closed; callers must close
    # their iterator before leaving the transaction when consumption fails.
    size = batch if psycopg.capabilities.has_stream_chunked() else 1
    with connection.cursor() as cursor, closing(cursor.stream(query, params, size=size)) as records:
        yield from records
