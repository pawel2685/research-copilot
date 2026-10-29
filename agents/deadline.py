"""A deadline for one run, with an injectable clock so tests never sleep."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Deadline:
    """A point in time (on `clock`) after which the run is out of budget."""

    at: float
    clock: Callable[[], float] = field(default=time.monotonic, repr=False)

    @classmethod
    def after(
        cls, seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> Deadline:
        """Build a deadline `seconds` from now."""
        return cls(at=clock() + seconds, clock=clock)

    def left(self) -> float:
        """Seconds left. Negative when the deadline has passed."""
        return self.at - self.clock()

    def should_skip(self, min_left_s: float) -> bool:
        """True when less than `min_left_s` seconds are left."""
        return self.left() < min_left_s
