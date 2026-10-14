"""Event study: abnormal stock returns around The Game Awards ceremonies.

Design (fixed before looking at results):
- Event: each ceremony (2014-2025). Day 0 = first trading day AFTER the ceremony date on the
  stock's own exchange. The show airs Thursday evening Pacific time: after the US close, but
  during Friday trading in Tokyo and before the European open, so day 0 is the first session
  that can react everywhere.
- Normal returns: market model R_i = a + b * R_m, estimated on trading days -250 .. -31,
  benchmark = main index of the stock's exchange. Minimum 120 estimation days.
- Primary outcome: CAR[0,+1]. Secondary: CAR[-5,-1] (leakage), [0,0], [0,+5], [0,+20].
- Unit: one observation per (ceremony, listed company). A company counts as nominated if any
  game it published OR developed was nominated in a game category that year.
- Groups: winner (>= 1 win), nominee (nominated, no wins), not_nominated (listed, no nominations).
- Inference: all companies share the same 12 event dates, so returns are correlated within a
  ceremony. Confidence intervals resample whole ceremony years (cluster bootstrap).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import CLEAN, N_BOOTSTRAP, RANDOM_SEED, RAW

EST_WINDOW = (-250, -31)
MIN_EST_OBS = 120
EVENT_WINDOW = (-10, 20)
CAR_WINDOWS = {"car_pre_m5_m1": (-5, -1), "car_0_0": (0, 0), "car_0_1": (0, 1),
               "car_0_5": (0, 5), "car_0_20": (0, 20)}
PRIMARY = "car_0_1"

# How much of each listed parent's business is games (judgment call, documented):
#   pure_play    - games are the majority of revenue
#   mixed        - games are a large but not majority share (toys, media, ads, office software)
#   conglomerate - games are a small share of a much larger company
TIER = {
    # pure play
    "EA": "pure_play", "ATVI": "pure_play", "TTWO": "pure_play", "UBI.PA": "pure_play",
    "9684.T": "pure_play", "9697.T": "pure_play", "7974.T": "pure_play", "3635.T": "pure_play",
    "9766.T": "pure_play", "CDR.WA": "pure_play", "11B.WA": "pure_play", "BLO.WA": "pure_play",
    "REMEDY.HE": "pure_play", "PDX.ST": "pure_play", "EMBRAC-B.ST": "pure_play",
    "DIB.MI": "pure_play", "ALPUL.PA": "pure_play", "ALDNE.PA": "pure_play",
    "ALATA.PA": "pure_play", "DEVO.L": "pure_play", "EVPL.L": "pure_play", "FDEV.L": "pure_play",
    "TBLD.L": "pure_play", "THUNDR.ST": "pure_play", "CDM.L": "pure_play", "3659.T": "pure_play",
    "251270.KS": "pure_play", "259960.KS": "pure_play", "462870.KS": "pure_play",
    "095660.KQ": "pure_play", "263750.KQ": "pure_play", "NTES": "pure_play",
    "002624.SZ": "pure_play", "7844.T": "pure_play",
    # mixed
    "6460.T": "mixed", "7832.T": "mixed", "9468.T": "mixed", "3888.HK": "mixed",
    "4751.T": "mixed", "2432.T": "mixed",
    # conglomerate
    "MSFT": "conglomerate", "6758.T": "conglomerate", "0700.HK": "conglomerate",
    "AMZN": "conglomerate", "GOOGL": "conglomerate", "META": "conglomerate",
    "NFLX": "conglomerate", "DIS": "conglomerate", "T": "conglomerate",
    "TWX": "conglomerate", "WBD": "conglomerate",
}


# ------------------------------------------------------------------ loading
def load_inputs() -> dict:
    prices = pd.read_csv(RAW / "prices" / "prices_daily.csv", parse_dates=["date"])
    bms = pd.read_csv(RAW / "prices" / "benchmarks_daily.csv", parse_dates=["date"])
    fx = pd.read_csv(RAW / "prices" / "fx_daily.csv", parse_dates=["date"])
    ex_bm = pd.read_csv(RAW / "prices" / "exchange_benchmarks.csv", keep_default_na=False)
    parents = pd.read_csv(CLEAN / "parent_companies.csv", keep_default_na=False)
    noms = pd.read_csv(CLEAN / "nominations_enriched.csv", keep_default_na=False,
                       parse_dates=["ceremony_date"])
    return dict(prices=prices, bms=bms, fx=fx, ex_bm=ex_bm, parents=parents, noms=noms)


def stock_returns(inp: dict) -> dict[str, pd.Series]:
    """Daily simple returns per ticker on its own trading calendar, inside its listing window.
    Warsaw stocks are converted to USD when the Warsaw benchmark is the USD-priced EPOL ETF."""
    prices, parents, fx, ex_bm = inp["prices"], inp["parents"], inp["fx"], inp["ex_bm"]
    usd_bm = set(ex_bm.loc[ex_bm.source_used.str.endswith(":EPOL"), "exchange"])
    out = {}
    for r in parents.itertuples():
        p = prices[prices.ticker == r.ticker].dropna(subset=["adj_close"])
        p = p[p.volume > 0] if (p.volume > 0).mean() > 0.5 else p  # drop stale no-trade rows
        if r.listed_from:
            p = p[p.date >= pd.Timestamp(r.listed_from)]
        if r.listed_to:
            p = p[p.date <= pd.Timestamp(r.listed_to)]
        if len(p) < MIN_EST_OBS:
            continue
        s = p.set_index("date").adj_close.sort_index()
        s = s[~s.index.duplicated()]
        if r.exchange in usd_bm and r.currency != "USD":
            rate = fx[fx.currency == r.currency].set_index("date").usd_per_unit.sort_index()
            s = s * rate.reindex(s.index, method="ffill")
        out[r.ticker] = s.pct_change().dropna()
    return out


def market_returns(inp: dict) -> dict[str, pd.Series]:
    out = {}
    for b, g in inp["bms"].groupby("benchmark"):
        s = g.set_index("date").adj_close.sort_index().dropna()
        out[b] = s[~s.index.duplicated()].pct_change().dropna()
    return out


# ------------------------------------------------------------------ core estimation
def event_abnormal_returns(ri: pd.Series, rm: pd.Series, event_date: pd.Timestamp):
    """Market-model abnormal returns for one stock around one event.
    Returns (daily AR DataFrame, params dict) or (None, reason)."""
    df = pd.concat([ri.rename("r"), rm.rename("m")], axis=1, join="inner").dropna()
    after = np.flatnonzero(df.index > event_date)
    if len(after) == 0:
        return None, "no trading after event"
    pos0 = after[0]
    est = df.iloc[max(0, pos0 + EST_WINDOW[0]): max(0, pos0 + EST_WINDOW[1] + 1)]
    if len(est) < MIN_EST_OBS:
        return None, f"only {len(est)} estimation days"
    if pos0 + 1 >= len(df):
        return None, "event window incomplete"
    beta = np.cov(est.r, est.m, ddof=1)[0, 1] / est.m.var(ddof=1)
    alpha = est.r.mean() - beta * est.m.mean()
    resid = est.r - (alpha + beta * est.m)
    s = resid.std(ddof=2)
    win = df.iloc[max(0, pos0 + EVENT_WINDOW[0]): pos0 + EVENT_WINDOW[1] + 1].copy()
    win["rel_day"] = np.arange(len(win)) + (max(0, pos0 + EVENT_WINDOW[0]) - pos0)
    win["ar"] = win.r - (alpha + beta * win.m)
    params = dict(alpha=alpha, beta=beta, sigma=s, est_n=len(est),
                  day0=df.index[pos0].date())
    return win.reset_index(names="date"), params


def car(ar: pd.DataFrame, lo: int, hi: int, sigma: float):
    w = ar[(ar.rel_day >= lo) & (ar.rel_day <= hi)]
    if len(w) < (hi - lo + 1):
        return np.nan, np.nan
    c = w.ar.sum()
    return c, c / (sigma * np.sqrt(len(w)))  # CAR and standardized CAR


# ------------------------------------------------------------------ build panel
def exposure_by_year(noms: pd.DataFrame) -> pd.DataFrame:
    """Per (year, ticker): nominations and wins where the company published OR developed the game."""
    n = noms[noms.withdrawn.astype(str) != "True"].copy()
    n["goty"] = n.category_std == "Game of the Year"
    n["win"] = n.status == "winner"
    long = pd.concat([
        n.assign(ticker=n.publisher_ticker, role="publisher"),
        n.assign(ticker=n.developer_ticker, role="developer"),
    ])
    long = long[long.ticker != ""]
    # count each nomination once per company even if it both published and developed the game
    long = long.drop_duplicates(subset=["year", "category", "game_id", "ticker"])
    agg = long.groupby(["year", "ticker"]).agg(
        n_noms=("game_id", "size"), n_wins=("win", "sum"),
        goty_nom=("goty", "any"), goty_win=("goty", lambda s: bool((s & long.loc[s.index, "win"]).any())),
        roles=("role", lambda s: ";".join(sorted(set(s)))),
        games_nominated=("game_title", lambda s: "; ".join(sorted(set(s)))),
    ).reset_index()
    wins = long[long.win].groupby(["year", "ticker"]).game_title.agg(
        lambda s: "; ".join(sorted(set(s)))).rename("games_won")
    return agg.merge(wins, on=["year", "ticker"], how="left").fillna({"games_won": ""})


def build_panel(inp: dict | None = None):
    """One row per (ceremony, listed company) with CARs, plus the daily AR panel."""
    inp = inp or load_inputs()
    rets, mkts = stock_returns(inp), market_returns(inp)
    parents = inp["parents"].set_index("ticker")
    bm_of = inp["ex_bm"].set_index("exchange").benchmark
    ceremonies = (inp["noms"][["year", "ceremony_date"]].drop_duplicates()
                  .sort_values("year").itertuples(index=False))
    ceremonies = list(ceremonies)
    expo = exposure_by_year(inp["noms"])
    rows, daily, skipped = [], [], []
    for year, cdate in ceremonies:
        for t, ri in rets.items():
            ex = parents.loc[t, "exchange"]
            rm = mkts.get(bm_of[ex])
            if rm is None:
                skipped.append((year, t, "no benchmark"))
                continue
            ar, info = event_abnormal_returns(ri, rm, pd.Timestamp(cdate))
            if ar is None:
                skipped.append((year, t, info))
                continue
            row = dict(year=year, ceremony_date=pd.Timestamp(cdate).date(), ticker=t,
                       parent_company=parents.loc[t, "parent_company"] if "parent_company" in parents else "",
                       exchange=ex, tier=TIER.get(t, "unclassified"), **info)
            for name, (lo, hi) in CAR_WINDOWS.items():
                c, sc = car(ar, lo, hi, info["sigma"])
                row[name], row["s" + name] = c, sc
            rows.append(row)
            daily.append(ar.assign(year=year, ticker=t)[["year", "ticker", "rel_day", "date", "r", "m", "ar"]])
    panel = pd.DataFrame(rows).merge(expo, on=["year", "ticker"], how="left")
    panel[["n_noms", "n_wins"]] = panel[["n_noms", "n_wins"]].fillna(0).astype(int)
    panel[["goty_nom", "goty_win"]] = panel[["goty_nom", "goty_win"]].fillna(False).astype(bool)
    panel[["roles", "games_nominated", "games_won"]] = panel[["roles", "games_nominated", "games_won"]].fillna("")
    panel["group"] = np.select([panel.n_wins > 0, panel.n_noms > 0], ["winner", "nominee"],
                               "not_nominated")
    daily = pd.concat(daily).merge(panel[["year", "ticker", "group", "tier"]], on=["year", "ticker"])
    return panel, daily, pd.DataFrame(skipped, columns=["year", "ticker", "reason"])


# ------------------------------------------------------------------ inference
def cluster_bootstrap(df: pd.DataFrame, stat, n: int = N_BOOTSTRAP, seed: int = RANDOM_SEED):
    """Resample ceremony years with replacement; returns array of the statistic."""
    rng = np.random.default_rng(seed)
    years = df.year.unique()
    by_year = {y: g for y, g in df.groupby("year")}
    out = np.empty(n)
    for i in range(n):
        pick = rng.choice(years, size=len(years), replace=True)
        out[i] = stat(pd.concat([by_year[y] for y in pick]))
    return out


def summarize(panel: pd.DataFrame, col: str = PRIMARY, by: str = "group") -> pd.DataFrame:
    """Mean CAR per group with t-stat, BMP z, share positive and cluster-bootstrap 95% CI."""
    out = []
    base = panel.dropna(subset=[col])
    lo, hi = base[col].quantile([0.01, 0.99])  # winsorize bounds from the whole sample
    for g, d in base.groupby(by):
        x, sx = d[col], d["s" + col]
        boots = cluster_bootstrap(d, lambda s: s[col].mean()) if d.year.nunique() > 1 else np.array([np.nan])
        out.append({
            by: g, "n_obs": len(d), "n_years": d.year.nunique(),
            "mean_car_pct": 100 * x.mean(), "median_car_pct": 100 * x.median(),
            "winsorized_mean_pct": 100 * x.clip(lo, hi).mean(),
            "share_positive": (x > 0).mean(),
            "p_mean_positive": np.nanmean(boots > 0),
            "t_stat": x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 1 else np.nan,
            "bmp_z": sx.mean() / (sx.std(ddof=1) / np.sqrt(len(sx))) if len(sx) > 1 else np.nan,
            "ci95_low_pct": 100 * np.nanpercentile(boots, 2.5),
            "ci95_high_pct": 100 * np.nanpercentile(boots, 97.5),
        })
    return pd.DataFrame(out)


def compare(panel: pd.DataFrame, a: str, b: str, col: str = PRIMARY, by: str = "group") -> dict:
    """Difference in mean CAR between groups a and b, cluster-bootstrapped by ceremony year."""
    d = panel.dropna(subset=[col])
    d = d[d[by].isin([a, b])]

    def diff(s):
        ga, gb = s.loc[s[by] == a, col], s.loc[s[by] == b, col]
        return ga.mean() - gb.mean() if len(ga) and len(gb) else np.nan

    boots = cluster_bootstrap(d, diff)
    point = diff(d)
    return {"comparison": f"{a} - {b}", "window": col, "diff_pct": 100 * point,
            "ci95_low_pct": 100 * np.nanpercentile(boots, 2.5),
            "ci95_high_pct": 100 * np.nanpercentile(boots, 97.5),
            "p_diff_positive": np.nanmean(boots > 0)}


def regression(panel: pd.DataFrame, col: str = PRIMARY, tiers=("pure_play", "mixed")):
    """CAR on award exposure, with ceremony-year clustered standard errors."""
    import statsmodels.formula.api as smf

    d = panel[panel.tier.isin(tiers)].dropna(subset=[col]).copy()
    d["car_pct"] = 100 * d[col]
    d["goty_win_i"] = d.goty_win.astype(int)
    d["pure_play"] = (d.tier == "pure_play").astype(int)
    m = smf.ols("car_pct ~ n_wins + n_noms + goty_win_i + pure_play", data=d)
    return m.fit(cov_type="cluster", cov_kwds={"groups": d.year})


def run_and_save():
    panel, daily, skipped = build_panel()
    panel.to_csv(CLEAN / "event_study_obs.csv", index=False)
    daily.to_csv(CLEAN / "event_study_daily_ar.csv", index=False)
    return panel, daily, skipped


if __name__ == "__main__":
    p, d, s = run_and_save()
    print(f"{len(p)} company-ceremony observations, {len(s)} skipped")
    print(summarize(p[p.tier == "pure_play"]).round(3).to_string(index=False))
