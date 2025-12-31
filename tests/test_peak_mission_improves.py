import json
from pathlib import Path

from earp.sim import simulate


def test_peak_mission_energy_aware_beats_baseline(tmp_path: Path):
    simulate(tmp_path / "run", scenario="peak_mission", seed=1)
    summary = json.loads((tmp_path / "run" / "summary.json").read_text(encoding="utf-8"))
    assert summary["delta_cost_usd"] > 0
    assert summary["delta_grid_kwh"] > 0
