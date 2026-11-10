"""Aggregate scored routes into the leaderboard, scatter, validation and the HTML dashboard.

Run after src.run_all:  python -m src.build
Writes out/dashboard.html (plus the published copy docs/index.html), out/leaderboard.csv,
out/cb_leaderboard.csv, out/summary.json.
"""
from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.offline import get_plotlyjs

from .data import ROOT, prepare_game
from .glossary import TIP_CSS, TIP_JS, coverage_term, position_term, term
from .insight import route_insight
from .metric import FPS, add_over_expected, compute_play
from .viz import make_play_figure

OUT = ROOT / "out"
MIN_ROUTES = 15
CENSOR_LIMIT = 0.30
SMOKE_NAMES = ["Cooper Kupp", "Davante Adams", "Justin Jefferson", "Deebo Samuel", "Ja'Marr Chase",
               "Travis Kelce", "Mark Andrews"]
POS_COLORS = {"WR": "#4fc3f7", "TE": "#ffb74d", "RB": "#aed581"}
DARK = dict(paper_bgcolor="#0d1b12", plot_bgcolor="#13251a", font=dict(color="white"))


def load_routes() -> pd.DataFrame:
    return add_over_expected(pd.read_csv(OUT / "routes.csv"))


def choose_headline(man: pd.DataFrame) -> tuple[str, str, float]:
    share = float(man["censored"].mean())
    if share > CENSOR_LIMIT:
        return "mean_gap_oe", (f"{share:.0%} of man-coverage routes end with the defender still turned when the ball "
                               f"is thrown (censored), above the {CENSOR_LIMIT:.0%} censoring threshold we set in "
                               f"advance, so time-to-turn is capped on most reps. The headline is therefore Mean Gap Over Expected, which has no cap."), share
    return "turn_lag_oe", f"Only {share:.0%} of man-coverage routes are censored, so Turn Lag Over Expected is the headline.", share


def player_table(man: pd.DataFrame, headline: str) -> pd.DataFrame:
    g = man.groupby(["nflId", "name", "position", "team"], dropna=False)
    t = g.agg(routes=("playId", "size"), headline=(headline, "mean"), turn_lag=("turn_lag", "mean"),
              turn_lag_oe=("turn_lag_oe", "mean"), mean_gap=("mean_gap", "mean"),
              mean_gap_oe=("mean_gap_oe", "mean"), censored=("censored", "mean"),
              sep_throw=("sep_throw", "mean"), sep_gained=("sep_gained", "mean"),
              targets=("is_target", "sum")).reset_index()
    # A player can appear under two teams if traded; keep his main row.
    t = t.sort_values("routes", ascending=False).drop_duplicates("nflId")
    return t[t["routes"] >= MIN_ROUTES].sort_values("headline", ascending=False).reset_index(drop=True)


def cb_table(man: pd.DataFrame, headline: str) -> pd.DataFrame:
    g = man.groupby(["def_id", "def_name", "def_position"])
    t = g.agg(routes=("playId", "size"), headline=(headline, "mean"), turn_lag=("turn_lag", "mean"),
              sep_throw=("sep_throw", "mean")).reset_index()
    return t[t["routes"] >= MIN_ROUTES].sort_values("headline").reset_index(drop=True)


def leaderboard_fig(tbl: pd.DataFrame, label: str) -> go.Figure:
    top = tbl.head(10).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top["headline"], y=[f"{n} ({p}, {t})" for n, p, t in zip(top["name"], top["position"], top["team"])],
        orientation="h", marker_color=[POS_COLORS.get(p, "#ccc") for p in top["position"]],
        text=[f"{v:+.1f}°  ·  {r} routes  ·  {s:.1f} yd sep" for v, r, s in zip(top["headline"], top["routes"], top["sep_throw"])],
        textposition="inside", insidetextanchor="start",
        hovertemplate="%{y}<br>" + label + ": %{x:.1f}°<extra></extra>"))
    fig.update_layout(title=f"Top 10 receivers vs man coverage (min {MIN_ROUTES} routes)",
                      xaxis_title=f"{label} (°)",
                      height=460, margin=dict(l=10, r=10, t=50, b=50), **DARK)
    return fig


def scatter_fig(tbl: pd.DataFrame, label: str, r: float) -> go.Figure:
    fig = go.Figure()
    for pos, sub in tbl.groupby("position"):
        fig.add_trace(go.Scatter(
            x=sub["headline"], y=sub["sep_throw"], mode="markers", name=pos,
            marker=dict(size=np.clip(sub["routes"] / 2, 6, 22), color=POS_COLORS.get(pos, "#ccc"),
                        line=dict(color="white", width=0.5), opacity=0.85),
            text=sub["name"], customdata=sub[["routes", "team"]],
            hovertemplate="%{text} (%{customdata[1]})<br>" + label + ": %{x:.1f}°<br>separation at throw: %{y:.2f} yd"
                          "<br>%{customdata[0]} routes<extra></extra>"))
    for n in tbl.head(5)["name"].tolist() + tbl.sort_values("sep_throw", ascending=False).head(3)["name"].tolist():
        row = tbl[tbl["name"] == n].iloc[0]
        fig.add_annotation(x=row["headline"], y=row["sep_throw"], text=n.split()[-1], showarrow=False,
                           yshift=12, font=dict(size=10, color="#eceff1"))
    xm, ym = 0.0, float(tbl["sep_throw"].median())
    fig.add_vline(x=xm, line=dict(color="rgba(255,255,255,0.3)", dash="dot"))
    fig.add_hline(y=ym, line=dict(color="rgba(255,255,255,0.3)", dash="dot"))
    fig.add_annotation(xref="paper", yref="paper", x=0.99, y=0.02, xanchor="right", showarrow=False,
                       text="turns his man, but not open at the throw<br>(scheme or timing didn't reward it)",
                       font=dict(size=11, color="#ffcc80"))
    fig.add_annotation(xref="paper", yref="paper", x=0.99, y=0.98, xanchor="right", showarrow=False,
                       text="turns his man and gets open", font=dict(size=11, color="#a5d6a7"))
    fig.add_annotation(xref="paper", yref="paper", x=0.01, y=0.98, xanchor="left", showarrow=False,
                       text=f"player-level r = {r:+.2f}", font=dict(size=12, color="#fff59d"))
    fig.update_layout(title=f"{label} vs separation at the throw",
                      xaxis_title=f"{label} (°)", yaxis_title="mean separation at throw (yd)",
                      height=520, margin=dict(l=10, r=10, t=50, b=50), **DARK)
    return fig


def pick_heroes(man: pd.DataFrame, tbl: pd.DataFrame, headline: str) -> list[dict]:
    picks, used, players = [], set(), set()

    def add(row, why):
        key = (int(row["gameId"]), int(row["playId"]))
        if key not in used:
            used.add(key)
            players.add(int(row["nflId"]))
            picks.append({"gameId": key[0], "playId": key[1], "nflId": int(row["nflId"]), "why": why})

    demo = man[(man["gameId"] == 2021090900) & (man["playId"] == 97) & man["is_target"]]
    if len(demo):
        add(demo.iloc[0], "Opening play of the season: Brady deep to Godwin, Cover-1")
    # Showcase reps must be unambiguous man matchups: a cornerback on a wide receiver,
    # with a separation at the throw in the range real man coverage produces. This only
    # affects which replays are featured, not the metric or the leaderboards.
    clean = (man["def_position"] == "CB") & (man["position"] == "WR") & (man["sep_throw"] <= 6.0) \
        & (man["break_frame"] - man["snap_frame"] >= 8)
    top_ids = set(tbl.head(10)["nflId"])
    pool = man[clean & man["nflId"].isin(top_ids) & (man["sep_gained"] > 1.0)]
    if len(pool):
        add(pool.sort_values(headline, ascending=False).iloc[0], "Leaderboard player turning his man")
    pool = man[clean & ~man["is_target"] & (man["sep_gained"] > 1.5)]
    if len(pool):
        add(pool.sort_values(headline, ascending=False).iloc[0], "Uncredited rep: won his man, ball went elsewhere")
    pool = man[clean & man["is_target"] & ~man["nflId"].isin(players)]
    if len(pool):
        add(pool.sort_values(headline).iloc[0], "Low score: defender stays square through the break")
    return picks


def hero_figures(picks: list[dict], routes: pd.DataFrame):
    cache, out = {}, []
    for p in picks:
        if p["gameId"] not in cache:
            cache[p["gameId"]] = prepare_game(p["gameId"])
        play = cache[p["gameId"]]
        play = play[play["playId"] == p["playId"]]
        scored = compute_play(play, keep_series=True)
        route = next(r for r in scored if r["nflId"] == p["nflId"])
        oe = routes[(routes["gameId"] == p["gameId"]) & (routes["playId"] == p["playId"]) & (routes["nflId"] == p["nflId"])]
        route["mean_gap_oe"] = float(oe["mean_gap_oe"].iloc[0])
        route["turn_lag_oe"] = float(oe["turn_lag_oe"].iloc[0])
        info = play.iloc[0]
        p.update(quarter=int(info["quarter"]), down=int(info["down"]), ytg=int(info["yardsToGo"]))
        title = (f"{info['possessionTeam']} vs {info['defensiveTeam']} · Q{int(info['quarter'])} · "
                 f"{int(info['down'])}&{int(info['yardsToGo'])} · {info['pff_passCoverage']} · spotlight: {route['name']}")
        out.append((p, route, make_play_figure(play, route, title), str(info["playDescription"])))
    return out


def main():
    routes = load_routes()
    log = json.loads((OUT / "run_log.json").read_text())
    man = routes[routes["coverage_type"] == "Man"].copy()
    headline, headline_reason, censor_share = choose_headline(man)
    label = "Mean Gap Over Expected" if headline == "mean_gap_oe" else "Turn Lag Over Expected"
    man["headline"] = man[headline]

    tbl = player_table(man, headline)
    cbs = cb_table(man, headline)
    r_player = float(tbl["headline"].corr(tbl["sep_throw"]))
    r_route_sep = float(man[headline].corr(man["sep_throw"]))
    r_def_ahead = float(man[headline].corr(man["def_ahead"].astype(float)))
    top25 = tbl.head(25)["name"].tolist()
    smoke_hits = [n for n in top25 if any(s in n for s in SMOKE_NAMES)]

    summary = {
        "headline": headline, "headline_label": label, "headline_reason": headline_reason,
        "censored_share_man": round(censor_share, 3), "censored_share_all": round(float(routes["censored"].mean()), 3),
        "routes_scored": int(len(routes)), "routes_man": int(len(man)), "qualified_players": int(len(tbl)),
        "min_routes": MIN_ROUTES,
        "r_player_headline_vs_sep_throw": round(r_player, 3),
        "r_route_headline_vs_sep_throw": round(r_route_sep, 3),
        "validation_r_headline_vs_defender_ahead": round(r_def_ahead, 3),
        "smoke_test_top25_hits": smoke_hits,
        "bucket_baselines_man": {f"{p} / {b}": v for (p, b), v in
                                 man.groupby(["position", "bucket"])[["turn_lag", "mean_gap", "censored"]].mean()
                                 .round(3).assign(n=man.groupby(["position", "bucket"]).size())
                                 .to_dict(orient="index").items()},
        "run_log": log,
        "top10": tbl.head(10)[["name", "position", "team", "routes", "headline", "turn_lag", "censored",
                               "sep_throw", "targets"]].round(2).to_dict(orient="records"),
    }
    tbl.round(3).to_csv(OUT / "leaderboard.csv", index=False)
    cbs.round(3).to_csv(OUT / "cb_leaderboard.csv", index=False)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    picks = pick_heroes(man, tbl, headline)
    heroes = hero_figures(picks, routes)
    write_dashboard(summary, heroes, leaderboard_fig(tbl, label), scatter_fig(tbl, label, r_player), cbs, label)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("bucket_baselines_man", "run_log")}, indent=2, default=str))
    for p, route, _, _ in heroes:
        print(p["why"], "->", route["name"], route["gameId"], route["playId"], round(route["mean_gap_oe"], 1))


def write_dashboard(summary, heroes, lb_fig, sc_fig, cbs, label):
    opts = "".join(f'<option value="{i}">{html.escape(p["why"])} · {html.escape(r["name"])}</option>'
                   for i, (p, r, _, _) in enumerate(heroes))
    panels = []
    for i, (p, r, fig, desc) in enumerate(heroes):
        # Only the visible replay auto-plays, and with the same smooth settings as the
        # Play button. Plotly's on-load default is a full redraw every frame with
        # 0.5 s eased steps, which is what made the first run lag.
        div = pio.to_html(fig, full_html=False, include_plotlyjs=False, div_id=f"play{i}",
                          config={"displayModeBar": False}, auto_play=(i == 0),
                          animation_opts=dict(mode="immediate", frame=dict(duration=int(1000 / FPS), redraw=False),
                                              transition=dict(duration=int(1000 / FPS), easing="linear")))
        ctype = str(r["coverage_type"])
        ctype_html = term(ctype, ctype.lower()) if ctype in ("Man", "Zone") else html.escape(ctype)
        ctx = (f'{term("Q%d" % p["quarter"], "quarter")} · {term("%d&%d" % (p["down"], p["ytg"]), "down_distance")}'
               f' · {coverage_term(r["coverage"])} ({ctype_html}) · {term("spotlight", "spotlight")}: '
               f'{html.escape(r["name"])} vs {term("paired defender", "paired_defender")} '
               f'{html.escape(r["def_name"])} ({position_term(r["def_position"])})')
        panels.append(f'<div class="panel" id="panel{i}" style="display:{"block" if i == 0 else "none"}">'
                      f'<p class="ctx">{ctx}</p><p class="desc">{html.escape(desc)}</p>{div}'
                      f'<div class="insight">{route_insight(r)}</div></div>')
    cb_top = cbs.head(8)
    cb_rows = "".join(f"<tr><td>{html.escape(n)}</td><td>{position_term(p)}</td><td>{rt}</td><td>{h:+.1f}°</td>"
                      f"<td>{s:.2f}</td></tr>"
                      for n, p, rt, h, s in zip(cb_top["def_name"], cb_top["def_position"], cb_top["routes"],
                                                cb_top["headline"], cb_top["sep_throw"]))
    s = summary
    # Hover-definition snippets used in the template below (see src/glossary.py).
    reason = html.escape(s["headline_reason"])
    reason = reason.replace("(censored)", "(" + term("censored", "censored") + ")")
    reason = reason.replace("30% censoring threshold we set in advance",
                            term("30% censoring threshold we set in advance", "censor_threshold"))
    reason = reason.replace("Mean Gap Over Expected, which has no cap", term("Mean Gap Over Expected", "mgoe")
                            + ", which has no cap")
    T = dict(
        routes=term("routes with a detectable break", "routes_scored"),
        man=term("man coverage", "man"),
        qual=term("receivers with ≥%d man routes" % s["min_routes"], "min_routes"),
        cens=term("man routes: defender never turned before the throw", "censored"),
        rdef=term('r with "defender ahead at throw"', "r_def_ahead"),
        rsep=term("r with separation at throw", "r_sep"),
        spot=term("spotlight receiver", "spotlight"),
        o=term("(o)", "o"), dir=term("(dir)", "dir"),
        wedge=term("Wedge", "wedge"), brk=term("BREAK", "slider_break"), readout=term("readout", "readout"),
        label=term(label, "mgoe"), paired=term("paired defender", "paired_defender"),
        bucket=term("break type", "bucket"), lb=term("leaderboard (left)", "leaderboard"),
        sc=term("scatter (right)", "scatter"), flip=term("read from the defense", "flip_side"),
        h_routes=term("Routes", "min_routes"), h_label=term(label, "flip_side"),
        h_sep=term("Separation at throw (yd)", "sep_throw"), shoulders=term("shoulders, not hips", "shoulders"),
        zone=term("zone defenders", "zone"), assoc=term("associated with the route", "association"),
        break_t=term("break", "break"), turned=term("turned", "turned"), r=term("r", "r"),
    )
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Turn Lag: the route-running win that separation stats miss</title>
<script>{get_plotlyjs()}</script>
<style>
body{{background:#0d1b12;color:#eceff1;font-family:Segoe UI,Arial,sans-serif;margin:0;padding:24px 36px;}}
h1{{margin:0;font-size:30px}} h2{{margin-top:36px;border-bottom:1px solid #2e4a36;padding-bottom:6px}}
.sub{{color:#a5d6a7;font-size:17px;margin:6px 0 18px}}
.cards{{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0}}
.card{{background:#13251a;border:1px solid #2e4a36;border-radius:10px;padding:12px 18px;min-width:170px}}
.card b{{display:block;font-size:24px;color:#fff59d}} .card span{{font-size:13px;color:#b0bec5}}
select{{background:#13251a;color:#fff;border:1px solid #4caf50;border-radius:6px;padding:8px;font-size:15px}}
.desc{{color:#b0bec5;font-style:italic}} .insight{{background:#13251a;border-left:4px solid #fdd835;padding:12px 16px;
line-height:1.5;margin:8px 0 0;border-radius:4px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} @media(max-width:1200px){{.grid{{grid-template-columns:1fr}}}}
table{{border-collapse:collapse}} td,th{{padding:5px 12px;border-bottom:1px solid #2e4a36;text-align:left}}
.note{{color:#b0bec5;font-size:14px;line-height:1.5}}
.ctx{{color:#eceff1;font-size:14px;margin:6px 0 0}} .hint{{color:#81c784;font-size:13px;margin:4px 0 0}}
{TIP_CSS}
</style></head><body>
<h1>Turn Lag <span style="color:#a5d6a7">· the route-running win that separation stats miss</span></h1>
<div class="sub">Existing receiver metrics score the outcome — how open he was. Turn Lag scores the mechanism — how long
he left the man covering him turned the wrong way.</div>
<div class="hint">Hover over (or tab to) any dotted-underlined term for what it means and what it tells you.</div>
<div class="cards">
<div class="card"><b>{s['routes_scored']:,}</b><span>{T['routes']}</span></div>
<div class="card"><b>{s['routes_man']:,}</b><span>of them against {T['man']}</span></div>
<div class="card"><b>{s['qualified_players']}</b><span>{T['qual']}</span></div>
<div class="card"><b>{s['censored_share_man']:.0%}</b><span>{T['cens']}</span></div>
<div class="card"><b>{s['validation_r_headline_vs_defender_ahead']:+.2f}</b><span>{T['rdef']} (near 0 = not just good coverage)</span></div>
<div class="card"><b>{s['r_player_headline_vs_sep_throw']:+.2f}</b><span>{T['rsep']} (player level)</span></div>
</div>

<h2>Replay</h2>
<div class="note legend">
<div><span style="color:#ffffff">● white</span> = offense (team-color ring) &nbsp;·&nbsp; <span style="color:#9e9e9e">● black</span> = defense
&nbsp;·&nbsp; <span style="color:#ff9800">◆ orange</span> = ball
&nbsp;·&nbsp; <span style="color:#fdd835">◯ yellow ring</span> = {T['spot']}</div>
<div><span style="color:#ffee58">▲ yellow arrow</span> = where a coverage defender's shoulders face {T['o']} &nbsp;·&nbsp;
<span style="color:#4dd0e1">▲ cyan arrow</span> = where a receiver is moving {T['dir']}</div>
<div>{T['wedge']}: <span style="color:#ef9a9a">red</span> = {T['paired']} facing ≥45° off the receiver's path &nbsp;·&nbsp;
<span style="color:#a5d6a7">green</span> = he has {T['turned']} &nbsp;·&nbsp; <span style="color:#bdbdbd">grey</span> = before the {T['break_t']}</div>
<div>The slider marks the {T['brk']}. The {T['readout']} above the field updates live. Use 0.25× slow-mo to watch the shoulders.</div>
</div>
<p><select onchange="show(this.value)">{opts}</select></p>
{''.join(panels)}

<h2>Who turns defenders around</h2>
<p class="note">{reason} {T['label']} = the receiver's average angle between his {T['paired']}'s
shoulders and his own path from the break to the throw, minus the average for the same receiver position, defender type
(defensive back or linebacker) and {T['bucket']} (slight / sideways / back toward line / diagonal downfield) against
{T['man']}.</p>
<p class="note">Reading the charts: {T['lb']} &nbsp;·&nbsp; {T['sc']}. Hover a bar or dot for the player's numbers.</p>
<div class="grid"><div id="lb"></div><div id="sc"></div></div>

<h2>Flip side: stickiest man defenders</h2>
<p class="note">The same data {T['flip']}: the lowest {T['label']} against them (min {s['min_routes']} routes as the {T['paired']}).</p>
<table><tr><th>Defender</th><th>Pos</th><th>{T['h_routes']}</th><th>{T['h_label']}</th><th>{T['h_sep']}</th></tr>{cb_rows}</table>

<h2>How to read it, and its limits</h2>
<p class="note">Orientation {T['o']} comes from shoulder-pad sensors, so this measures {T['shoulders']}. The {T['paired']} is
the closest cornerback, safety or linebacker in coverage over the first second after the snap, a heuristic, since the
data has no coverage assignments. Linemen dropping into coverage are never paired, and routes where the paired defender
is more than 5 yd away at the break are excluded because he was not on the receiver. Even on man-coverage plays some
linebackers drop into zones, so linebacker pairings are compared only with other linebacker pairings. Headline numbers use {T['man']} only, because {T['zone']} are taught to face the quarterback and are
not trying to mirror a receiver. Tracking stops just after the throw, so everything is measured snap to release.
A defender still turned after a break is {T['assoc']}; it does not prove the route caused it.
Thresholds: {T['break_t']} = largest 0.5 s direction change ≥30° with peak speed &gt;2 yd/s; {T['turned']} = within 45°.
Correlations are reported as {T['r']}.</p>
<script>
const lb={pio.to_json(lb_fig)}; const sc={pio.to_json(sc_fig)};
Plotly.newPlot('lb', lb.data, lb.layout, {{displayModeBar:false}});
Plotly.newPlot('sc', sc.data, sc.layout, {{displayModeBar:false}});
function show(i){{document.querySelectorAll('.panel').forEach((p,j)=>p.style.display=(j==i)?'block':'none');
Plotly.Plots.resize(document.getElementById('play'+i));}}
{TIP_JS}
</script></body></html>"""
    (OUT / "dashboard.html").write_text(page, encoding="utf-8")
    # Published copy for GitHub Pages (Settings -> Pages -> serve from /docs).
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "index.html").write_text(page, encoding="utf-8")
    (docs / ".nojekyll").touch()  # serve the file as is, skip the Jekyll build


if __name__ == "__main__":
    main()
