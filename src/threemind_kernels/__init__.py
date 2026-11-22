"""Versioned kernel identities, independent of database, GUI and networking."""

__all__ = ["DEFAULT_KERNEL", "describe_kernel", "kernel_catalog", "resolve_kernel"]


def __getattr__(name):
    # Importing one independent kernel must not load every historical implementation.
    if name in __all__:
        from . import registry

        return getattr(registry, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
