"""Core: the grouped Reddit API and its data models."""

from .api import Reddit
from . import models

__all__ = ["Reddit", "models"]
