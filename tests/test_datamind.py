import numpy as np
import pandas as pd
import pytest

from datamind.__main__ import main
from datamind.analyze import correlations, find_patterns, outliers_iqr
from datamind.clean import clean, profile, snake
from datamind.samples import air_quality, study_habits


def test_snake_case_names():
    assert snake(" Final Score % ") == "final_score_pct"
    assert snake("PM2.5 (µg/m³)") == "pm2_5_ug_m3"


def test_cleaning_messy_values():
    raw = pd.DataFrame({"Name": ["a", "b", "b", "c", " d "], "Amount": ["$1,200", "300", "300", "N/A", "4.5"], "Joined": ["2026-01-02", "2026-02-03", "2026-02-03", "2026-03-04", "-"],
                        "Active": ["Yes", "no", "no", "YES", "No"], "Team": ["Red", "red", "red", "Blue", "BLUE"], "Empty": ["", "", "", "", ""]}).astype(str)
    df, log = clean(raw)
    assert len(df) == 4, "duplicate row removed"
    assert "empty" not in df.columns
    assert df["amount"].tolist()[:2] == [1200.0, 300.0] and df["amount"].isna().sum() == 1
    assert pd.api.types.is_datetime64_any_dtype(df["joined"])
    assert df["active"].tolist() == [True, False, True, False]
    assert set(df["team"].dropna()) == {"Red", "Blue"}, "case variants unified to the most common spelling"
    assert any("duplicate" in s for s in log.steps)
    prof = profile(df).set_index("column")
    assert prof.loc["amount", "type"] == "number" and prof.loc["joined", "type"] == "date"


def test_percent_columns_and_imputation():
    df, _ = clean(pd.DataFrame({"id": ["a", "b", "c", "d"], "rate": ["10%", "20%", "35%", "n/a"]}).astype(str), impute=True)
    assert df["rate"].tolist() == pytest.approx([0.10, 0.20, 0.35, 0.20])


def test_outliers_and_correlations():
    s = pd.Series([1, 2, 3, 2, 3, 2, 100])
    assert outliers_iqr(s).tolist()[-1] is True or bool(outliers_iqr(s).iloc[-1])
    rng = np.random.default_rng(0)
    x = rng.normal(size=200)
    df = pd.DataFrame({"x": x, "y": 2 * x + rng.normal(scale=0.3, size=200), "z": rng.normal(size=200)})
    c = correlations(df)
    assert (c[0]["a"], c[0]["b"]) == ("x", "y") and c[0]["r"] > 0.9


def test_patterns_on_known_synthetic_data():
    df, _ = clean(study_habits().astype(str))
    texts = " | ".join(i.text for i in find_patterns(df))
    assert "final_score_pct rises as weekly_study_hours" in texts
    assert "phone_hours_day has 1 extreme value" in texts, "the deliberate 95-hour entry is flagged"
    assert "grade_level" not in texts, "grade level has no real effect in this data, so nothing should be claimed"
    air, _ = clean(air_quality().astype(str))
    kinds = {i.kind for i in find_patterns(air)}
    assert {"trend", "group_difference", "outliers"} <= kinds


def test_random_noise_produces_no_findings():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"a": rng.normal(size=150), "b": rng.normal(size=150), "c": rng.normal(size=150), "g": rng.choice(["x", "y", "z"], 150)}).astype(str)
    df, _ = clean(df)
    assert [i for i in find_patterns(df) if i.kind in {"correlation", "group_difference", "trend"}] == []


def test_cli_end_to_end(tmp_path, capsys):
    assert main(["samples", "--out", str(tmp_path / "s")]) == 0
    assert main(["analyze", str(tmp_path / "s" / "study_habits.csv"), "--out", str(tmp_path / "r")]) == 0
    html = (tmp_path / "r" / "report.html").read_text()
    assert html.count("data:image/png;base64,") >= 3 and "Data cleaning log" in html
    assert (tmp_path / "r" / "charts" / "correlations.png").stat().st_size > 5000
    assert main(["clean", str(tmp_path / "s" / "air_quality.csv"), str(tmp_path / "clean.csv")]) == 0
    assert pd.read_csv(tmp_path / "clean.csv").shape == (120, 5)
