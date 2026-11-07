import argparse
import sys
from pathlib import Path

from .clean import clean, load, profile
from .report import build
from .samples import write_samples


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="datamind", description="Import, clean, analyze, and report on a CSV/Excel/JSON dataset")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="full pipeline → report.html"); a.add_argument("file"); a.add_argument("--out", default="datamind_report"); a.add_argument("--title"); a.add_argument("--impute", action="store_true", help="fill missing values (median/mode)")
    pr = sub.add_parser("profile", help="column types and missing values"); pr.add_argument("file")
    c = sub.add_parser("clean", help="write a cleaned CSV and print the log"); c.add_argument("file"); c.add_argument("out")
    s = sub.add_parser("samples", help="write the sample datasets"); s.add_argument("--out", default="samples")
    args = p.parse_args(argv)
    if args.cmd == "samples":
        write_samples(args.out); print(f"Wrote sample datasets to {args.out}/"); return 0
    df, log = clean(load(args.file), impute=getattr(args, "impute", False))
    if args.cmd == "profile":
        print(profile(df).to_string(index=False)); return 0
    if args.cmd == "clean":
        df.to_csv(args.out, index=False); print("\n".join(f"- {s}" for s in log.steps)); print(f"Clean data: {args.out} ({len(df)} rows)"); return 0
    res = build(df, log, args.title or Path(args.file).stem.replace("_", " ").title(), args.out)
    print(f"Cleaning: {len(log.steps)} steps")
    for s in log.steps: print(f"  - {s}")
    print(f"\nTop findings:")
    for i in res["insights"][:8]: print(f"  • {i.text}\n      {i.evidence}")
    print(f"\nReport: {res['html']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
