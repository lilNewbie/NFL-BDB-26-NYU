"""Data loading, direction normalization, smoothing and snap-to-throw windowing."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "nfl-big-data-bowl-regional-event-data" / "data"
TRACKING_DIR = DATA_DIR / "tracking"

SNAP_EVENTS = {"ball_snap", "autoevent_ballsnap"}
THROW_EVENTS = {"pass_forward", "autoevent_passforward"}
SKILL_POSITIONS = {"WR", "TE", "RB"}
FIELD_LENGTH = 120.0
FIELD_WIDTH = 53.3


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name, na_values=["NA"])


@lru_cache(maxsize=None)
def load_games() -> pd.DataFrame:
    return _read("games.csv")


@lru_cache(maxsize=None)
def load_plays() -> pd.DataFrame:
    return _read("plays.csv")


@lru_cache(maxsize=None)
def load_players() -> pd.DataFrame:
    return _read("players.csv")


@lru_cache(maxsize=None)
def load_pff() -> pd.DataFrame:
    return _read("pffScoutingData.csv")


def list_game_ids() -> list[int]:
    return sorted(int(p.stem.split("_")[1]) for p in TRACKING_DIR.glob("tracking_*.csv"))


def load_tracking(game_id: int) -> pd.DataFrame:
    df = pd.read_csv(TRACKING_DIR / f"tracking_{game_id}.csv", na_values=["NA"])
    df["event"] = df["event"].where(df["event"] != "None")
    return df.sort_values(["playId", "nflId", "frameId"], na_position="last").reset_index(drop=True)


def normalize_direction(df: pd.DataFrame) -> pd.DataFrame:
    """Rotate left-moving plays by 180 degrees so every offense moves toward +x.

    Flipping both axes (x -> 120 - x, y -> 53.3 - y) is a true rotation, so
    angles map as theta -> theta + 180. Flipping x alone would be a reflection
    and break every angle comparison.
    """
    df = df.copy()
    left = df["playDirection"] == "left"
    df.loc[left, "x"] = FIELD_LENGTH - df.loc[left, "x"]
    df.loc[left, "y"] = FIELD_WIDTH - df.loc[left, "y"]
    for col in ("o", "dir"):
        df.loc[left, col] = (df.loc[left, col] + 180.0) % 360.0
    return df


def smooth_angles(df: pd.DataFrame, cols=("o", "dir")) -> pd.DataFrame:
    """Centered 3-frame circular mean per player per play. Adds `<col>_s` columns."""
    df = df.copy()
    keys = [df["playId"], df["nflId"].fillna(-1)]
    for col in cols:
        rad = np.deg2rad(df[col])
        parts_s, parts_c = [], []
        for shift in (-1, 0, 1):
            if shift == 0:
                parts_s.append(np.sin(rad))
                parts_c.append(np.cos(rad))
            else:
                parts_s.append(np.sin(rad).groupby(keys).shift(shift))
                parts_c.append(np.cos(rad).groupby(keys).shift(shift))
        s = pd.concat(parts_s, axis=1).mean(axis=1, skipna=True)
        c = pd.concat(parts_c, axis=1).mean(axis=1, skipna=True)
        df[f"{col}_s"] = np.rad2deg(np.arctan2(s, c)) % 360.0
    return df


def _first_frame(ev: pd.DataFrame, manual: str, auto: str) -> pd.Series:
    """First frame of the manual tag per play, falling back to the auto tag.

    Manual tags are preferred because the auto tags can be early: on play 97
    `autoevent_passforward` is frame 38 but the ball only leaves at frame 40.
    """
    m = ev[ev["event"] == manual].groupby("playId")["frameId"].min()
    a = ev[ev["event"] == auto].groupby("playId")["frameId"].min()
    return m.combine_first(a)


def play_windows(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per play with snap_frame and throw_frame (NaN if missing)."""
    ev = df.loc[df["event"].notna(), ["playId", "frameId", "event"]].drop_duplicates()
    out = pd.DataFrame({"playId": df["playId"].unique()}).set_index("playId")
    out["snap_frame"] = _first_frame(ev, "ball_snap", "autoevent_ballsnap")
    out["throw_frame"] = _first_frame(ev, "pass_forward", "autoevent_passforward")
    bad = out["throw_frame"] <= out["snap_frame"]
    out.loc[bad, "throw_frame"] = np.nan
    return out.reset_index()


def attach_context(df: pd.DataFrame, game_id: int) -> pd.DataFrame:
    """Attach PFF role, player position/name and play coverage info."""
    pff = load_pff()
    pff = pff.loc[pff["gameId"] == game_id, ["playId", "nflId", "pff_role", "pff_positionLinedUp"]]
    players = load_players()[["nflId", "officialPosition", "displayName"]]
    plays = load_plays()
    plays = plays.loc[plays["gameId"] == game_id,
                      ["playId", "pff_passCoverage", "pff_passCoverageType", "passResult",
                       "playDescription", "possessionTeam", "defensiveTeam", "down", "yardsToGo", "quarter"]]
    df = df.merge(pff, on=["playId", "nflId"], how="left")
    df = df.merge(players, on="nflId", how="left")
    df = df.merge(plays, on="playId", how="left")
    return df


def prepare_game(game_id: int, log: dict | None = None) -> pd.DataFrame:
    """Load one game, normalize, smooth, attach context, and keep only snap-to-throw frames.

    Plays without both a snap and a throw event are dropped and counted in `log`.
    """
    raw = load_tracking(game_id)
    df = smooth_angles(normalize_direction(raw))
    win = play_windows(df)
    valid = win.dropna(subset=["snap_frame", "throw_frame"])
    if log is not None:
        log["plays_total"] = log.get("plays_total", 0) + len(win)
        log["plays_dropped_no_snap_or_throw"] = log.get("plays_dropped_no_snap_or_throw", 0) + len(win) - len(valid)
    df = df.merge(valid, on="playId", how="inner")
    df = df[(df["frameId"] >= df["snap_frame"]) & (df["frameId"] <= df["throw_frame"])]
    df = attach_context(df, game_id)
    df["gameId"] = game_id
    return df.reset_index(drop=True)


def orientation_check(df: pd.DataFrame) -> dict:
    """At the snap, after normalization, offense should face roughly +x (90 deg)
    and coverage defenders roughly -x (270 deg). Returns the share of players
    facing within 90 degrees of the expected direction."""
    snap = df[(df["frameId"] == df["snap_frame"]) & df["nflId"].notna()].copy()
    offense = snap["team"] == snap["possessionTeam"]
    expected = np.where(offense, 90.0, 270.0)
    diff = np.abs((snap["o"].to_numpy() - expected + 180.0) % 360.0 - 180.0)
    ok = diff < 90.0
    return {
        "players_checked": int(len(snap)),
        "offense_facing_ok": float(ok[offense.to_numpy()].mean()) if offense.any() else float("nan"),
        "defense_facing_ok": float(ok[~offense.to_numpy()].mean()) if (~offense).any() else float("nan"),
    }
