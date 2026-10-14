"""Charts for the event study (matplotlib, static PNGs for the notebook and README).

Colors: first three slots of the validated reference palette (blue, orange, aqua), which pass
color-blind separation checks for every pair. Text stays in ink colors, never series colors.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
GROUP_COLOR = {"winner": "#2a78d6", "nominee": "#eb6834", "not_nominated": "#1baf7a"}
GROUP_LABEL = {"winner": "Won an award", "nominee": "Nominated, no win",
               "not_nominated": "Not nominated"}
GROUP_ORDER = ["winner", "nominee", "not_nominated"]


def _style(ax, title, subtitle=None):
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=22 if subtitle else 8,
                 fontweight="semibold")
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=INK_2, va="bottom")


def caar_chart(daily: pd.DataFrame, title: str, start: int = -10, end: int = 20, ax=None):
    """Average cumulative abnormal return by group, from `start` to `end` trading days."""
    d = daily[(daily.rel_day >= start) & (daily.rel_day <= end)]
    mean_ar = d.groupby(["group", "rel_day"]).ar.mean().unstack(0)
    caar = 100 * mean_ar.cumsum()
    counts = d.drop_duplicates(["year", "ticker"]).group.value_counts()
    ax = ax or plt.subplots(figsize=(8.5, 4.6), dpi=130)[1]
    _style(ax, title, "Average cumulative abnormal return (%), trading days around ceremony night")
    ax.axhline(0, color=INK_2, linewidth=0.8)
    ax.axvline(0, color=INK_2, linewidth=0.8, linestyle=(0, (3, 3)))
    ax.text(0.3, ax.get_ylim()[1] if False else 0, "", color=INK_2)
    for g in GROUP_ORDER:
        if g not in caar:
            continue
        ax.plot(caar.index, caar[g], color=GROUP_COLOR[g], linewidth=2,
                label=f"{GROUP_LABEL[g]} (n={counts.get(g, 0)})", solid_capstyle="round")
        ax.annotate(GROUP_LABEL[g], (caar.index[-1], caar[g].iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9, color=INK)
    ymin, ymax = ax.get_ylim()
    ax.text(0.2, ymax, "Day 0: first trading day\nafter the ceremony", fontsize=8,
            color=INK_2, va="top")
    ax.set_xlabel("Trading days relative to the ceremony", color=INK_2, fontsize=9)
    ax.set_xlim(start, end + 7)
    ax.legend(loc="lower left", frameon=False, fontsize=9, labelcolor=INK)
    return ax


def estimate_chart(summary: pd.DataFrame, title: str, by: str = "group", ax=None):
    """Dot = mean CAR, whisker = cluster-bootstrap 95% CI, one row per group."""
    s = summary.set_index(by).reindex([g for g in GROUP_ORDER if g in set(summary[by])])
    ax = ax or plt.subplots(figsize=(8.5, 2.2 + 0.45 * len(s)), dpi=130)[1]
    _style(ax, title, "Mean 2-day abnormal return (%) with 95% confidence interval "
                      "(resampling whole ceremony years)")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.axvline(0, color=INK_2, linewidth=0.8)
    y = np.arange(len(s))[::-1]
    for yi, (g, r) in zip(y, s.iterrows()):
        c = GROUP_COLOR.get(g, INK_2)
        ax.plot([r.ci95_low_pct, r.ci95_high_pct], [yi, yi], color=c, linewidth=2,
                solid_capstyle="round")
        ax.plot(r.mean_car_pct, yi, "o", color=c, markersize=9, markeredgecolor=SURFACE,
                markeredgewidth=2)
        ax.annotate(f"{r.mean_car_pct:+.2f}%  (n={int(r.n_obs)})", (r.ci95_high_pct, yi),
                    xytext=(8, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
    ax.set_yticks(y, [GROUP_LABEL.get(g, g) for g in s.index], color=INK, fontsize=10)
    ax.set_ylim(-0.7, len(s) - 0.3)
    lo, hi = s.ci95_low_pct.min(), s.ci95_high_pct.max()
    pad = 0.25 * (hi - lo)
    ax.set_xlim(min(lo - pad, -pad), hi + 2.2 * pad)
    ax.spines["bottom"].set_visible(False)
    return ax
