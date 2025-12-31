import numpy as np

from earp.models import price_profile_tou, pv_profile_synthetic


def test_pv_profile_bounds():
    n = 96
    prof = pv_profile_synthetic(n, 0.25)
    assert np.all(prof >= 0.0)
    assert np.all(prof <= 1.0)
    assert prof.sum() > 0.0


def test_price_profile_positive():
    n = 96
    p = price_profile_tou(n, 0.25)
    assert np.all(p > 0.0)
