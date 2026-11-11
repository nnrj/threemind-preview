"""Route structural birth to the preserved historical rule, before any reset."""

from importlib import import_module

from threemind_core import StateImage

from .causal import create, version


def birth(image: StateImage) -> StateImage:
    identity = image.to_dict().get("dynamics")
    number = version(identity)
    # Validate with the kernel owning the image. Validation never materializes
    # modern fields or advances a parent; the original rule owns every reset.
    create(identity, state=image, backend="reference")
    provider = import_module(".causal8.inheritance" if number == 8 else ".causal_compat.inheritance", __package__)
    child = StateImage(provider.birth(image).payload)
    create(identity, state=child, backend="reference")
    return child
