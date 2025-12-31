from pathlib import Path

from earp.sim import simulate


def test_simulate_creates_files(tmp_path: Path):
    summary = simulate(tmp_path / "run1", scenario="demo", seed=1)
    assert (tmp_path / "run1" / "timeseries_baseline.csv").exists()
    assert (tmp_path / "run1" / "timeseries_energy_aware.csv").exists()
    assert (tmp_path / "run1" / "summary.json").exists()
    assert "delta_cost_usd" in summary
