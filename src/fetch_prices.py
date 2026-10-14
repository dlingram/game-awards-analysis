"""Download daily stock prices, FX rates and market benchmarks for every listed
parent company in data/clean/parent_companies.csv.

Run from the project root:
    python -m src.fetch_prices            # download everything
    python -m src.fetch_prices --dry-run  # just list what would be downloaded

Outputs (data/raw/prices/):
    prices_daily.csv      date, ticker, open, high, low, close, adj_close, volume
    fx_daily.csv          date, currency, usd_per_unit
    benchmarks_daily.csv  date, benchmark, close, adj_close
    exchange_benchmarks.csv  exchange -> benchmark index used for abnormal returns
    download_log.csv      one row per symbol: rows, first/last date, status
"""
import argparse
import sys
import time

import pandas as pd

from src.config import CLEAN, RAW

START = "2014-06-01"  # six months before the first ceremony (Dec 2014)
END = pd.Timestamp.today().strftime("%Y-%m-%d")
OUT = RAW / "prices"

# Market index used as the "normal return" benchmark for each exchange
EXCHANGE_BENCHMARK = {
    "NASDAQ": "^GSPC", "NYSE": "^GSPC",
    "Tokyo": "^N225",
    "Hong Kong": "^HSI",
    "Shenzhen": "399001.SZ",
    "Korea (KOSPI)": "^KS11", "Korea (KOSDAQ)": "^KQ11",
    "Euronext Paris": "^FCHI", "Euronext Growth Paris": "^FCHI",
    "Borsa Italiana": "FTSEMIB.MI",
    "Warsaw": "WIG20",
    "Nasdaq Stockholm": "^OMX",
    "Nasdaq Helsinki": "^OMXH25",
    "London AIM": "^FTSE",
}

# If Yahoo has nothing for a symbol, try these sources in order: ("yahoo"|"stooq", symbol).
# Stooq keeps price history for delisted companies; its prices have no separate
# adjusted close, so adj_close = close for those rows.
FALLBACKS = {
    # Delisted US stocks: Tiingo keeps their history (free key, read from .env)
    "ATVI": [("tiingo", "atvi")],
    "TWX": [("tiingo", "twx")],
    "WIG20": [("yahoo", "^WIG20"), ("stooq", "wig20"),
              ("yahoo", "EPOL")],  # EPOL = iShares MSCI Poland ETF (USD) as last resort
}
# Delisted non-US stocks with no free source; excluded from the stock analysis
# (CDM.L: 4 nominations, THUNDR.ST: 2 nominations). See reports/data_dictionary.md.
KNOWN_GAPS = {"CDM.L", "THUNDR.ST"}


def tiingo_key() -> str:
    """TIINGO_API_KEY from the environment, or from a .env file in the project root."""
    import os

    from src.config import ROOT

    key = os.environ.get("TIINGO_API_KEY", "")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith("TIINGO_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    return key


def fetch_tiingo(symbol: str) -> pd.DataFrame:
    """Daily prices from Tiingo (includes delisted US tickers); empty DataFrame on failure."""
    import requests

    key = tiingo_key()
    if not key:
        print(f"  ! tiingo {symbol}: no TIINGO_API_KEY found (add it to the .env file)")
        return pd.DataFrame()
    url = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices"
    try:
        r = requests.get(url, params={"startDate": START, "endDate": END, "token": key},
                         timeout=60)
        data = r.json()
    except Exception as exc:
        print(f"  ! tiingo {symbol}: {exc}")
        return pd.DataFrame()
    if not isinstance(data, list) or not data:
        print(f"  ! tiingo {symbol}: {str(data)[:120]!r}")
        return pd.DataFrame()
    df = pd.DataFrame(data).rename(columns={"adjClose": "adj_close"})
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.date
    return df[["date", "open", "high", "low", "close", "adj_close", "volume"]]


def fetch_stooq(symbol: str) -> pd.DataFrame:
    """Daily OHLCV from Stooq's free CSV download; empty DataFrame on failure."""
    import io

    import requests

    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    except Exception as exc:
        print(f"  ! stooq {symbol}: {exc}")
        return pd.DataFrame()
    if not r.text.startswith("Date"):
        print(f"  ! stooq {symbol}: {r.text.strip()[:120]!r}")
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO(r.text)).rename(columns=str.lower)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[(df.date >= pd.Timestamp(START).date()) & (df.date <= pd.Timestamp(END).date())]
    df["adj_close"] = df["close"]
    if "volume" not in df:
        df["volume"] = 0
    return df[["date", "open", "high", "low", "close", "adj_close", "volume"]]


def fetch_any(symbol: str) -> tuple[pd.DataFrame, str]:
    """Try Yahoo, then any fallbacks. Returns (data, 'source:symbol' actually used)."""
    attempts = [] if symbol == "WIG20" else [("yahoo", symbol)]
    attempts += FALLBACKS.get(symbol, [])
    source_fn = {"yahoo": fetch, "stooq": fetch_stooq, "tiingo": fetch_tiingo}
    for source, sym in attempts:
        df = source_fn[source](sym)
        if len(df):
            return df, f"{source}:{sym}"
    return pd.DataFrame(), ""


def fetch(symbol: str) -> pd.DataFrame:
    """Daily OHLCV for one symbol; empty DataFrame if Yahoo has no data."""
    import yfinance as yf

    for attempt in range(3):
        try:
            df = yf.Ticker(symbol).history(start=START, end=END, auto_adjust=False,
                                           actions=False)
            break
        except Exception as exc:  # network hiccup -> retry
            if attempt == 2:
                print(f"  ! {symbol}: {exc}")
                return pd.DataFrame()
            time.sleep(2)
    if df.empty:
        return df
    df = df.reset_index().rename(columns={"Date": "date", "Open": "open", "High": "high",
                                          "Low": "low", "Close": "close",
                                          "Adj Close": "adj_close", "Volume": "volume"})
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.date
    return df[["date", "open", "high", "low", "close", "adj_close", "volume"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    parents_path = CLEAN / "parent_companies.csv"
    if not parents_path.exists():
        sys.exit(f"Can't find {parents_path}. Unzip game_key_tables.zip into the project root first.")
    parents = pd.read_csv(parents_path, encoding="utf-8-sig", keep_default_na=False)

    tickers = sorted(parents.ticker.unique())
    currencies = sorted(set(parents.currency) - {"USD"})
    fx_symbols = {c: f"{c}USD=X" for c in currencies}
    benchmarks = sorted({EXCHANGE_BENCHMARK[e] for e in parents.exchange})
    missing_bm = sorted(set(parents.exchange) - set(EXCHANGE_BENCHMARK))
    if missing_bm:
        sys.exit(f"No benchmark defined for exchange(s): {missing_bm}")

    print(f"{len(tickers)} stocks, {len(fx_symbols)} currencies, {len(benchmarks)} benchmarks")
    print(f"Date range: {START} to {END}")
    if args.dry_run:
        print("Stocks:", tickers)
        print("FX:", list(fx_symbols.values()))
        print("Benchmarks:", benchmarks)
        return

    OUT.mkdir(parents=True, exist_ok=True)
    log, prices, fx, bms = [], [], [], []

    def record(kind, symbol, df, used=""):
        status = "ok" if len(df) else "NO DATA"
        log.append({"kind": kind, "symbol": symbol, "source_used": used or f"yahoo:{symbol}",
                    "rows": len(df),
                    "first_date": df.date.min() if len(df) else "",
                    "last_date": df.date.max() if len(df) else "", "status": status})
        note = f"  (via {used})" if used and used != f"yahoo:{symbol}" else ""
        print(f"  {kind:9} {symbol:13} {len(df):5} rows  {status}{note}")

    for t in tickers:
        if t in KNOWN_GAPS:
            print(f"  stock     {t:13}     -  skipped (known gap, no free source)")
            continue
        df, used = fetch_any(t)
        record("stock", t, df, used)
        if len(df):
            prices.append(df.assign(ticker=t))
    for cur, sym in fx_symbols.items():
        df = fetch(sym)
        record("fx", sym, df)
        if len(df):
            fx.append(df[["date", "close"]].rename(columns={"close": "usd_per_unit"})
                      .assign(currency=cur))
    bm_used = {}
    for b in benchmarks:
        df, used = fetch_any(b)
        record("benchmark", b, df, used)
        bm_used[b] = used
        if len(df):
            bms.append(df[["date", "close", "adj_close"]].assign(benchmark=b))

    if prices:
        pd.concat(prices)[["date", "ticker", "open", "high", "low", "close", "adj_close",
                           "volume"]].to_csv(OUT / "prices_daily.csv", index=False)
    if fx:
        pd.concat(fx)[["date", "currency", "usd_per_unit"]].to_csv(OUT / "fx_daily.csv",
                                                                   index=False)
    if bms:
        pd.concat(bms)[["date", "benchmark", "close", "adj_close"]].to_csv(
            OUT / "benchmarks_daily.csv", index=False)
    pd.DataFrame([(ex, b, bm_used.get(b, "")) for ex, b in sorted(EXCHANGE_BENCHMARK.items())],
                 columns=["exchange", "benchmark", "source_used"]).to_csv(
        OUT / "exchange_benchmarks.csv", index=False)
    if bm_used.get("WIG20", "").endswith("EPOL"):
        print("Note: Warsaw benchmark fell back to EPOL (priced in USD) - compare Polish "
              "stocks in USD returns.")
    log_df = pd.DataFrame(log)
    log_df.to_csv(OUT / "download_log.csv", index=False)

    bad = log_df[log_df.status != "ok"]
    print(f"\nDone. {len(log_df) - len(bad)} of {len(log_df)} symbols downloaded "
          f"({len(KNOWN_GAPS)} known gaps skipped: {', '.join(sorted(KNOWN_GAPS))}).")
    if len(bad):
        print("No data for:", ", ".join(bad.symbol))
        print("Paste this list back to Claude to sort out replacements.")


if __name__ == "__main__":
    main()
