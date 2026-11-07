"""Charts saved as PNG (matplotlib, headless)."""
from __future__ import annotations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .analyze import correlations  # noqa: E402
from .clean import numeric_columns  # noqa: E402

BLUE, ORANGE, INK, GRID = "#2563eb", "#ea580c", "#1f2937", "#e5e7eb"


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=11, color=INK, fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)


def make_charts(df: pd.DataFrame, out: str | Path) -> list[tuple[str, Path]]:
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    charts = []
    num = numeric_columns(df)
    if num:
        n = min(len(num), 6); cols = 3; rows = int(np.ceil(n / cols))
        fig, axes = plt.subplots(rows, cols, figsize=(11, 3 * rows), squeeze=False)
        for ax, c in zip(axes.flat, num[:n]):
            ax.hist(df[c].dropna(), bins=20, color=BLUE, alpha=0.85, edgecolor="white"); _style(ax, c)
            ax.axvline(df[c].median(), color=ORANGE, linestyle="--", linewidth=1.2, label="median"); ax.legend(frameon=False, fontsize=8)
        for ax in list(axes.flat)[n:]:
            ax.axis("off")
        fig.tight_layout(); p = out / "distributions.png"; fig.savefig(p, dpi=110); plt.close(fig)
        charts.append(("Distributions of numeric columns", p))
    if len(num) >= 2:
        corr = df[num].corr(method="spearman")  # rank-based: robust to outliers
        fig, ax = plt.subplots(figsize=(1.1 * len(num) + 3, 1.0 * len(num) + 2))
        im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
        ax.set_xticks(range(len(num)), num, rotation=45, ha="right"); ax.set_yticks(range(len(num)), num)
        for i in range(len(num)):
            for j in range(len(num)):
                ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8, color="white" if abs(corr.iloc[i, j]) > 0.6 else INK)
        fig.colorbar(im, ax=ax, shrink=0.8); ax.set_title("Correlation matrix (Spearman rank ρ)", loc="left", fontweight="bold")
        fig.tight_layout(); p = out / "correlations.png"; fig.savefig(p, dpi=110); plt.close(fig)
        charts.append(("Correlation matrix", p))
        top = correlations(df)[:1]
        if top:
            a, b = top[0]["a"], top[0]["b"]; pair = df[[a, b]].dropna()
            fig, ax = plt.subplots(figsize=(6.5, 4.2))
            ax.scatter(pair[a], pair[b], s=18, color=BLUE, alpha=0.6)
            m, c0 = np.polyfit(pair[a], pair[b], 1); xs = np.linspace(pair[a].min(), pair[a].max(), 50)
            ax.plot(xs, m * xs + c0, color=ORANGE, linewidth=2, label=f"linear fit (ρ = {top[0]['rho']:.2f})")
            ax.set_xlabel(a); ax.set_ylabel(b); ax.legend(frameon=False); _style(ax, f"Strongest relationship: {a} vs {b}")
            fig.tight_layout(); p = out / "top_scatter.png"; fig.savefig(p, dpi=110); plt.close(fig)
            charts.append((f"{b} vs {a}", p))
    dates = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    if dates and num:
        d = dates[0]; s = df.sort_values(d)
        fig, ax = plt.subplots(figsize=(10, 3.6))
        for c, col in zip(num[:3], [BLUE, ORANGE, "#16a34a"]):
            ax.plot(s[d], s[c], color=col, linewidth=1.2, label=c)
            if len(s) >= 14:
                ax.plot(s[d], s[c].rolling(7, min_periods=3).mean(), color=col, linewidth=2.4, alpha=0.5)
        ax.legend(frameon=False, ncol=3); _style(ax, "Over time (thin = daily, thick = 7-point average)")
        fig.autofmt_xdate(); fig.tight_layout(); p = out / "time_series.png"; fig.savefig(p, dpi=110); plt.close(fig)
        charts.append(("Time series", p))
    cats = [c for c in df.columns if isinstance(df[c].dtype, pd.CategoricalDtype)]
    if cats and num:
        g = cats[0]; y = num[0]
        means = df.groupby(g, observed=True)[y].agg(["mean", "count"]).sort_values("mean")
        fig, ax = plt.subplots(figsize=(7, 0.45 * len(means) + 1.5))
        ax.barh([str(i) for i in means.index], means["mean"], color=BLUE)
        for i, (v, n) in enumerate(zip(means["mean"], means["count"])):
            ax.text(v, i, f"  {v:.1f} (n={n})", va="center", fontsize=8)
        ax.grid(axis="x", color=GRID); ax.spines[["top", "right"]].set_visible(False); ax.set_title(f"Average {y} by {g}", loc="left", fontweight="bold")
        fig.tight_layout(); p = out / "by_category.png"; fig.savefig(p, dpi=110); plt.close(fig)
        charts.append((f"Average {y} by {g}", p))
    return charts
