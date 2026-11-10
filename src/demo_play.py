"""Render one play's animated replay to out/play_<gameId>_<playId>.html.

Usage: python -m src.demo_play [gameId] [playId] [receiver nflId]
"""
from __future__ import annotations

import sys

from .data import ROOT, orientation_check, prepare_game
from .metric import compute_play
from .viz import make_play_figure


def main(game_id=2021090900, play_id=97, rec_id=None):
    df = prepare_game(game_id)
    play = df[df["playId"] == play_id]
    print("o check:", orientation_check(df))
    routes = compute_play(play, keep_series=True)
    for r in routes:
        print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items() if k != "series"})
    if rec_id is not None:
        route = next(r for r in routes if r["nflId"] == rec_id)
    else:
        route = next((r for r in routes if r["is_target"]), None) or max(routes, key=lambda r: r["turn_lag"], default=None)
    info = play.iloc[0]
    title = f"{info['possessionTeam']} vs {info['defensiveTeam']} · {info['pff_passCoverage']} ({info['pff_passCoverageType']})"
    fig = make_play_figure(play, route, title)
    out = ROOT / "out" / f"play_{game_id}_{play_id}.html"
    out.parent.mkdir(exist_ok=True)
    fig.write_html(out, include_plotlyjs="cdn", auto_play=False)
    print("wrote", out, "frames:", len(fig.frames))
    return fig


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]]
    main(*args)
