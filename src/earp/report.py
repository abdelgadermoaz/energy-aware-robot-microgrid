from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def make_report(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    base = pd.read_csv(run_dir / "timeseries_baseline.csv")
    ea = pd.read_csv(run_dir / "timeseries_energy_aware.csv")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    # --- Plot 1: SOC comparison ---
    fig = plt.figure()
    plt.plot(base["t_h"], base["soc_microgrid"], label="SOC baseline")
    plt.plot(ea["t_h"], ea["soc_microgrid"], label="SOC energy-aware")
    plt.xlabel("Time (h)")
    plt.ylabel("Microgrid SOC (0..1)")
    plt.legend()
    plt.title("Microgrid SOC: baseline vs energy-aware")
    fig_path = run_dir / "fig_soc.png"
    fig.savefig(fig_path, dpi=180, bbox_inches="tight")
    plt.close(fig)

    # --- Plot 2: Grid import comparison ---
    fig2 = plt.figure()
    plt.plot(base["t_h"], base["grid_kw"], label="Grid kW baseline")
    plt.plot(ea["t_h"], ea["grid_kw"], label="Grid kW energy-aware")
    plt.xlabel("Time (h)")
    plt.ylabel("Grid power (kW)")
    plt.legend()
    plt.title("Grid import power: baseline vs energy-aware")
    fig2_path = run_dir / "fig_grid_kw.png"
    fig2.savefig(fig2_path, dpi=180, bbox_inches="tight")
    plt.close(fig2)

    # --- Plot 3: Price + robot charging power ---
    fig3 = plt.figure()
    plt.plot(base["t_h"], base["price_per_kwh"], label="Price ($/kWh)")
    plt.plot(base["t_h"], base["robot_kw"], label="Robot charge kW (baseline)")
    plt.plot(ea["t_h"], ea["robot_kw"], label="Robot charge kW (energy-aware)")
    plt.xlabel("Time (h)")
    plt.ylabel("Value")
    plt.legend()
    plt.title("Price and Robot Charging: baseline vs energy-aware")
    fig3_path = run_dir / "fig_price_robot_kw.png"
    fig3.savefig(fig3_path, dpi=180, bbox_inches="tight")
    plt.close(fig3)

    # --- Plot 4: Cumulative cost ---
    dt_base = base["t_h"].diff().fillna(base["t_h"].iloc[1] - base["t_h"].iloc[0])
    dt_ea = ea["t_h"].diff().fillna(ea["t_h"].iloc[1] - ea["t_h"].iloc[0])

    base_cost = (base["grid_kw"] * dt_base * base["price_per_kwh"]).cumsum()
    ea_cost = (ea["grid_kw"] * dt_ea * ea["price_per_kwh"]).cumsum()

    fig4 = plt.figure()
    plt.plot(base["t_h"], base_cost, label="Cumulative cost baseline")
    plt.plot(ea["t_h"], ea_cost, label="Cumulative cost energy-aware")
    plt.xlabel("Time (h)")
    plt.ylabel("Cumulative cost ($)")
    plt.legend()
    plt.title("Cumulative grid cost over time")
    fig4_path = run_dir / "fig_cumulative_cost.png"
    fig4.savefig(fig4_path, dpi=180, bbox_inches="tight")
    plt.close(fig4)

    # --- Markdown report ---
    md = f"""# Run report

## Key results
**Cost baseline:** ${summary["baseline"]["cost_usd"]:.2f}  
**Cost energy-aware:** ${summary["energy_aware"]["cost_usd"]:.2f}  
**Cost saved:** ${summary["delta_cost_usd"]:.2f}  

**Grid kWh baseline:** {summary["baseline"]["grid_kwh"]:.2f}  
**Grid kWh energy-aware:** {summary["energy_aware"]["grid_kwh"]:.2f}  
**Grid kWh saved:** {summary["delta_grid_kwh"]:.2f}  

## Figures
- `{fig_path.name}`
- `{fig2_path.name}`
- `{fig3_path.name}`
- `{fig4_path.name}`
"""
    (run_dir / "REPORT.md").write_text(md, encoding="utf-8")
    return run_dir / "REPORT.md"
