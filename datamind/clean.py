"""Loading and cleaning messy tabular data, with a log of every change made."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

MISSING_TOKENS = {"", "na", "n/a", "null", "none", "-", "?", "nan", "missing"}


@dataclass
class CleaningLog:
    steps: list[str] = field(default_factory=list)

    def add(self, msg: str) -> None:
        self.steps.append(msg)


def load(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(p, dtype=str)
    if p.suffix.lower() == ".json":
        return pd.read_json(p, dtype=False).astype(str)
    sep = "\t" if p.suffix.lower() == ".tsv" else None
    return pd.read_csv(p, dtype=str, sep=sep, engine="python", keep_default_na=False)


def snake(name: str) -> str:
    name = str(name)
    for a, b in {"µ": "u", "³": "3", "²": "2", "%": " pct", "#": " num", "°": " deg"}.items():
        name = name.replace(a, b)
    s = re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip()).strip("_").lower()
    return s or "column"


_NUM = re.compile(r"^[\s$€£]*[-+]?(\d{1,3}(,\d{3})+|\d+)?(\.\d+)?\s*%?\s*$")


def _to_number(s: pd.Series) -> pd.Series:
    t = s.str.strip().str.replace(r"[$€£\s]", "", regex=True)
    pct = t.str.endswith("%")
    t = t.str.rstrip("%").str.replace(",", "", regex=False)
    out = pd.to_numeric(t.astype(object), errors="coerce").astype(float)
    return out.where(~pct, out / 100) if pct.any() and pct.mean() > 0.5 else out


def clean(df: pd.DataFrame, impute: bool = False) -> tuple[pd.DataFrame, CleaningLog]:
    log = CleaningLog()
    df = df.copy()
    # Column names
    new = []
    for c in df.columns:
        n = snake(c); k = 2
        while n in new:
            n = f"{snake(c)}_{k}"; k += 1
        new.append(n)
    if list(df.columns) != new:
        log.add(f"Renamed columns to snake_case: {', '.join(f'{a!r}→{b}' for a, b in zip(df.columns, new) if a != b)}")
    df.columns = new
    # Whitespace and missing markers
    df = df.apply(lambda s: s.astype("string").str.strip())
    missing_before = int(df.isna().sum().sum())
    df = df.apply(lambda s: s.mask(s.str.lower().isin(MISSING_TOKENS)))
    converted = int(df.isna().sum().sum()) - missing_before
    if converted:
        log.add(f"Treated {converted} placeholder values (blank, 'N/A', '-', '?', …) as missing")
    # Empty rows and columns
    empty_cols = [c for c in df.columns if df[c].isna().all()]
    if empty_cols:
        df = df.drop(columns=empty_cols); log.add(f"Dropped empty column(s): {', '.join(empty_cols)}")
    n = len(df); df = df.dropna(how="all")
    if len(df) < n:
        log.add(f"Dropped {n - len(df)} completely empty row(s)")
    # Duplicates
    n = len(df); df = df.drop_duplicates()
    if len(df) < n:
        log.add(f"Removed {n - len(df)} duplicate row(s)")
    # Type inference
    for c in df.columns:
        s = df[c].dropna()
        if s.empty:
            continue
        num = _to_number(df[c])
        if num.notna().sum() >= 0.9 * len(s):
            bad = int((df[c].notna() & num.isna()).sum())
            df[c] = num
            log.add(f"'{c}' → numeric" + (f" ({bad} unparseable value(s) set to missing)" if bad else ""))
            continue
        if s.str.contains(r"\d", regex=True).mean() > 0.9 and s.str.len().between(6, 30).mean() > 0.9:
            dt = pd.to_datetime(df[c], errors="coerce", format="mixed")
            if dt.notna().sum() >= 0.9 * len(s):
                df[c] = dt; log.add(f"'{c}' → date"); continue
        low = s.str.lower()
        if set(low.unique()) <= {"yes", "no", "true", "false", "y", "n", "1", "0"}:
            df[c] = df[c].str.lower().map({"yes": True, "y": True, "true": True, "1": True, "no": False, "n": False, "false": False, "0": False}).astype("boolean")
            log.add(f"'{c}' → yes/no"); continue
        # Normalize category spelling: "Grade 10", "grade 10 " → most common variant
        canon = s.groupby(low).agg(lambda x: x.value_counts().index[0])
        fixed = df[c].map(lambda v: canon.get(v.lower(), v) if isinstance(v, str) else v)
        changes = int((fixed.fillna("<NA>") != df[c].fillna("<NA>")).sum())
        if changes:
            df[c] = fixed; log.add(f"'{c}': unified {changes} inconsistent capitalization(s)")
        if df[c].nunique() <= max(12, len(df) // 20):
            df[c] = df[c].astype("category")
    if impute:
        for c in df.columns:
            k = int(df[c].isna().sum())
            if not k:
                continue
            if pd.api.types.is_numeric_dtype(df[c]):
                df[c] = df[c].fillna(df[c].median()); log.add(f"Filled {k} missing '{c}' value(s) with the median")
            elif isinstance(df[c].dtype, pd.CategoricalDtype):
                df[c] = df[c].fillna(df[c].mode().iloc[0]); log.add(f"Filled {k} missing '{c}' value(s) with the most common value")
    return df.reset_index(drop=True), log


def profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in df.columns:
        s = df[c]
        kind = "number" if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s) else "date" if pd.api.types.is_datetime64_any_dtype(s) else "yes/no" if pd.api.types.is_bool_dtype(s) else "category" if isinstance(s.dtype, pd.CategoricalDtype) else "text"
        rows.append({"column": c, "type": kind, "missing": int(s.isna().sum()), "missing_pct": round(100 * s.isna().mean(), 1), "unique": int(s.nunique()),
                     "example": str(s.dropna().iloc[0]) if s.notna().any() else ""})
    return pd.DataFrame(rows)


def numeric_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c]) and df[c].nunique() > 2]
