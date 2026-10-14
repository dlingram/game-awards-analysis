# Game Awards Financial Analysis

Does a Game Awards nomination or win move a game's financial performance? This project examines ten years of The Game Awards (2014-2025) using Python for the analysis and Power BI / Tableau for dashboards.

## Question
Does being nominated for, or winning, a Game Awards category change sales, player counts, or publisher stock performance, once release timing and pre-existing popularity are accounted for?

## Hypotheses
- H1: Winners see a larger post-ceremony lift than nominees that did not win.
- H2: Nominees see a larger lift than comparable non-nominated games.
- H3: The effect is larger for indie titles than for AAA titles.

## Design
- Treatment: nominated / won (by category tier).
- Outcomes: Steam concurrent players, estimated sales, review scores, publisher stock returns.
- Windows: 30 / 90 / 180 days before and after the ceremony.
- Method: event study, difference-in-differences vs matched controls, bootstrap / Bayesian intervals.
- Main threat: selection bias (nominated games were already successful).

## Structure
```
data/raw/        untouched source data
data/clean/      cleaned, analysis-ready data
notebooks/       EDA and modeling
src/             reusable cleaning / feature / model code
dashboards/      Power BI (.pbix) and Tableau (.twbx)
reports/         findings and methodology
```

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

## Pipeline
`raw -> src/clean.py -> data/clean -> notebooks/ -> dashboards/`

## Data sources
Document every source, access date, license, and known limitations in `reports/data_sources.md`.

## Status
- [ ] Data sourcing
- [ ] Cleaning and title matching
- [ ] EDA
- [ ] Event study and DiD
- [ ] Power BI dashboard
- [ ] Tableau dashboard
- [ ] Write-up
