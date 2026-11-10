import numpy as np
import pandas as pd
import pytest

from src.angles import ang_diff, bearing
from src.data import normalize_direction, play_windows, prepare_game
from src.metric import break_bucket, compute_play, detect_break, pair_defender, turn_lag


# ---------- angles ----------
def test_angle_wraps():
    assert ang_diff(359, 1) == pytest.approx(2)
    assert ang_diff(10, 190) == pytest.approx(180)


def test_bearing_convention():
    assert bearing(0, 0, 0, 1) == pytest.approx(0)    # +y
    assert bearing(0, 0, 1, 0) == pytest.approx(90)   # +x
    assert bearing(0, 0, -1, 0) == pytest.approx(270)


# ---------- normalization ----------
def test_left_play_rotates_180():
    df = pd.DataFrame({"playDirection": ["left"], "x": [30.0], "y": [10.0], "o": [270.0], "dir": [270.0]})
    out = normalize_direction(df)
    assert out.loc[0, "x"] == pytest.approx(90.0)
    assert out.loc[0, "y"] == pytest.approx(43.3)
    assert out.loc[0, "dir"] == pytest.approx(90.0)  # moving toward +x after normalization


def test_play_without_throw_is_dropped():
    df = pd.DataFrame({"playId": [1, 1, 2, 2], "frameId": [1, 5, 1, 5],
                       "event": ["ball_snap", "pass_forward", "ball_snap", "qb_sack"]})
    win = play_windows(df).set_index("playId")
    assert win.loc[1, "throw_frame"] == 5
    assert np.isnan(win.loc[2, "throw_frame"])


# ---------- break, bucket, lag, pairing ----------
def test_synthetic_cut_detected_and_straight_route_not():
    dirs = np.r_[np.full(15, 90.0), np.full(10, 0.0)]   # 90 degree cut at frame 15
    speed = np.full(25, 6.0)
    idx, change = detect_break(dirs, speed)
    assert change == pytest.approx(90)
    assert 15 <= idx <= 19
    assert detect_break(np.full(25, 90.0), speed) is None


def test_slow_noise_is_not_a_break():
    dirs = np.r_[np.full(10, 90.0), np.full(10, 200.0)]
    assert detect_break(dirs, np.full(20, 0.5)) is None


def test_buckets():
    assert break_bucket(45, 0) == "slight"
    assert break_bucket(90, 80) == "diagonal downfield"
    assert break_bucket(90, 0) == "sideways"
    assert break_bucket(150, 270) == "back toward line"


def test_turn_lag_instant_and_censored():
    assert turn_lag([20, 10, 5]) == (0.0, False)
    lag, cens = turn_lag([120, 90, 50, 30])
    assert lag == pytest.approx(0.3) and not cens
    lag, cens = turn_lag([170, 160, 150, 140, 130])
    assert lag == pytest.approx(0.4) and cens


def test_pairing_picks_closest():
    rec = np.tile([[20.0, 20.0]], (10, 1))
    defs = {1: np.tile([[25.0, 20.0]], (10, 1)), 2: np.tile([[21.0, 21.0]], (10, 1))}
    assert pair_defender(rec, defs) == 2


# ---------- real data: play 97 ----------
@pytest.fixture(scope="module")
def play97():
    df = prepare_game(2021090900)
    return df[df["playId"] == 97]


def test_play97_window(play97):
    assert play97["frameId"].min() == 6
    assert play97["frameId"].max() == 40
    assert play97["pff_passCoverageType"].iloc[0] == "Man"


def test_play97_routes(play97):
    routes = compute_play(play97, keep_series=True)
    godwin = next(r for r in routes if r["name"] == "Chris Godwin")
    assert godwin["is_target"]
    gap = godwin["series"]["gap"][godwin["series"]["b_idx"]:]
    assert godwin["mean_gap"] == pytest.approx(float(np.mean(gap)))
    assert 0 <= godwin["mean_gap"] <= 180
    for r in routes:
        assert r["snap_frame"] < r["break_frame"] < r["throw_frame"]
