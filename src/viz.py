"""Plotly animated field replay with defender facing arrows and the Turn Lag wedge."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .angles import ang_diff
from .data import FIELD_LENGTH, FIELD_WIDTH
from .metric import FPS, GAP_THRESHOLD

TEAM_COLORS = {
    "ARI": "#97233F", "ATL": "#A71930", "BAL": "#241773", "BUF": "#00338D", "CAR": "#0085CA",
    "CHI": "#C83803", "CIN": "#FB4F14", "CLE": "#FF3C00", "DAL": "#869397", "DEN": "#FB4F14",
    "DET": "#0076B6", "GB": "#203731", "HOU": "#03202F", "IND": "#002C5F", "JAX": "#006778",
    "KC": "#E31837", "LA": "#003594", "LAC": "#0080C6", "LV": "#A5ACAF", "MIA": "#008E97",
    "MIN": "#4F2683", "NE": "#002244", "NO": "#D3BC8D", "NYG": "#0B2265", "NYJ": "#125740",
    "PHI": "#004C54", "PIT": "#FFB612", "SEA": "#69BE28", "SF": "#AA0000", "TB": "#D50A0A",
    "TEN": "#4B92DB", "WAS": "#773141",
}
TURF = "#2e7d32"
TURF_DARK = "#1b5e20"
RED = "rgba(229,57,53,0.55)"
GREEN = "rgba(102,187,106,0.55)"
GREY = "rgba(200,200,200,0.35)"
ARROW_LEN = 2.2
WEDGE_R = 4.0


def _field_layout(los: float | None, first_down: float | None) -> dict:
    shapes = [
        dict(type="rect", x0=0, x1=FIELD_LENGTH, y0=0, y1=FIELD_WIDTH, fillcolor=TURF,
             line=dict(color="white", width=2), layer="below"),
        dict(type="rect", x0=0, x1=10, y0=0, y1=FIELD_WIDTH, fillcolor=TURF_DARK, line_width=0, layer="below"),
        dict(type="rect", x0=110, x1=120, y0=0, y1=FIELD_WIDTH, fillcolor=TURF_DARK, line_width=0, layer="below"),
    ]
    for x in range(10, 111, 5):
        shapes.append(dict(type="line", x0=x, x1=x, y0=0, y1=FIELD_WIDTH, layer="below",
                           line=dict(color="rgba(255,255,255,%s)" % (0.8 if x % 10 == 0 else 0.4), width=1)))
    if los is not None:
        shapes.append(dict(type="line", x0=los, x1=los, y0=0, y1=FIELD_WIDTH, layer="below",
                           line=dict(color="#42a5f5", width=3)))
    if first_down is not None and 0 < first_down < FIELD_LENGTH:
        shapes.append(dict(type="line", x0=first_down, x1=first_down, y0=0, y1=FIELD_WIDTH, layer="below",
                           line=dict(color="#fdd835", width=3)))
    annotations = []
    for x in range(20, 101, 10):
        num = x - 10 if x <= 60 else 110 - x
        for y, rot in ((5, 0), (FIELD_WIDTH - 5, 180)):
            annotations.append(dict(x=x, y=y, text=f"<b>{num}</b>", showarrow=False, textangle=rot,
                                    font=dict(color="rgba(255,255,255,0.75)", size=18, family="Arial Black")))
    annotations.append(dict(x=60, y=-3.2, text="offense moving →", showarrow=False,
                            font=dict(color="#cfd8dc", size=12)))
    return dict(shapes=shapes, annotations=annotations)


def _arrows(df: pd.DataFrame, angle_col: str):
    """Line segments plus tip markers pointing along `angle_col` (NGS angle)."""
    xs, ys, tx, ty, ta = [], [], [], [], []
    for r in df.itertuples():
        ang = getattr(r, angle_col)
        if np.isnan(ang):
            continue
        dx, dy = np.sin(np.deg2rad(ang)) * ARROW_LEN, np.cos(np.deg2rad(ang)) * ARROW_LEN
        xs += [r.x, r.x + dx, None]
        ys += [r.y, r.y + dy, None]
        tx.append(r.x + dx)
        ty.append(r.y + dy)
        ta.append(ang)
    return xs, ys, tx, ty, ta


def _wedge(cx, cy, a_from, a_to, r=WEDGE_R, n=20):
    signed = ((a_to - a_from + 180.0) % 360.0) - 180.0
    thetas = a_from + np.linspace(0, signed, n)
    xs = [cx] + list(cx + r * np.sin(np.deg2rad(thetas))) + [cx]
    ys = [cy] + list(cy + r * np.cos(np.deg2rad(thetas))) + [cy]
    return xs, ys


def _frame_traces(fr: pd.DataFrame, off_team: str, def_team: str, route: dict | None,
                  idx: int, trail: pd.DataFrame | None, readout: str):
    players = fr[fr["nflId"].notna()]
    off = players[players["team"] == off_team]
    dfn = players[players["team"] == def_team]
    ball = fr[fr["team"] == "football"]

    def hover(d):
        return [f"{n} ({p})<br>{role}<br>{s:.1f} yd/s" for n, p, role, s in
                zip(d["displayName"], d["officialPosition"], d["pff_role"].fillna(""), d["s"])]

    # Offense is always cream (team color as the outline) so it never blends with the
    # defense when both teams wear dark colors, e.g. LA vs HOU.
    oc = TEAM_COLORS.get(off_team, "#e53935")
    dc = TEAM_COLORS.get(def_team, "#1e88e5")
    traces = [
        go.Scatter(x=off["x"], y=off["y"], mode="markers+text", text=off["jerseyNumber"].astype("Int64").astype(str),
                   textfont=dict(color="#111111", size=9), hovertext=hover(off), hoverinfo="text",
                   marker=dict(size=17, color="#f5f0e1", line=dict(color=oc, width=2.5)),
                   name=f"{off_team} (offense)"),
        go.Scatter(x=dfn["x"], y=dfn["y"], mode="markers+text", text=dfn["jerseyNumber"].astype("Int64").astype(str),
                   textfont=dict(color="white", size=9), hovertext=hover(dfn), hoverinfo="text",
                   marker=dict(size=17, color=dc, line=dict(color="white", width=1.5)),
                   name=f"{def_team} (defense)"),
        go.Scatter(x=ball["x"], y=ball["y"], mode="markers", hoverinfo="skip", name="ball",
                   marker=dict(size=9, color="#8d6e63", symbol="diamond", line=dict(color="white", width=1))),
    ]
    cov = dfn[dfn["pff_role"] == "Coverage"]
    xs, ys, tx, ty, ta = _arrows(cov, "o_s")
    traces.append(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#fff59d", width=2),
                             hoverinfo="skip", name="defender facing (o)"))
    traces.append(go.Scatter(x=tx, y=ty, mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(symbol="triangle-up", size=9, angle=ta, color="#fff59d")))
    rts = off[off["pff_role"] == "Pass Route"]
    xs, ys, tx, ty, ta = _arrows(rts, "dir_s")
    traces.append(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#80deea", width=2),
                             hoverinfo="skip", name="receiver path (dir)"))
    traces.append(go.Scatter(x=tx, y=ty, mode="markers", hoverinfo="skip", showlegend=False,
                             marker=dict(symbol="triangle-up", size=9, angle=ta, color="#80deea")))

    # Spotlight: trail, pairing line and wedge.
    wx, wy, color, px, py, trx, tryy = [None], [None], GREY, [None], [None], [None], [None]
    if route is not None:
        rec = players[players["nflId"] == route["nflId"]]
        d = players[players["nflId"] == route["def_id"]]
        if len(rec) and len(d):
            rec, d = rec.iloc[0], d.iloc[0]
            wx, wy = _wedge(d["x"], d["y"], d["o_s"], rec["dir_s"])
            b = route["series"]["b_idx"]
            gap = float(ang_diff(d["o_s"], rec["dir_s"]))
            color = GREY if idx < b else (RED if gap >= GAP_THRESHOLD else GREEN)
            px, py = [rec["x"], d["x"]], [rec["y"], d["y"]]
        if trail is not None and len(trail):
            trx, tryy = list(trail["x"]), list(trail["y"])
    traces.append(go.Scatter(x=trx, y=tryy, mode="lines", line=dict(color="#80deea", width=3, dash="dot"),
                             hoverinfo="skip", name="spotlight route"))
    traces.append(go.Scatter(x=px, y=py, mode="lines+markers", line=dict(color="white", width=1, dash="dash"),
                             marker=dict(size=[30, 0], color="rgba(0,0,0,0)", line=dict(color="#fdd835", width=3)),
                             hoverinfo="skip", name="spotlight receiver ↔ paired defender"))
    traces.append(go.Scatter(x=wx, y=wy, mode="lines", fill="toself", fillcolor=color,
                             line=dict(color=color.replace("0.55", "0.9").replace("0.35", "0.6"), width=1),
                             hoverinfo="skip", name="facing gap"))
    traces.append(go.Scatter(x=[1], y=[FIELD_WIDTH + 3.3], mode="text", text=[readout], textposition="middle right",
                             textfont=dict(color="white", size=14, family="Consolas, monospace"),
                             hoverinfo="skip", showlegend=False))
    return traces


def _readout(route: dict | None, idx: int, frame_id: int) -> str:
    t = (frame_id - route["snap_frame"]) / FPS if route else 0.0
    if route is None:
        return f"t={t:.1f}s"
    s = route["series"]
    b = s["b_idx"]
    gap = s["gap"][idx]
    sep = s["dist"][idx]
    head = f"{route['name']} vs {route['def_name']}  |  t={t:.1f}s  |  sep {sep:.1f} yd  |  facing gap {gap:.0f}°"
    if idx < b:
        return head + "  |  before break"
    elapsed = (idx - b) / FPS
    lag = route["turn_lag"]
    if not route["censored"] and elapsed >= lag:
        return head + f"  |  TURNED  ·  Turn Lag {lag:.1f}s"
    return head + f"  |  TURNING…  {elapsed:.1f}s"


def make_play_figure(play: pd.DataFrame, route: dict | None, title: str = "") -> go.Figure:
    """Animated replay of one play's snap-to-throw window.

    `route` is a compute_play row with `series` (keep_series=True), or None.
    """
    info = play.iloc[0]
    off_team, def_team = info["possessionTeam"], info["defensiveTeam"]
    frames_ids = sorted(play["frameId"].unique())
    snap_ball = play[(play["team"] == "football") & (play["frameId"] == frames_ids[0])]
    los = float(snap_ball["x"].iloc[0]) if len(snap_ball) else None
    first_down = los + float(info["yardsToGo"]) if los is not None and pd.notna(info["yardsToGo"]) else None
    by_frame = {f: g for f, g in play.groupby("frameId")}
    rec_path = play[play["nflId"] == route["nflId"]].sort_values("frameId") if route else None

    frames = []
    for i, f in enumerate(frames_ids):
        trail = rec_path[rec_path["frameId"] <= f] if rec_path is not None else None
        frames.append(go.Frame(name=str(f), data=_frame_traces(by_frame[f], off_team, def_team, route, i, trail,
                                                               _readout(route, i, f))))

    layout = _field_layout(los, first_down)
    fig = go.Figure(data=frames[0].data, frames=frames)
    steps = [dict(method="animate", label=f"{(f - frames_ids[0]) / FPS:.1f}",
                  args=[[str(f)], dict(mode="immediate", frame=dict(duration=0, redraw=True),
                                       transition=dict(duration=0))]) for f in frames_ids]
    if route is not None:
        b = route["series"]["b_idx"]
        steps[b]["label"] = f"BREAK {steps[b]['label']}"
    fig.update_layout(
        title=dict(text=title, font=dict(color="white", size=16), x=0.01),
        paper_bgcolor="#0d1b12", plot_bgcolor="#0d1b12", font=dict(color="white"),
        xaxis=dict(range=[-1, FIELD_LENGTH + 1], showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(range=[-5, FIELD_WIDTH + 6], showgrid=False, zeroline=False, showticklabels=False,
                   scaleanchor="x", scaleratio=1),
        legend=dict(orientation="h", y=-0.02, x=0, font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=10, r=10, t=50, b=10), height=640,
        shapes=layout["shapes"], annotations=layout["annotations"],
        updatemenus=[dict(type="buttons", showactive=False, x=0.0, y=-0.08, xanchor="left", direction="left",
                          buttons=[
                              dict(label="▶ Play", method="animate",
                                   args=[None, dict(frame=dict(duration=100, redraw=True), fromcurrent=True,
                                                    transition=dict(duration=0))]),
                              dict(label="❚❚ Pause", method="animate",
                                   args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))]),
                              dict(label="0.25× slow-mo", method="animate",
                                   args=[None, dict(frame=dict(duration=400, redraw=True), fromcurrent=True,
                                                    transition=dict(duration=0))]),
                          ])],
        sliders=[dict(active=0, x=0.25, len=0.75, y=-0.06, steps=steps,
                      currentvalue=dict(prefix="seconds after snap: ", font=dict(color="white")),
                      font=dict(color="white", size=9))],
    )
    return fig
