"""ThreeMind's database-free, anonymous dynamics reference implementation."""

from .engine import Engine, StateImage
from .spec import Config, Stimulus

__all__ = ["Config", "Engine", "StateImage", "Stimulus"]
__version__ = "2.0.0"
