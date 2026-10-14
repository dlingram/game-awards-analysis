# Copilot instructions: Game Awards Financial Analysis

## Project context
Analysis of how Game Awards nominations and wins (2014-2025) affect game sales, player counts, review scores, and publisher stock returns. Deliverables: Python analysis plus Power BI and Tableau dashboards, built as a portfolio piece.

## Conventions
- Python 3.11+, pandas for data, statsmodels / scipy for inference, matplotlib / seaborn / plotly for charts.
- Code lives in `src/` as importable functions; notebooks only call them and show results.
- Raw data in `data/raw/` is never edited. Cleaning writes to `data/clean/`.
- Use type hints and short docstrings. Format with Ruff.
- Use `pathlib.Path`, never hard-coded absolute paths.
- Dates are timezone-naive UTC `datetime64`. Money is nominal USD unless a column says `_real` (inflation-adjusted).

## Analysis rules
- Treat selection bias as the main threat: nominated games were already succeeding. Prefer event-study and difference-in-differences with matched controls over naive before/after comparisons.
- Report effect sizes with confidence intervals (bootstrap is fine for small samples), not just p-values.
- Run sensitivity checks on the event window (30 / 90 / 180 days).
- Sales figures from third parties are estimates; label them as such in charts and text.

## Data keys
- Games are identified by `game_id` from `data/clean/game_key.csv`. Title matching across sources goes through that key (fuzzy match with rapidfuzz, then manual review).
- Award rows: `year, category, game_id, status` where `status` is `nominee` or `winner`.

## Dashboards
- Power BI and Tableau read the same cleaned files in `data/clean/` so numbers reconcile.
- Color coding: winner, nominee, no award. Keep it consistent across both tools.
