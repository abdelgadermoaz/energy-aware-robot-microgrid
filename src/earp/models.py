from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class MicrogridParams:
    dt_hours: float = 0.25  # 15 min
    pv_rated_kw: float = 30.0
    pv_eff: float = 0.95  # simple derate
    batt_capacity_kwh: float = 60.0
    batt_pmax_kw: float = 25.0
    batt_eff: float = 0.95
    soc_init: float = 0.5  # 0..1
    soc_min: float = 0.1
    soc_max: float = 0.95


@dataclass
class RobotParams:
    batt_capacity_kwh: float = 2.0
    soc_init: float = 0.8
    soc_min: float = 0.15
    charge_power_kw: float = 0.6
    charge_eff: float = 0.9
    wh_per_meter: float = 0.5  # simple energy model (tune later)


@dataclass
class Task:
    name: str
    distance_m: float
    deadline_h: float  # mission time in hours from start
    duration_h: float = 0.1  # time spent doing the task on site
    release_h: float = 0.0  # earliest start time in hours from start

def pv_profile_synthetic(
    n: int,
    dt_hours: float,
    sunrise_h: float = 7.0,
    sunset_h: float = 18.5,
) -> np.ndarray:
    """Return normalized PV profile in [0,1] with a smooth bell shape.
    This is a *placeholder* until you plug in real irradiance.
    """
    t = np.arange(n) * dt_hours
    prof = np.zeros(n, dtype=float)
    day = (t >= sunrise_h) & (t <= sunset_h)
    # map [sunrise, sunset] -> [0, pi]
    x = (t[day] - sunrise_h) / max(sunset_h - sunrise_h, 1e-6) * np.pi
    prof[day] = np.sin(x) ** 1.5
    return prof


def price_profile_tou(n: int, dt_hours: float) -> np.ndarray:
    """Simple time-of-use price ($/kWh) profile."""
    t = np.arange(n) * dt_hours
    p = np.full(n, 0.14, dtype=float)  # off-peak
    peak = (t >= 16) & (t < 21)
    p[peak] = 0.30
    mid = (t >= 7) & (t < 16)
    p[mid] = 0.20
    return p
