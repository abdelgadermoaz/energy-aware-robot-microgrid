from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from .models import (
    MicrogridParams,
    RobotParams,
    Task,
    price_profile_tou,
    pv_profile_synthetic,
)
from .planner import baseline_plan, energy_aware_plan


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def simulate(
    outdir: Path,
    scenario: str = "demo",
    seed: int = 7,
) -> Dict:
    _ = np.random.default_rng(seed)  # reserved for future stochastic scenarios

    mg = MicrogridParams()
    rp = RobotParams()

    # ----------------------------
    # Scenario overrides
    # ----------------------------
    if scenario == "peak_mission":
        # Smaller microgrid so the grid is actually used
        mg.pv_rated_kw = 2.5
        mg.batt_capacity_kwh = 3.5
        mg.batt_pmax_kw = 1.2
        mg.soc_init = 0.25
        mg.soc_min = 0.10
        mg.soc_max = 0.95

        # Robot needs meaningful charging energy
        rp.batt_capacity_kwh = 3.0
        rp.soc_init = 0.20
        rp.soc_min = 0.15
        rp.charge_power_kw = 3.5
        rp.wh_per_meter = 2.2

    horizon_h = 24.0
    n = int(horizon_h / mg.dt_hours)
    t = np.arange(n) * mg.dt_hours

    pv_norm = pv_profile_synthetic(n, mg.dt_hours)
    pv_kw = pv_norm * mg.pv_rated_kw * mg.pv_eff

    price = price_profile_tou(n, mg.dt_hours)

    # ----------------------------
    # Mission definition
    # ----------------------------
    if scenario == "peak_mission":
        distance_scale = 2.0
        # Tasks released late to push charging decisions into expensive hours (16–21)
        tasks = [
            Task(
                "inspect_A",
                distance_m=1200 * distance_scale,
                release_h=14.5,
                deadline_h=16.5,
                duration_h=0.40,
            ),
            Task(
                "inspect_B",
                distance_m=1600 * distance_scale,
                release_h=16.1,
                deadline_h=18.6,
                duration_h=0.55,
            ),
            Task(
                "return_base",
                distance_m=900 * distance_scale,
                release_h=18.2,
                deadline_h=20.0,
                duration_h=0.25,
            ),
        ]
    else:
        tasks = [
            Task("inspect_A", distance_m=220, deadline_h=6.0, duration_h=0.25),
            Task("inspect_B", distance_m=480, deadline_h=10.0, duration_h=0.35),
            Task("thermal_scan_C", distance_m=650, deadline_h=14.0, duration_h=0.40),
            Task("return_base", distance_m=500, deadline_h=20.0, duration_h=0.20),
        ]

    # ----------------------------
    # Two planners
    # ----------------------------
    base_steps = baseline_plan(tasks, rp)
    ea_steps = energy_aware_plan(
        tasks,
        rp,
        price=price,
        pv_kw=pv_kw,
        dt_hours=mg.dt_hours,
    )

    # ----------------------------
    # Convert planner steps into robot charging load (kW) + robot SOC time series
    # ----------------------------
    def robot_load(steps) -> Tuple[np.ndarray, np.ndarray]:
        load_kw = np.zeros(n, dtype=float)
        soc_kwh = rp.soc_init * rp.batt_capacity_kwh
        soc_hist = np.zeros(n, dtype=float)

        for i in range(n):
            h0 = i * mg.dt_hours
            h1 = (i + 1) * mg.dt_hours

            e_kwh = 0.0
            for s in steps:
                overlap = max(0.0, min(h1, s.end_h) - max(h0, s.start_h))
                if overlap > 0:
                    frac = overlap / max(s.end_h - s.start_h, 1e-9)
                    e_kwh += s.energy_kwh * frac

            # positive e_kwh means charging -> microgrid load
            if e_kwh > 0:
                load_kw[i] += min(rp.charge_power_kw, e_kwh / mg.dt_hours)

            # update SOC: discharge for negative e_kwh, charge for positive e_kwh
            soc_kwh = np.clip(
                soc_kwh - (-min(e_kwh, 0.0)) + max(e_kwh, 0.0) * rp.charge_eff,
                0.0,
                rp.batt_capacity_kwh,
            )
            soc_hist[i] = soc_kwh / rp.batt_capacity_kwh

        return load_kw, soc_hist

    base_robot_kw, base_robot_soc = robot_load(base_steps)
    ea_robot_kw, ea_robot_soc = robot_load(ea_steps)

    # ----------------------------
    # Microgrid dispatch: PV serves load first, then battery, then grid.
    # ----------------------------
    def dispatch(robot_kw: np.ndarray) -> Tuple[pd.DataFrame, Dict]:
        soc_kwh = mg.soc_init * mg.batt_capacity_kwh
        records = []
        grid_kwh = 0.0
        cost = 0.0
        batt_throughput_kwh = 0.0

        for i in range(n):
            load_kw = robot_kw[i]
            pv = pv_kw[i]
            net = load_kw - pv  # + means deficit, - means surplus

            batt_kw = 0.0
            grid_kw = 0.0

            if net > 1e-9:
                max_dis_kw = min(
                    mg.batt_pmax_kw,
                    (soc_kwh - mg.soc_min * mg.batt_capacity_kwh) / mg.dt_hours,
                )
                batt_kw = min(net, max(0.0, max_dis_kw)) * mg.batt_eff
                grid_kw = max(0.0, net - batt_kw)
                soc_kwh -= (batt_kw / mg.batt_eff) * mg.dt_hours
            else:
                surplus_kw = -net
                max_ch_kw = min(
                    mg.batt_pmax_kw,
                    (mg.soc_max * mg.batt_capacity_kwh - soc_kwh) / mg.dt_hours,
                )
                batt_kw = -min(surplus_kw, max(0.0, max_ch_kw)) * mg.batt_eff
                soc_kwh += (-batt_kw / mg.batt_eff) * mg.dt_hours
                grid_kw = 0.0

            soc_kwh = float(
                np.clip(
                    soc_kwh,
                    mg.soc_min * mg.batt_capacity_kwh,
                    mg.soc_max * mg.batt_capacity_kwh,
                )
            )

            grid_kwh_i = grid_kw * mg.dt_hours
            grid_kwh += grid_kwh_i
            cost += grid_kwh_i * price[i]
            batt_throughput_kwh += abs(batt_kw) * mg.dt_hours

            records.append(
                {
                    "t_h": t[i],
                    "pv_kw": pv,
                    "robot_kw": load_kw,
                    "batt_kw": batt_kw,
                    "grid_kw": grid_kw,
                    "price_per_kwh": price[i],
                    "soc_microgrid": soc_kwh / mg.batt_capacity_kwh,
                }
            )

        df = pd.DataFrame.from_records(records)
        summary = {
            "grid_kwh": grid_kwh,
            "cost_usd": cost,
            "batt_throughput_kwh": batt_throughput_kwh,
        }
        return df, summary

    base_df, base_sum = dispatch(base_robot_kw)
    ea_df, ea_sum = dispatch(ea_robot_kw)

    base_df["robot_soc"] = base_robot_soc
    ea_df["robot_soc"] = ea_robot_soc

    # ----------------------------
    # Save
    # ----------------------------
    _ensure_dir(outdir)
    base_df.to_csv(outdir / "timeseries_baseline.csv", index=False)
    ea_df.to_csv(outdir / "timeseries_energy_aware.csv", index=False)

    summary = {
        "scenario": scenario,
        "microgrid_params": asdict(mg),
        "robot_params": asdict(rp),
        "baseline": base_sum,
        "energy_aware": ea_sum,
        "delta_cost_usd": base_sum["cost_usd"] - ea_sum["cost_usd"],
        "delta_grid_kwh": base_sum["grid_kwh"] - ea_sum["grid_kwh"],
    }
    (outdir / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    return summary
