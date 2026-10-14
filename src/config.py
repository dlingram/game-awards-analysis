"""Project-wide paths and constants."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
REPORTS = ROOT / "reports"

YEARS = list(range(2014, 2026))  # Game Awards ceremonies analyzed
EVENT_WINDOWS_DAYS = (30, 90, 180)  # pre/post ceremony windows
RANDOM_SEED = 42
N_BOOTSTRAP = 5000
