"""Host execution selection, deliberately outside scientific configuration."""

from threemind_kernels.registry import resolve_kernel


def select_execution(kernel_id, requested=None, *, default="native"):
    descriptor = resolve_kernel(kernel_id)
    requested = dict(requested or {})
    if set(requested) - {"backend"}:
        raise ValueError("unsupported host execution setting")
    backend = requested.get("backend")
    if backend is not None and backend not in descriptor.backends:
        raise ValueError(f"{kernel_id} does not support backend {backend!r}; no automatic fallback")
    if backend is None:
        backend = default if default in descriptor.backends else descriptor.backends[0]
    return {"backend": backend}


def run_backend(row, *, default="native"):
    """Unrecorded historical choices retain the previous host-default policy."""
    return select_execution(row["spec"]["kernel_id"], row.get("execution"), default=default)["backend"]
