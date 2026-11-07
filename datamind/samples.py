"""Synthetic sample datasets with deliberately messy values (documented, reproducible)."""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd


def study_habits(n: int = 240, seed: int = 4) -> pd.DataFrame:
    """Fictional students: study time and sleep help scores, phone time hurts; plus real-world mess."""
    r = np.random.default_rng(seed)
    grade = r.choice(["Grade 9", "Grade 10", "Grade 11", "Grade 12"], n)
    study = np.clip(r.gamma(2.2, 1.6, n), 0, 14)
    sleep = np.clip(r.normal(7.2, 1.0, n), 4, 10)
    phone = np.clip(r.normal(3.5, 1.5, n) - 0.15 * study, 0.2, 10)
    club = r.choice(["Yes", "No"], n, p=[0.45, 0.55])
    score = 52 + 4.1 * study + 2.6 * (sleep - 7) - 2.2 * phone + (club == "Yes") * 2.5 + r.normal(0, 6, n)
    score = np.clip(score, 0, 100)
    df = pd.DataFrame({"Student ID": [f"S{1000 + i}" for i in range(n)], "Grade Level": grade, "Weekly Study Hours": study.round(1),
                       "Avg Sleep (hrs)": sleep.round(1), "Phone Hours/Day": phone.round(1), "Club Member": club, "Final Score %": score.round(1)})
    df = df.astype(object)
    # Mess: inconsistent case, placeholders, units, a few typos, duplicates, an obvious entry error.
    for i in r.choice(n, 12, replace=False): df.loc[i, "Grade Level"] = str(df.loc[i, "Grade Level"]).lower()
    for i in r.choice(n, 10, replace=False): df.loc[i, "Avg Sleep (hrs)"] = "N/A"
    for i in r.choice(n, 6, replace=False): df.loc[i, "Weekly Study Hours"] = "-"
    for i in r.choice(n, 25, replace=False): df.loc[i, "Final Score %"] = f"{df.loc[i, 'Final Score %']}%"
    df.loc[7, "Phone Hours/Day"] = 95.0  # data entry error (should be ~9.5)
    df = pd.concat([df, df.iloc[[3, 50, 51]]], ignore_index=True)
    df[" notes "] = ""
    return df


def air_quality(days: int = 120, seed: int = 9) -> pd.DataFrame:
    """Fictional city air sensor: PM2.5 falls over the season and rises with traffic and low wind."""
    r = np.random.default_rng(seed)
    date = pd.date_range("2026-06-01", periods=days, freq="D")
    wind = np.clip(r.normal(12, 4, days), 1, 30)
    traffic = 900 + 250 * (date.dayofweek < 5) + r.normal(0, 80, days)
    pm25 = 30 - 0.08 * np.arange(days) + 0.012 * (traffic - 900) - 0.6 * (wind - 12) + r.normal(0, 2.5, days)
    df = pd.DataFrame({"Date": date.strftime("%Y-%m-%d"), "PM2.5 (µg/m³)": pm25.round(1), "Wind km/h": wind.round(1), "Vehicles/hour": traffic.round(0).astype(int),
                       "Day Type": np.where(date.dayofweek < 5, "Weekday", "Weekend")})
    df.loc[40, "PM2.5 (µg/m³)"] = 260.0  # wildfire smoke day
    return df


def write_samples(folder: str | Path) -> None:
    f = Path(folder); f.mkdir(parents=True, exist_ok=True)
    study_habits().to_csv(f / "study_habits.csv", index=False)
    air_quality().to_csv(f / "air_quality.csv", index=False)
