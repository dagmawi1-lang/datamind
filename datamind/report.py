"""Automated analytical report (self-contained HTML with embedded charts, plus Markdown)."""
from __future__ import annotations
import base64
import html
from datetime import datetime
from pathlib import Path

import pandas as pd

from .analyze import describe, find_patterns
from .clean import CleaningLog, profile
from .viz import make_charts


def build(df: pd.DataFrame, log: CleaningLog, title: str, out_dir: str | Path) -> dict:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    insights = find_patterns(df)
    charts = make_charts(df, out / "charts")
    prof, desc = profile(df), describe(df)
    e = html.escape
    imgs = "".join(f"<figure><img alt='{e(cap)}' src='data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}'><figcaption>{e(cap)}</figcaption></figure>" for cap, p in charts)
    icon = {"correlation": "🔗", "group_difference": "📊", "trend": "📈", "outliers": "⚠️", "skew": "↗️", "missing": "❓"}
    ins_html = "".join(f"<li><b>{icon.get(i.kind, '•')} {e(i.text)}</b><br><small>{e(i.evidence)}{(' · ' + e(i.caveat)) if i.caveat else ''}</small></li>" for i in insights[:12])
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>{e(title)}</title>
<style>body{{font-family:system-ui,-apple-system,sans-serif;color:#1f2937;max-width:1050px;margin:auto;padding:28px;line-height:1.5}}h1{{margin-bottom:0}}.muted{{color:#6b7280}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}}.card{{border:1px solid #e5e7eb;border-radius:12px;padding:12px}}.card b{{font-size:22px;display:block}}
li{{margin-bottom:10px}}small{{color:#6b7280}}table{{border-collapse:collapse;font-size:13px;width:100%;margin:8px 0 20px}}td,th{{border-bottom:1px solid #e5e7eb;padding:6px 8px;text-align:left}}
figure{{margin:16px 0}}img{{max-width:100%;border:1px solid #e5e7eb;border-radius:10px}}figcaption{{color:#6b7280;font-size:12px}}</style></head><body>
<h1>📊 {e(title)}</h1><p class=muted>DataMind report · generated {datetime.now():%Y-%m-%d %H:%M}</p>
<div class=cards><div class=card><b>{len(df):,}</b>rows</div><div class=card><b>{df.shape[1]}</b>columns</div><div class=card><b>{len(insights)}</b>findings</div><div class=card><b>{len(log.steps)}</b>cleaning steps</div></div>
<h2>Key findings</h2><ol>{ins_html or '<li>No statistically clear patterns were found.</li>'}</ol>
<h2>Charts</h2>{imgs}
<h2>Data cleaning log</h2><ul>{''.join(f'<li>{e(s)}</li>' for s in log.steps) or '<li>No changes needed.</li>'}</ul>
<h2>Column profile</h2>{prof.to_html(index=False, border=0)}
<h2>Summary statistics</h2>{desc.to_html(border=0) if not desc.empty else '<p>No numeric columns.</p>'}
<p class=muted>Findings use a significance level of 0.01 to reduce false discoveries when testing many pairs. Statistical association does not prove cause.</p></body></html>"""
    (out / "report.html").write_text(page)
    md = [f"# {title}", f"_DataMind report · {datetime.now():%Y-%m-%d}_", "", f"{len(df):,} rows × {df.shape[1]} columns", "", "## Key findings"]
    md += [f"{n}. **{i.text}** — {i.evidence}" + (f" _({i.caveat})_" if i.caveat else "") for n, i in enumerate(insights[:12], 1)] or ["No clear patterns."]
    md += ["", "## Cleaning log", *[f"- {s}" for s in log.steps], "", "## Charts", *[f"![{c}](charts/{p.name})" for c, p in charts]]
    (out / "report.md").write_text("\n".join(md))
    return {"insights": insights, "charts": charts, "html": out / "report.html", "md": out / "report.md"}
