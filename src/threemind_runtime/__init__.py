"""Host services for an independently deployable ThreeMind model."""

__all__ = ["BIRTH_RULE", "KERNEL60_BIRTH_RULE", "ArtifactCodec", "Runtime", "birth", "birth_rule", "create_engine"]


def __getattr__(name):
    # Loading a single native adapter does not require every historical kernel.
    import importlib

    modules = {
        "ArtifactCodec": "codec", "Runtime": "host", "create_engine": "host",
        "BIRTH_RULE": "inheritance", "KERNEL60_BIRTH_RULE": "inheritance", "birth": "inheritance", "birth_rule": "inheritance",
    }
    if name in modules:
        return getattr(importlib.import_module(f"{__name__}.{modules[name]}"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
