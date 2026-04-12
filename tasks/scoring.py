"""Shared task reward shaping for OpenEnv validation (scores must lie strictly in (0, 1))."""

from __future__ import annotations

import math
from numbers import Real


def finalize_task_reward(raw: float) -> float:
    """
    Return a finite float strictly between 0 and 1.
    OpenEnv task validators reject 0.0, 1.0, NaN, and inf.
    """
    if not isinstance(raw, Real):
        return 0.5
    x = float(raw)
    if not math.isfinite(x):
        return 0.5
    return min(0.99, max(0.01, x))
