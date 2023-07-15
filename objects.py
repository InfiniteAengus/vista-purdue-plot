"""Define objects used in purdue_plot.py."""
from enum import Enum
from typing import NamedTuple


class TLColor(str, Enum):
    """Traffic light colors."""

    GREEN = 'green'
    YELLOW = 'yellow'
    RED = 'red'


class Location(NamedTuple):
    """RSU+Bound+Movement."""

    rsu_id: int
    bound: str
    movement: str


class Point(NamedTuple):
    """Simple (x, y) point."""

    x: float
    y: float
