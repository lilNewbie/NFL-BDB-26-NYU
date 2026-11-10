"""Plain-language insight for one scored route."""
from __future__ import annotations

from .metric import FPS

HIGH, LOW = 15.0, -15.0  # degrees of Mean Gap Over Expected


def route_insight(r: dict) -> str:
    t_break = (r["break_frame"] - r["snap_frame"]) / FPS
    oe = r["mean_gap_oe"]
    name, dname = r["name"], f"{r['def_name']} ({r['def_position']})"
    if r["censored"]:
        turn = f"he never squared up to the new path before the ball came out, {r['turn_lag']:.1f}s later"
    elif r["turn_lag"] == 0:
        turn = "he was already facing the new path as the break happened"
    else:
        turn = f"he took {r['turn_lag']:.1f}s to get his shoulders within 45° of it"
    moved = "gained" if r["sep_gained"] >= 0 else "lost"
    sep = (f"{name} {moved} {abs(r['sep_gained']):.1f} yds of separation from him between the break and the throw "
           f"({r['sep_throw']:.1f} yds at release).")
    target = ("He was the target on the play." if r["is_target"]
              else "The ball went elsewhere, so no box score or catch-point separation stat credits this rep.")

    if oe >= HIGH:
        verdict = (f"<b>High score ({oe:+.0f}°).</b> {name} turned his man around. After his {r['bucket']} break at "
                   f"{t_break:.1f}s, {dname} was still facing {r['gap_at_break']:.0f}° off the new path, and {turn}. "
                   f"Through the throw his shoulders averaged {r['mean_gap']:.0f}° off, {oe:.0f}° worse than a "
                   f"typical defender against a {r['position']} on this kind of break.")
    elif oe <= LOW:
        verdict = (f"<b>Low score ({oe:+.0f}°).</b> {dname} stayed closer to square with {name} than most "
                   f"defenders do. At the {r['bucket']} break ({t_break:.1f}s) he was {r['gap_at_break']:.0f}° off "
                   f"the new path and {turn}. From the break to the throw his shoulders averaged "
                   f"{r['mean_gap']:.0f}° off, {abs(oe):.0f}° better than a typical defender against a "
                   f"{r['position']} on this kind of break, so the route turned him less than usual.")
    else:
        verdict = (f"<b>Average rep ({oe:+.0f}°).</b> After {name}'s {r['bucket']} break at {t_break:.1f}s, "
                   f"{dname} was {r['gap_at_break']:.0f}° off the new path and {turn}. That is close to what a "
                   f"typical defender does against a {r['position']} on this kind of break.")
    return f"{verdict} {sep} {target}"
