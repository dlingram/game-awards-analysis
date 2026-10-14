"""Small statistical helpers used across notebooks."""

import numpy as np

from src.config import N_BOOTSTRAP, RANDOM_SEED


def bootstrap_ci(
    values: np.ndarray, stat=np.mean, n: int = N_BOOTSTRAP, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Return (estimate, lower, upper) percentile bootstrap CI for a statistic."""
    rng = np.random.default_rng(RANDOM_SEED)
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    boots = [stat(rng.choice(values, size=len(values), replace=True)) for _ in range(n)]
    lo, hi = np.percentile(boots, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(stat(values)), float(lo), float(hi)


def lift_pct(pre: float, post: float) -> float:
    """Percent change from pre-window to post-window average."""
    return (post - pre) / pre * 100 if pre else float("nan")
