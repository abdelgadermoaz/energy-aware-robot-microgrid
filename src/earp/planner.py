from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from .models import RobotParams, Task


@dataclass
class PlanStep:
    kind: str  # "task" | "charge" | "idle"
    name: str
    start_h: float
    end_h: float
    energy_kwh: float  # robot energy used (-) or charged (+)


def _robot_energy_for_task(task: Task, rp: RobotParams) -> float:
    # travel energy + a tiny fixed overhead
    return (task.distance_m * rp.wh_per_meter) / 1000.0 + 0.02


def baseline_plan(tasks: List[Task], rp: RobotParams) -> List[PlanStep]:
    """
    Naive planner:
    - Wait until task release time.
    - Do tasks in given order.
    - Charge only when SOC is too low.
    """
    soc_kwh = rp.soc_init * rp.batt_capacity_kwh
    t = 0.0
    steps: List[PlanStep] = []

    for task in tasks:
        # wait for release time
        if hasattr(task, "release_h") and t < task.release_h:
            steps.append(PlanStep("idle", "wait", t, task.release_h, 0.0))
            t = task.release_h

        need = _robot_energy_for_task(task, rp)

        # charge if needed (to reach 80% SOC)
        if soc_kwh - need < rp.soc_min * rp.batt_capacity_kwh:
            target_kwh = 0.80 * rp.batt_capacity_kwh
            add_kwh = max(target_kwh - soc_kwh, 0.0)
            dt = add_kwh / max(rp.charge_power_kw * rp.charge_eff, 1e-9)
            steps.append(PlanStep("charge", "dock", t, t + dt, +add_kwh))
            soc_kwh = min(soc_kwh + add_kwh * rp.charge_eff, rp.batt_capacity_kwh)
            t += dt

        # execute task
        steps.append(PlanStep("task", task.name, t, t + task.duration_h, -need))
        soc_kwh = max(soc_kwh - need, 0.0)
        t += task.duration_h

    return steps


def energy_aware_plan(
    tasks: List[Task],
    rp: RobotParams,
    price: np.ndarray,
    pv_kw: np.ndarray,
    dt_hours: float,
) -> List[PlanStep]:
    """
    Energy-aware heuristic:
    - Prefers charging when price is low AND PV is high.
    - Uses idle time before task release to pre-charge opportunistically.
    - Guarantees enough energy to complete tasks with a buffer.
    """
    soc_kwh = rp.soc_init * rp.batt_capacity_kwh
    t = 0.0
    steps: List[PlanStep] = []
    n = len(price)

    pv_norm = pv_kw / (pv_kw.max() + 1e-9)
    p_min, p_max = float(np.min(price)), float(np.max(price))
    p_span = max(p_max - p_min, 1e-9)

    alpha_pv = 0.7  # higher => more “charge when PV is strong”

    def idx(h: float) -> int:
        return int(np.clip(np.floor(h / dt_hours + 1e-9), 0, n - 1))

    def score(i: int) -> float:
        # lower is better
        return float(price[i] - alpha_pv * p_span * pv_norm[i])

    def schedule_charge(best_t: float, add_kwh: float) -> None:
        nonlocal t, soc_kwh

        if best_t > t:
            steps.append(PlanStep("idle", "wait", t, best_t, 0.0))
            t = best_t

        add_kwh = max(0.0, min(add_kwh, rp.batt_capacity_kwh - soc_kwh))
        if add_kwh <= 1e-9:
            return

        dt = add_kwh / max(rp.charge_power_kw * rp.charge_eff, 1e-9)
        steps.append(PlanStep("charge", "dock", t, t + dt, +add_kwh))
        soc_kwh = min(soc_kwh + add_kwh * rp.charge_eff, rp.batt_capacity_kwh)
        t += dt

    for task in tasks:
        release_h = getattr(task, "release_h", 0.0)

        # --- opportunistic pre-charge before release ---
        if t < release_h:
            gap = release_h - t
            target_kwh = 0.85 * rp.batt_capacity_kwh

            if soc_kwh < target_kwh:
                i0 = idx(t)
                i1 = idx(release_h)
                candidates = list(range(i0, max(i0, i1)))
                if candidates:
                    best_i = min(candidates, key=score)
                    best_t = best_i * dt_hours

                    max_add = rp.charge_power_kw * rp.charge_eff * gap
                    add = min(target_kwh - soc_kwh, max_add)
                    schedule_charge(best_t, add)

            if t < release_h:
                steps.append(PlanStep("idle", "wait", t, release_h, 0.0))
                t = release_h

        # --- ensure enough energy for the task ---
        need_kwh = _robot_energy_for_task(task, rp)
        buffer_kwh = 0.15 * rp.batt_capacity_kwh
        required_kwh = max(need_kwh + buffer_kwh, rp.soc_min * rp.batt_capacity_kwh)

        if soc_kwh < required_kwh:
            latest_start = max(task.deadline_h - task.duration_h, t)
            i0 = idx(t)
            i1 = idx(latest_start)

            if i1 < i0:
                best_i = i0
            else:
                best_i = min(range(i0, i1 + 1), key=score)

            best_t = best_i * dt_hours
            schedule_charge(best_t, required_kwh - soc_kwh)

        # --- execute task ---
        steps.append(PlanStep("task", task.name, t, t + task.duration_h, -need_kwh))
        soc_kwh = max(soc_kwh - need_kwh, 0.0)
        t += task.duration_h

    return steps
