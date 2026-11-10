# NFL Big Data Bowl — NYU Edition: Project Spec for Kiro

## Context
3-hour on-site hackathon. Build ONE data tool/visualization using 2021 NFL Next Gen Stats
tracking data (Weeks 1-8) that surfaces an original insight about skill-position players
(WR / TE / RB). Everything must be built during the event window — no pre-built code.

## Chosen Concept: "Space Created" Animated Replay
An animated field replay of a single pass play (or a short highlight reel of 3-5 plays)
showing all 22 players + ball moving frame-by-frame, with a live "separation bubble"
around the targeted receiver that grows/shrinks as they create or lose space from the
nearest defender. A running separation metric is displayed as an on-screen readout.

This single deliverable satisfies both allowed submission formats at once:
- **Visualization**: the animated replay itself
- **Metric**: the separation score computed and displayed live, plus leaderboard aggregation

## Audience
Primary: scout / coach ("which WRs/TEs/RBs consistently create separation, and on which
route types / coverages"). Secondary: broadcaster (the animation itself is TV-ready).

---

## Data Files (confirm exact paths once on-site)
| File | Purpose |
|---|---|
| `tracking/tracking_[gameId].csv` | Per-frame x/y/s/a/o/dir for all players + ball, per game |
| `games.csv` | game metadata (season, week, teams) |
| `plays.csv` | play metadata: down, distance, formation, coverage, passResult |
| `players.csv` | player name, position (filter to WR/TE/RB) |
| `pffScoutingData.csv` | per-player-per-play role (`pff_role`), matchup, outcome labels |

Key join fields: `gameId`, `playId`, `nflId`.

### Known schema details
- `x`, `y`: field position in yards. x: 0-120 (length), y: 0-53.3 (width)
- `s`: speed (yd/s), `a`: acceleration (yd/s²), `dis`: distance since last frame
- `o`: body orientation (deg), `dir`: direction of motion (deg)
- `event`: tagged frame moments (`ball_snap`, `pass_forward`, `pass_arrived`,
  `pass_outcome_caught`, `tackle`, etc.)
- Ball rows: `nflId` is blank, `team == "football"`
- `playDirection`: `'left'` or `'right'` — **must normalize** so all plays face the same way
  before doing anything spatial (flip x and/or y accordingly)
- Pass-block window = `ball_snap` → first of `{pass_forward, qb_sack, qb_strip_sack, run}`
- `passResult`: C=complete, I=incomplete, S=sack, R=scramble, IN=interception
- `pff_role` values include: Pass Route, Coverage, Pass Block, Pass Rush

---

## Build Plan (time-boxed)

### Phase 0 — Setup (15 min)
- [ ] Load `games.csv`, `plays.csv`, `players.csv`, `pffScoutingData.csv`
- [ ] Load ONE game's tracking file to inspect real column names/values (confirm against
      schema above — adjust naming if it differs)
- [ ] Filter `players.csv` to position in `{WR, TE, RB}`
- [ ] Write a `normalize_play_direction(df)` helper: if `playDirection == 'left'`, flip
      `x -> 120 - x` and `dir/o -> (180 + dir) % 360` etc., so every play runs left-to-right

### Phase 1 — Play selection (15 min)
- [ ] Filter `plays.csv` to passing plays with `passResult == 'C'` (complete passes — cleanest
      target-receiver signal)
- [ ] Join to `pffScoutingData.csv` to find the receiver with `pff_role == 'Pass Route'` who
      was the target (if a target flag exists, use it directly — check column names on-site)
- [ ] Pick 1 play to prototype on; later pick 3-5 "best separation swing" plays for the final
      highlight reel (sort by max separation range during the route)

### Phase 2 — Separation metric (30 min)
For the chosen play's targeted receiver, at every frame from `ball_snap` to `pass_arrived`:
- [ ] Compute Euclidean distance from receiver (x,y) to every defender (x,y) in that frame
      (defenders = players on the opposite team from the receiver, from `plays.csv`/`games.csv`
      team fields)
- [ ] `separation(frame) = min(distance to any defender)`
- [ ] Store a per-frame series: `frameId, separation`
- [ ] Headline number: `separation_at_catch = separation(frame of pass_arrived event)`

### Phase 3 — Animation (60-75 min)
- [ ] Draw static field background: rectangle, yard lines every 10 yards, endzones shaded
- [ ] `matplotlib.animation.FuncAnimation` (or `plotly.graph_objects.Figure(frames=...)` if time
      allows for an interactive slider instead of a fixed video):
  - All 22 players as dots, color by team (offense vs defense), ball as a small marker
  - Highlight the targeted receiver distinctly (different marker/color)
  - Draw a circle centered on the receiver with radius = current `separation` value
  - Color the circle green (open, large separation) → red (covered, small separation) using
    a colormap keyed to separation magnitude
  - On-screen text: live separation number, down/distance, play description
- [ ] Export as GIF (`PillowWriter`) or interactive Plotly HTML — Plotly HTML is easier to
      demo/judge without a video codec dependency

### Phase 4 — Aggregation / leaderboard (30 min, if time allows)
- [ ] Loop the Phase 2 metric across many plays (as many games as time allows) for all
      WR/TE/RB
- [ ] Aggregate: `avg_separation_at_catch` per player (min N targets to qualify, e.g. 5+)
- [ ] Bar chart: top 10 separation leaders — this is the "quantified insight a scout would
      care about" backing the animation

### Phase 5 — README + packaging (20 min)
- [ ] Write README (3-5 sentences): what was built, what insight it reveals, who'd use it
- [ ] Make sure repo is public, includes code + output (GIF/HTML + leaderboard chart)
- [ ] Submit via the event form before 2:00 PM sharp

---

## Nice-to-haves (only if ahead of schedule)
- Lightweight Voronoi/pitch-control shading layered on the same animation
  (`scipy.spatial.Voronoi` per frame) for an originality boost
- "Ghost route" overlay comparing this route to the player's average route shape

## Explicit non-goals (don't scope-creep into these)
- No training/predictive ML model (not needed for this concept — pure analytics + viz)
- No multi-game live dashboard — one polished replay + one leaderboard chart is enough
- No defensive-player-centric analysis — must stay framed around WR/TE/RB per the brief

## Acceptance checklist (matches judging rubric)
- [ ] Runs end-to-end without errors from a clean environment
- [ ] Insight is specific and stated plainly (not just "here's a cool animation")
- [ ] README explains value to a named audience (coach/scout/broadcaster)
- [ ] Visualization is readable at a glance (clear colors/labels, not cluttered)
- [ ] Something non-obvious beyond a stock Big Data Bowl notebook (the live separation bubble
      + leaderboard combo is the differentiator — emphasize this in the README)
