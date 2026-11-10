"""Plain-language insight for one scored route, with hover definitions on the key terms."""
from __future__ import annotations

from .glossary import position_term, term
from .metric import FPS

HIGH, LOW = 15.0, -15.0  # degrees of Mean Gap Over Expected


def route_insight(r: dict) -> str:
    t_break = (r["break_frame"] - r["snap_frame"]) / FPS
    oe = r["mean_gap_oe"]
    name = r["name"]
    dname = "%s (%s)" % (r["def_name"], position_term(r["def_position"]))
    pos = position_term(r["position"])
    brk = term("%s break" % r["bucket"], "bucket")
    off_path = term("%.0f° off the new path" % r["gap_at_break"], "facing_gap")
    averaged = term("averaged %.0f° off" % r["mean_gap"], "mean_gap")
    lag_txt = "%.1fs" % r["turn_lag"]

    if r["censored"]:
        turn = ("he " + term("never squared up to the new path before the ball came out", "censored")
                + ", %s later" % lag_txt)
    elif r["turn_lag"] == 0:
        turn = "he was already facing the new path as the break happened"
    else:
        turn = "he took %s to get his shoulders %s of it" % (term(lag_txt, "turn_lag"), term("within 45°", "turned"))

    moved = "gained" if r["sep_gained"] >= 0 else "lost"
    gained = term("%s %.1f yds of separation" % (moved, abs(r["sep_gained"])), "sep_gained")
    at_release = term("%.1f yds at release" % r["sep_throw"], "sep_throw")
    sep = "%s %s from him between the break and the throw (%s)." % (name, gained, at_release)
    target = ("He was the %s on the play." % term("target", "target") if r["is_target"]
              else "The ball went elsewhere, so no box score or catch-point separation stat credits this rep.")

    if oe >= HIGH:
        label = term("High score (%+.0f°)" % oe, "high_score")
        vs = term("%.0f° worse than a typical defender" % oe, "oe")
        verdict = (f"<b>{label}.</b> {name} turned his man around. After his {brk} at {t_break:.1f}s, {dname} "
                   f"was still facing {off_path}, and {turn}. Through the throw his shoulders {averaged}, {vs} "
                   f"against a {pos} on this kind of break.")
    elif oe <= LOW:
        label = term("Low score (%+.0f°)" % oe, "low_score")
        vs = term("%.0f° better than a typical defender" % abs(oe), "oe")
        verdict = (f"<b>{label}.</b> {name}'s route did not turn his man: {dname} stayed closer to square with "
                   f"him than most defenders do. At the {brk} ({t_break:.1f}s) he was {off_path} and {turn}. "
                   f"From the break to the throw his shoulders {averaged}, {vs} against a {pos} on this kind of "
                   f"break, so the route turned him less than usual.")
    else:
        label = term("Average rep (%+.0f°)" % oe, "avg_score")
        typical = term("typical defender", "oe")
        verdict = (f"<b>{label}.</b> After {name}'s {brk} at {t_break:.1f}s, {dname} was {off_path} and {turn}. "
                   f"That is close to what a {typical} does against a {pos} on this kind of break.")
    return f"{verdict} {sep} {target}"
