"""Hover definitions for the dashboard: what each term means and what it tells you.

`term(text, key)` wraps `text` in a span that shows the definition on hover or
keyboard focus. Styling and positioning live in TIP_CSS / TIP_JS.
"""
from __future__ import annotations

import html

# key: (title, meaning, what it tells you or None)
GLOSSARY: dict[str, tuple[str, str, str | None]] = {
    # ---- this project's metrics ----
    "turn_lag": ("Turn Lag",
                 "Seconds from the receiver's break until his paired defender's shoulders are within 45° of the "
                 "receiver's new direction.",
                 "Longer = the route left the defender facing the wrong way for longer, so he was beaten even if "
                 "separation hasn't shown it yet."),
    "mean_gap": ("Mean Gap",
                 "The average facing gap from the break to the throw, in degrees. Unlike Turn Lag it has no cap.",
                 "One number for how far, on average, the route kept the defender turned away."),
    "oe": ("Over Expected",
           "A value minus the average for similar routes: same coverage type, same receiver position (WR/TE/RB), "
           "same kind of defender (defensive back or linebacker) and same break type.",
           "Removes the route-shape effect. +10° means the defender was 10° further off than usual for that kind of "
           "route, so the credit goes to the receiver, not the route call."),
    "mgoe": ("Mean Gap Over Expected (headline)",
             "Mean Gap minus the average for comparable routes (same coverage type, receiver position, defender "
             "type and break type), averaged over a receiver's man-coverage routes.",
             "Positive = he turns his man around more than peers on comparable routes: a route-running skill that "
             "box scores and catch-point separation don't show. Negative = defenders stay square to him."),
    "facing_gap": ("Facing gap",
                   "Angle between where the paired defender's shoulders point and where the receiver is running. "
                   "0° = facing the receiver's path; 180° = facing the opposite way.",
                   "The live measure of how wrong-footed the defender is at each moment."),
    "turned": ("Turned (45°)",
               "The facing gap has dropped below 45°: the defender has squared up to the receiver's new path.",
               "The end point of Turn Lag. Before this the defender is effectively chasing blind."),
    "censored": ("Censored",
                 "The defender never got within 45° before the ball was thrown, so his true Turn Lag is unknown; it "
                 "is capped at the throw.",
                 "A strong win for the receiver. When many routes end this way, Turn Lag is capped on most reps, so "
                 "Mean Gap (no cap) becomes the headline."),
    "censor_threshold": ("30% censoring threshold",
                         "Set before the full run: if more than 30% of routes were censored, the headline would "
                         "switch from Turn Lag to Mean Gap.",
                         "Fixing the rule in advance means the headline wasn't picked after seeing which looked "
                         "better."),
    "break": ("Break",
              "The receiver's cut: his largest change in running direction over 0.5 s, at least 30°, while reaching "
              "2+ yd/s.",
              "Everything is measured from here, because this is the moment a man-coverage defender has to react."),
    "bucket": ("Break type",
               "The shape of the break: slight (30–60° change), sideways, back toward the line (curls, comebacks) "
               "or diagonal downfield.",
               "Some route shapes turn defenders more than others; comparing within a type keeps the comparison "
               "fair."),
    "paired_defender": ("Paired defender",
                        "The cornerback, safety or linebacker in coverage closest to the receiver over the first "
                        "second after the snap, and still within 5 yd at the break. Linemen dropping into coverage "
                        "are never paired.",
                        "Our stand-in for 'the man covering him', since the data has no coverage assignments. "
                        "It's a heuristic, so read single plays with care."),
    "sep_throw": ("Separation at throw",
                  "Yards between the receiver and his paired defender when the ball leaves the quarterback's hand.",
                  "How open he was at the decision point. Tracking stops just after the throw, so this replaces "
                  "the usual catch-point separation."),
    "sep_gained": ("Separation gained",
                   "Separation at the throw minus separation at the break.",
                   "Whether turning the defender actually turned into space before the ball came out."),
    "def_ahead": ("Defender ahead at throw",
                  "The defender is further downfield than the receiver when the ball is thrown.",
                  "Used only as a validation check: a corner staying over the top faces away from the receiver "
                  "behind him, which could fake a high score."),
    "r": ("r (correlation)",
          "Pearson correlation, from −1 to +1. 0 = no linear relationship; about ±0.1–0.3 is weak, ±0.3–0.5 "
          "moderate.",
          None),
    "r_def_ahead": ("Validation: r with 'defender ahead'",
                    "Correlation between the headline metric and the defender being ahead of the receiver at the "
                    "throw, across man-coverage routes.",
                    "Near 0 means the metric isn't secretly rewarding good over-the-top coverage."),
    "r_sep": ("r with separation at throw",
              "Correlation between a receiver's headline score and his average separation at the throw.",
              "A weak value means turning your man and being open at the throw are different skills. Receivers "
              "high on one and low on the other are the interesting cases."),
    "routes_scored": ("Routes with a detectable break",
                      "Skill-position routes with a break before the throw and a paired defender still close at the "
                      "break.",
                      "Go routes and very quick throws have no break to measure, so they're left out."),
    "min_routes": ("Qualifying (min 15 routes)",
                   "A player needs at least 15 scored man-coverage routes to appear on a leaderboard.",
                   "Fewer reps are too noisy to rank. Even at 15–38 routes, treat ranks as directional."),
    "leaderboard": ("Receiver leaderboard",
                    "Top 10 receivers by Mean Gap Over Expected against man coverage.",
                    "Who most often leaves the man covering him turned the wrong way, relative to peers on the same "
                    "routes."),
    "scatter": ("Scatter: turning vs being open",
                "Each dot is a receiver: headline score across, separation at the throw up. Bigger dot = more "
                "routes.",
                "Lower right = beats his man but isn't open when the ball comes out, so separation stats undersell "
                "his route running and timing or play design is the likelier issue."),
    "flip_side": ("Defender view",
                  "The same numbers grouped by the paired defender instead of the receiver.",
                  "Low (negative) values = receivers rarely turn him: sticky man coverage. A sanity check, since "
                  "no coverage data was used to build it."),
    "high_score": ("High score (≥ +15°)",
                   "On this rep the defender's shoulders stayed at least 15° further off than usual for this kind "
                   "of route.",
                   "The receiver won the rep with his route, whether or not he got the ball."),
    "low_score": ("Low score (≤ −15°)",
                  "On this rep the defender stayed at least 15° closer to square than usual.",
                  "The defender handled the break; the route didn't turn him."),
    "avg_score": ("Average rep",
                  "Within ±15° of what's typical for this kind of route.",
                  None),
    "spotlight": ("Spotlight receiver",
                  "The receiver this replay is about, ringed in yellow and linked to his paired defender by a "
                  "dashed line.",
                  None),
    "wedge": ("Facing-gap wedge",
              "Drawn at the paired defender, spanning from where his shoulders face to the receiver's path. Grey "
              "before the break, red while the gap is ≥45°, green once he has turned.",
              "The longer it stays red after the break, the bigger the receiver's win."),
    "readout": ("Readout line",
                "Above the field: spotlight receiver vs paired defender, seconds since the snap, separation (sep), "
                "facing gap, and the Turn Lag timer (TURNING… then TURNED).",
                None),
    "slider_break": ("BREAK on the slider",
                     "The tick where the spotlight receiver makes his cut.",
                     "Pause there and step forward to watch whether the defender's yellow arrow follows."),
    # ---- data and tracking ----
    "o": ("o (orientation)",
          "The direction a player's shoulders face, in degrees, from the sensors in his shoulder pads.",
          "The key input: it shows where a defender is looking and set up, which position data alone can't."),
    "dir": ("dir (direction)",
            "The direction a player is moving, in degrees.",
            "Compared with the defender's o to get the facing gap."),
    "ngs": ("NGS (Next Gen Stats)",
            "The NFL's player-tracking system: chips in the shoulder pads record position, speed and orientation "
            "10 times per second.",
            None),
    "man": ("Man coverage",
            "Each defender follows a specific receiver.",
            "The only coverage where a defender's facing says something about one receiver's route, so the "
            "headline numbers use man coverage only."),
    "zone": ("Zone coverage",
             "Each defender guards an area and keeps his eyes on the quarterback.",
             "Excluded from the headline: a zone defender facing away from a receiver is usually doing his job."),
    "target": ("Target",
               "The receiver the pass was thrown to, read from the play description.",
               None),
    "down_distance": ("Down & distance",
                      "e.g. 2&8 = 2nd down, 8 yards to go for a first down.",
                      None),
    "quarter": ("Quarter", "Q1–Q4: which quarter of the game the play was in.", None),
    "shoulders": ("Shoulders, not hips",
                  "The orientation sensor sits in the shoulder pads, so the metric measures shoulders. Hips usually "
                  "follow but can lag.",
                  None),
    "association": ("Association, not causation",
                    "A defender still turned after a break is consistent with the route beating him, but the data "
                    "can't prove the route caused it.",
                    None),
}

COVERAGES = {
    "Cover-0": "Man coverage across the board with no deep safety, usually paired with a blitz.",
    "Cover-1": "Man coverage with one deep safety helping over the top.",
    "Cover-2": "Two deep safeties with zone coverage underneath.",
    "2-Man": "Two deep safeties with man coverage underneath.",
    "Cover-3": "Three deep defenders and four underneath, all in zones.",
    "Quarters": "Four deep, three under: each deep defender takes a quarter of the field.",
    "Cover-6": "Quarters on one half of the field, Cover-2 on the other.",
    "Bracket": "Two defenders bracket one receiver, one inside and one outside.",
    "Goal Line": "Goal-line defense.",
    "Red Zone": "A call specific to the red zone (inside the 20).",
    "Prevent": "End-of-half or end-of-game defense that gives up short gains to stop deep ones.",
    "Miscellaneous": "A coverage that doesn't fit the standard categories.",
}

POSITIONS = {
    "WR": "Wide receiver", "TE": "Tight end", "RB": "Running back", "FB": "Fullback", "QB": "Quarterback",
    "CB": "Cornerback: usually covers wide receivers", "FS": "Free safety: deep coverage",
    "SS": "Strong safety: often covers tight ends or plays near the line", "DB": "Defensive back",
    "OLB": "Outside linebacker", "ILB": "Inside linebacker", "MLB": "Middle linebacker", "LB": "Linebacker",
    "DE": "Defensive end", "DT": "Defensive tackle", "NT": "Nose tackle",
}


def _tip(title: str, meaning: str, why: str | None) -> str:
    body = f"<b>{html.escape(title)}</b>{html.escape(meaning)}"
    if why:
        body += f"<em>What it tells you</em>{html.escape(why)}"
    return f'<span class="tip" role="tooltip">{body}</span>'


def term(text: str, key: str, escape: bool = True) -> str:
    """Wrap visible `text` with the hover definition for `key`."""
    title, meaning, why = GLOSSARY[key]
    label = html.escape(text) if escape else text
    return f'<span class="term" tabindex="0">{label}{_tip(title, meaning, why)}</span>'


def coverage_term(name: str) -> str:
    desc = COVERAGES.get(str(name))
    if not desc:
        return html.escape(str(name))
    return f'<span class="term" tabindex="0">{html.escape(str(name))}{_tip(str(name), desc, None)}</span>'


def position_term(pos: str) -> str:
    desc = POSITIONS.get(str(pos))
    if not desc:
        return html.escape(str(pos))
    return f'<span class="term" tabindex="0">{html.escape(str(pos))}{_tip(str(pos), desc, None)}</span>'


TIP_CSS = """
.term{border-bottom:1px dotted #a5d6a7;cursor:help;position:relative;outline:none}
.term:hover,.term:focus{color:#fff}
.term .tip{display:none;position:absolute;left:0;top:calc(100% + 6px);z-index:1000;width:320px;
background:#0b1610;border:1px solid #4caf50;border-radius:8px;padding:10px 12px;box-shadow:0 6px 24px rgba(0,0,0,.6);
color:#eceff1;font-size:13px;font-style:normal;font-weight:normal;line-height:1.45;text-align:left;
white-space:normal;text-transform:none;letter-spacing:normal}
.term .tip b{display:block;color:#fff59d;font-size:14px;margin-bottom:4px}
.term .tip em{display:block;font-style:normal;color:#a5d6a7;font-weight:600;margin-top:8px}
.term:hover .tip,.term:focus .tip{display:block}
.term .tip.flip{left:auto;right:0}
.card .term .tip b{display:block;font-size:14px}
"""

# Keep tooltips on screen: flip to right-aligned when they would overflow the window.
TIP_JS = """
document.querySelectorAll('.term').forEach(function(t){
  function place(){var tip=t.querySelector('.tip'); if(!tip) return; tip.classList.remove('flip');
    var r=tip.getBoundingClientRect(); if(r.right>window.innerWidth-8) tip.classList.add('flip');}
  t.addEventListener('mouseenter',place); t.addEventListener('focus',place);
});
"""
