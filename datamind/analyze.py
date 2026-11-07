"""Statistics and automatic pattern finding. Every insight states its evidence and a caveat."""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from .clean import numeric_columns


@dataclass
class Insight:
    kind: str
    score: float      # used to rank insights by importance
    text: str
    evidence: str
    caveat: str = ""


def describe(df: pd.DataFrame) -> pd.DataFrame:
    cols = numeric_columns(df)
    if not cols:
        return pd.DataFrame()
    d = df[cols].describe().T
    d["skew"] = df[cols].skew()
    d["missing"] = df[cols].isna().sum()
    return d.round(3)


def correlations(df: pd.DataFrame, min_n: int = 10) -> list[dict]:
    cols = numeric_columns(df)
    out = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            pair = df[[a, b]].dropna()
            if len(pair) < min_n or pair[a].nunique() < 3 or pair[b].nunique() < 3:
                continue
            r, p = stats.pearsonr(pair[a], pair[b])
            rho, p_rho = stats.spearmanr(pair[a], pair[b])
            out.append({"a": a, "b": b, "r": float(r), "rho": float(rho), "p": float(min(p, p_rho)), "n": len(pair)})
    return sorted(out, key=lambda x: -max(abs(x["r"]), abs(x["rho"])))


def outliers_iqr(s: pd.Series, k: float = 1.5) -> pd.Series:
    q1, q3 = s.quantile([0.25, 0.75]); iqr = q3 - q1
    return (s < q1 - k * iqr) | (s > q3 + k * iqr) if iqr > 0 else pd.Series(False, index=s.index)


def _strength(r: float) -> str:
    a = abs(r)
    return "very strong" if a >= 0.8 else "strong" if a >= 0.6 else "moderate" if a >= 0.4 else "weak"


def find_patterns(df: pd.DataFrame, alpha: float = 0.01) -> list[Insight]:
    ins: list[Insight] = []
    num = numeric_columns(df)
    # 1) Correlations. Use a strict alpha because many pairs are tested (multiple comparisons).
    for c in correlations(df):
        strongest = c["r"] if abs(c["r"]) >= abs(c["rho"]) else c["rho"]
        if abs(strongest) >= 0.3 and c["p"] < alpha:
            direction = "rises" if strongest > 0 else "falls"
            note = " Rank correlation is stronger than Pearson, which suggests outliers or a curved relationship." if abs(c["rho"]) - abs(c["r"]) > 0.1 else ""
            ins.append(Insight("correlation", abs(strongest), f"{c['b']} {direction} as {c['a']} increases ({_strength(strongest)} relationship).{note}",
                               f"Pearson r = {c['r']:.2f}, Spearman ρ = {c['rho']:.2f}, p = {c['p']:.1e}, n = {c['n']}",
                               "Correlation is not causation; another factor may drive both."))
    # 2) Group differences: does a numeric column differ across a category?
    cats = [c for c in df.columns if isinstance(df[c].dtype, pd.CategoricalDtype) or pd.api.types.is_bool_dtype(df[c])]
    for g in cats:
        groups = df[g].dropna().unique()
        if not 2 <= len(groups) <= 8:
            continue
        for y in num:
            samples = [df.loc[df[g] == v, y].dropna() for v in groups]
            if min(len(s) for s in samples) < 5:
                continue
            h, p = stats.kruskal(*samples)
            if p < alpha:
                means = df.groupby(g, observed=True)[y].mean().sort_values()
                lo, hi = means.index[0], means.index[-1]
                pooled = df[y].std() or 1
                d = (means.iloc[-1] - means.iloc[0]) / pooled
                if abs(d) < 0.3:
                    continue
                ins.append(Insight("group_difference", min(1.0, abs(d) / 2), f"{y} differs by {g}: highest for '{hi}' ({means.iloc[-1]:.2f}), lowest for '{lo}' ({means.iloc[0]:.2f}).",
                                   f"Kruskal–Wallis p = {p:.1e}; difference ≈ {d:.2f} standard deviations", "Groups may differ in other ways too (confounding)."))
    # 3) Trends over time
    dates = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    for dcol in dates:
        for y in num:
            sub = df[[dcol, y]].dropna().sort_values(dcol)
            if len(sub) < 12:
                continue
            x = (sub[dcol] - sub[dcol].min()).dt.total_seconds() / 86400
            tau, p = stats.kendalltau(x, sub[y])            # robust to outliers
            slope = stats.theilslopes(sub[y], x)[0]           # median of pairwise slopes
            if p < alpha and abs(tau) >= 0.2:
                change = slope * (x.max() or 1)
                rel = change / abs(sub[y].median()) * 100 if sub[y].median() else 0
                ins.append(Insight("trend", abs(tau) + 0.2, f"{y} {'increased' if change > 0 else 'decreased'} over time by about {abs(change):.2f} ({abs(rel):.0f}%) across the period.",
                                   f"Theil–Sen slope {slope:+.3f}/day, Kendall τ = {tau:.2f}, p = {p:.1e}", "A straight-line trend can hide seasonal cycles."))
    # 4) Outliers
    for y in num:
        s = df[y].dropna()
        if len(s) < 20:
            continue
        mask = outliers_iqr(s, 3.0)  # "extreme" outliers only
        if mask.sum():
            vals = s[mask].sort_values()
            ins.append(Insight("outliers", 0.55, f"{y} has {int(mask.sum())} extreme value(s): {', '.join(f'{v:g}' for v in vals.head(5))}.",
                               f"more than 3×IQR beyond the quartiles (median {s.median():g})", "Check whether these are data-entry errors or real cases before removing them."))
    # 5) Skew and missing data
    for y in num:
        sk = df[y].skew()
        if abs(sk) > 1.5:
            ins.append(Insight("skew", 0.2, f"{y} is {'right' if sk > 0 else 'left'}-skewed, so the median ({df[y].median():g}) describes a typical value better than the mean ({df[y].mean():.2f}).", f"skewness {sk:.2f}"))
    for c in df.columns:
        m = df[c].isna().mean()
        if m >= 0.1:
            ins.append(Insight("missing", m / 2, f"{c} is missing in {m:.0%} of rows.", f"{int(df[c].isna().sum())} of {len(df)}", "If missingness isn't random, results can be biased."))
    return sorted(ins, key=lambda i: -i.score)
