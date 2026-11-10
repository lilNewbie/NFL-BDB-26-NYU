"""Score every route in every game. Writes out/routes.csv and out/run_log.json.

Usage: python -m src.run_all [max_games]
"""
from __future__ import annotations

import json
import sys
import time
from multiprocessing import Pool

import pandas as pd

from .data import ROOT, list_game_ids, prepare_game
from .metric import compute_play


def score_game(game_id: int):
    log: dict = {}
    try:
        df = prepare_game(game_id, log)
        rows = []
        for _, play in df.groupby("playId"):
            rows.extend(compute_play(play, log))
        return rows, log, None
    except Exception as exc:  # keep the batch alive; report the failure
        return [], log, f"{game_id}: {exc!r}"


def main(max_games: int | None = None):
    t0 = time.time()
    games = list_game_ids()[:max_games] if max_games else list_game_ids()
    rows, total, errors = [], {}, []
    with Pool() as pool:
        for i, (r, log, err) in enumerate(pool.imap_unordered(score_game, games), 1):
            rows.extend(r)
            for k, v in log.items():
                total[k] = total.get(k, 0) + v
            if err:
                errors.append(err)
            if i % 10 == 0:
                print(f"{i}/{len(games)} games, {len(rows)} routes, {time.time() - t0:.0f}s", flush=True)
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "routes.csv", index=False)
    total["games"] = len(games)
    total["errors"] = errors
    (out / "run_log.json").write_text(json.dumps(total, indent=2))
    print(json.dumps(total, indent=2))
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
