from __future__ import annotations

import argparse
import datetime
from pathlib import Path

from .report import make_report
from .sim import simulate


def _latest_output_dir(outputs_root: Path) -> Path:
    dirs = [p for p in outputs_root.glob("*") if p.is_dir()]
    if not dirs:
        raise SystemExit("No outputs found. Run: earp simulate")
    return sorted(dirs)[-1]


def main() -> None:
    parser = argparse.ArgumentParser(
    prog="earp",
    description="Energy-aware Robot + Microgrid Planner",
)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sim = sub.add_parser("simulate", help="Run a simulation scenario")
    p_sim.add_argument("--scenario", default="demo")
    p_sim.add_argument(
    "--out",
    default="outputs/latest",
    help="Output directory (or 'outputs/latest')",
)
    p_sim.add_argument("--seed", type=int, default=7)

    p_rep = sub.add_parser(
    "report",
    help="Generate plots and a short markdown report for a run directory",
)
    p_rep.add_argument("--run", default="outputs/latest", help="Run directory or 'outputs/latest'")

    args = parser.parse_args()

    if args.cmd == "simulate":
        out = Path(args.out)
        if str(out).endswith("latest"):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out = Path("outputs") / ts
            # update outputs/latest pointer-like folder with a text file
            Path("outputs").mkdir(exist_ok=True)
            Path("outputs/latest").write_text(str(out), encoding="utf-8")
        summary = simulate(out, scenario=args.scenario, seed=args.seed)
        print(f"Saved run to: {out}")
        print(f"Cost saved (USD): {summary['delta_cost_usd']:.2f}")
        print(f"Grid kWh saved: {summary['delta_grid_kwh']:.2f}")

    elif args.cmd == "report":
        run = Path(args.run)
        if str(run).endswith("latest"):
            # resolve latest run directory stored in outputs/latest text
            latest_ptr = Path("outputs/latest")
            if latest_ptr.is_file():
                run = Path(latest_ptr.read_text(encoding="utf-8").strip())
            else:
                run = _latest_output_dir(Path("outputs"))
        md = make_report(run)
        print(f"Wrote: {md}")
