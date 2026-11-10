"""Turn Lag engine: pairing, break detection, bucket, gap series and route metrics."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .angles import ang_diff
from .data import SKILL_POSITIONS

FPS = 10.0
BREAK_LOOKBACK = 5          # frames = 0.5 s
BREAK_MIN_CHANGE = 30.0     # degrees
BREAK_MIN_SPEED = 2.0       # yd/s, peak speed across the lookback span
GAP_THRESHOLD = 45.0        # degrees: defender has "turned" once below this
PAIR_FRAMES = 10            # frames after the snap used to pair a defender
MAX_PAIR_DIST = 5.0         # yards: paired defender must still be this close at the break

# Only defensive backs and linebackers can be paired. PFF tags a dropping edge rusher
# as "Coverage" too, but a lineman in coverage is spying or sinking into a short zone,
# not covering a receiver man to man.
DB_POSITIONS = {"CB", "FS", "SS", "S", "DB"}
LB_POSITIONS = {"ILB", "OLB", "MLB", "LB"}


def defender_group(position) -> str | None:
    if position in DB_POSITIONS:
        return "DB"
    if position in LB_POSITIONS:
        return "LB"
    return None


def detect_break(dir_s, speed, lookback=BREAK_LOOKBACK, min_change=BREAK_MIN_CHANGE,
                 min_speed=BREAK_MIN_SPEED):
    """Find the receiver's sharpest direction change over `lookback` frames.

    Returns (break_index, change_deg) where break_index is the end of the
    turning span (the frame the new direction is established), or None if no
    change of at least `min_change` happens. The speed gate requires the
    receiver to reach `min_speed` somewhere in the span: receivers slow down
    to cut, so a mean-speed gate rejected most curls and comebacks, while
    this still rejects direction noise from players standing nearly still.
    The break must leave at least one frame before the throw.
    """
    dir_s = np.asarray(dir_s, dtype=float)
    speed = np.asarray(speed, dtype=float)
    n = len(dir_s)
    best_i, best_change = None, -1.0
    for i in range(lookback, n - 1):
        if np.nanmax(speed[i - lookback:i + 1]) <= min_speed:
            continue
        change = float(ang_diff(dir_s[i], dir_s[i - lookback]))
        if change > best_change:
            best_i, best_change = i, change
    if best_i is None or best_change < min_change:
        return None
    return best_i, best_change


def break_bucket(change: float, new_dir: float) -> str:
    """Route-shape bucket from the break angle and the new direction.

    After normalization the offense moves toward +x, which is 90 degrees.
    """
    if change < 60.0:
        return "slight"
    off_downfield = float(ang_diff(new_dir, 90.0))
    if off_downfield <= 60.0:
        return "diagonal downfield"
    if off_downfield <= 120.0:
        return "sideways"
    return "back toward line"


def turn_lag(gap, threshold=GAP_THRESHOLD, fps=FPS):
    """Seconds from the break (index 0) until gap < threshold.

    If the defender never gets below the threshold before the throw the lag is
    capped at the throw and flagged as censored.
    """
    gap = np.asarray(gap, dtype=float)
    below = np.flatnonzero(gap < threshold)
    if len(below):
        return below[0] / fps, False
    return (len(gap) - 1) / fps, True


def pair_defender(rec_xy: np.ndarray, defenders: dict[int, np.ndarray], n_frames=PAIR_FRAMES):
    """Closest coverage defender by mean distance over the first n frames."""
    best, best_d = None, np.inf
    for nfl_id, xy in defenders.items():
        k = min(n_frames, len(xy), len(rec_xy))
        d = np.nanmean(np.hypot(rec_xy[:k, 0] - xy[:k, 0], rec_xy[:k, 1] - xy[:k, 1]))
        if d < best_d:
            best, best_d = nfl_id, d
    return best


_TARGET_RE = re.compile(r"\b(?:to|intended for)\s+([A-Z][A-Za-z]*)\.\s?([A-Z][A-Za-z'\-]+)")


def parse_target(description: str, candidates: pd.DataFrame):
    """Match the 'to X.Lastname' receiver in the play text to an nflId."""
    if not isinstance(description, str):
        return None
    m = _TARGET_RE.search(description)
    if not m:
        return None
    initial, last = m.group(1)[0].upper(), m.group(2).lower()
    for row in candidates.itertuples():
        name = str(row.displayName)
        parts = name.split()
        if len(parts) >= 2 and parts[0][0].upper() == initial and parts[-1].lower().startswith(last):
            return int(row.nflId)
    return None


def _player_arrays(play: pd.DataFrame, frames: np.ndarray) -> dict[int, pd.DataFrame]:
    out = {}
    for nfl_id, g in play[play["nflId"].notna()].groupby("nflId"):
        out[int(nfl_id)] = g.set_index("frameId").reindex(frames)
    return out


def compute_play(play: pd.DataFrame, log: dict | None = None, keep_series: bool = False) -> list[dict]:
    """Compute Turn Lag route metrics for every skill-position route on one play.

    `play` is the snap-to-throw slice produced by data.prepare_game.
    """
    log = log if log is not None else {}
    snap = int(play["snap_frame"].iloc[0])
    throw = int(play["throw_frame"].iloc[0])
    frames = np.arange(snap, throw + 1)
    players = _player_arrays(play, frames)
    first = play[play["frameId"] == snap]
    meta = first.set_index("nflId")

    routes = first[(first["pff_role"] == "Pass Route") & first["officialPosition"].isin(SKILL_POSITIONS)]
    cov = first[first["pff_role"] == "Coverage"]
    pairable = cov["officialPosition"].map(defender_group).notna()
    if (~pairable).any():
        log["coverage_players_not_pairable"] = log.get("coverage_players_not_pairable", 0) + int((~pairable).sum())
    coverage_ids = [int(i) for i in cov.loc[pairable, "nflId"]]
    if routes.empty or not coverage_ids:
        log["plays_no_routes_or_coverage"] = log.get("plays_no_routes_or_coverage", 0) + 1
        return []
    def_xy = {d: players[d][["x", "y"]].to_numpy() for d in coverage_ids if d in players}
    target_id = parse_target(first["playDescription"].iloc[0], routes)
    info = first.iloc[0]

    results = []
    for rec_id in routes["nflId"].astype(int):
        log["routes_total"] = log.get("routes_total", 0) + 1
        rec = players[rec_id]
        if rec[["x", "y", "dir_s", "s"]].isna().any().any():
            log["routes_missing_frames"] = log.get("routes_missing_frames", 0) + 1
            continue
        brk = detect_break(rec["dir_s"].to_numpy(), rec["s"].to_numpy())
        if brk is None:
            log["routes_no_break"] = log.get("routes_no_break", 0) + 1
            continue
        b_idx, change = brk
        def_id = pair_defender(rec[["x", "y"]].to_numpy(), def_xy)
        dfn = players[def_id]
        if dfn[["x", "y", "o_s"]].isna().any().any():
            log["routes_missing_frames"] = log.get("routes_missing_frames", 0) + 1
            continue

        rec_dir = rec["dir_s"].to_numpy()
        def_o = dfn["o_s"].to_numpy()
        gap_full = ang_diff(def_o, rec_dir)
        gap = gap_full[b_idx:]
        lag, censored = turn_lag(gap)
        dist = np.hypot(rec["x"].to_numpy() - dfn["x"].to_numpy(), rec["y"].to_numpy() - dfn["y"].to_numpy())
        if dist[b_idx] > MAX_PAIR_DIST:
            # The early-snap pairing no longer holds: this defender is not on him at the
            # break, so his facing says nothing about the route.
            log["routes_defender_not_close"] = log.get("routes_defender_not_close", 0) + 1
            continue
        new_dir = float(rec_dir[b_idx])

        row = {
            "gameId": int(info["gameId"]), "playId": int(info["playId"]),
            "nflId": rec_id, "name": meta.loc[rec_id, "displayName"],
            "position": meta.loc[rec_id, "officialPosition"], "team": meta.loc[rec_id, "team"],
            "def_id": def_id, "def_name": meta.loc[def_id, "displayName"],
            "def_position": meta.loc[def_id, "officialPosition"],
            "def_group": defender_group(meta.loc[def_id, "officialPosition"]),
            "coverage": info["pff_passCoverage"], "coverage_type": info["pff_passCoverageType"],
            "passResult": info["passResult"], "is_target": rec_id == target_id,
            "snap_frame": snap, "throw_frame": throw, "break_frame": int(frames[b_idx]),
            "break_change": change, "new_dir": new_dir, "bucket": break_bucket(change, new_dir),
            "gap_at_break": float(gap[0]), "turn_lag": lag, "censored": censored,
            "mean_gap": float(np.mean(gap)),
            "sep_break": float(dist[b_idx]), "sep_throw": float(dist[-1]),
            "sep_gained": float(dist[-1] - dist[b_idx]),
            "def_ahead": bool(dfn["x"].to_numpy()[-1] > rec["x"].to_numpy()[-1]),
        }
        if keep_series:
            row["series"] = {"frames": frames, "gap": gap_full, "dist": dist, "b_idx": b_idx}
        results.append(row)
        log["routes_scored"] = log.get("routes_scored", 0) + 1
    return results


def add_over_expected(routes: pd.DataFrame) -> pd.DataFrame:
    """Subtract the (coverage type, receiver position, defender group, bucket) average
    from Turn Lag and Mean Gap.

    Receiver position is in the baseline because a back releasing from the
    backfield is usually paired with a linebacker who keeps facing the
    quarterback; with a bucket-only baseline RBs filled the leaderboard.
    Defender group (DB vs LB) is in the baseline because even on man-coverage
    plays some linebackers drop into zones and face the quarterback, so an LB
    pairing looks "turned" without the receiver doing anything (LB-paired routes
    averaged +16 degrees over expected without it, CB-paired -2).
    """
    routes = routes.copy()
    grp = routes.groupby(["coverage_type", "position", "def_group", "bucket"], dropna=False)
    routes["turn_lag_oe"] = routes["turn_lag"] - grp["turn_lag"].transform("mean")
    routes["mean_gap_oe"] = routes["mean_gap"] - grp["mean_gap"].transform("mean")
    return routes
