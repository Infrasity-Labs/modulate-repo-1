#!/usr/bin/env python
"""Speech-to-text benchmark CLI.

  python benchmark.py --engine velma deepgram assemblyai --dataset all --num-files 20 --repeats 3
  python benchmark.py --report          # rebuild table and plots from results/

All engines run in one session on the same files, interleaved file by file. Each call is
repeated --repeats times and latency is averaged per file. If any engine fails on a file
(after retries), that file is excluded for every engine and the exclusion is reported.
"""
import argparse
import csv
import json
import platform
import statistics
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from engines import ENGINES
from engines.base import EngineNotConfigured
from scoring.normalize import normalize
from scoring.wer import compute_wer

ROOT = Path(__file__).parent
DATASETS = ROOT / "datasets"
RESULTS = ROOT / "results"
PLOTS = RESULTS / "plots"
CACHE = RESULTS / "call_cache.jsonl"  # per-call cache so an interrupted run can resume
ALL_DATASETS = ["librispeech", "voxpopuli", "commonvoice"]
PLACEHOLDER_ENGINES = ["slot_a", "slot_b"]
FIELDS = ["engine", "model", "dataset", "files", "files_excluded", "audio_hours", "wer_percent",
          "mean_latency_s", "median_latency_s", "price_per_hour_usd", "tested_on"]


def load_cache():
    cache = {}
    if CACHE.exists():
        for line in CACHE.read_text().splitlines():
            r = json.loads(line)
            cache[(r["engine"], r["dataset"], r["id"], r["repeat"])] = r
    return cache


def call(engine, name, dataset, entry, repeat, cache):
    key = (name, dataset, entry["id"], repeat)
    if key in cache:
        return cache[key]
    rec = {"engine": name, "dataset": dataset, "id": entry["id"], "repeat": repeat}
    try:
        t = engine.transcribe(str(DATASETS / entry["file"]))
        rec.update(text=t.text, latency_s=round(t.latency_s, 3), error=None)
    except RuntimeError as err:
        rec.update(text=None, latency_s=None, error=str(err)[:300])
    with open(CACHE, "a") as f:
        f.write(json.dumps(rec) + "\n")
    cache[key] = rec
    return rec


def run_session(engine_names, datasets, num_files, repeats, models):
    RESULTS.mkdir(exist_ok=True)
    engines = {n: ENGINES[n](**({"model": models[n]} if n in models else {})) for n in engine_names}
    cache = load_cache()
    prev = RESULTS / "session.json"  # resumed runs keep the original start time
    started = json.loads(prev.read_text())["started"] if prev.exists() else None
    session = {"started": started or datetime.now().isoformat(timespec="seconds"), "machine": platform.platform(),
               "python": platform.python_version(), "repeats": repeats, "models": {}, "excluded": {}}
    for n, e in engines.items():
        session["models"][n] = {"model": getattr(e, "model", ""), "price_per_hour_usd": e.price_per_hour}
    per = {}  # (engine, dataset) -> rows
    for ds in datasets:
        files = json.loads((DATASETS / "manifests" / f"{ds}.json").read_text())["files"][:num_files]
        recs = {n: {} for n in engines}
        excluded = []
        for i, e in enumerate(files, 1):
            ok = True
            for n, eng in engines.items():  # interleave engines per file
                runs = [call(eng, n, ds, e, r, cache) for r in range(repeats)]
                recs[n][e["id"]] = runs
                if any(r["error"] for r in runs):
                    ok = False
                    print(f"  FAILED {n} {ds} {e['id']}: {[r['error'] for r in runs if r['error']][0]}", file=sys.stderr)
            if not ok:
                excluded.append(e["id"])
            print(f"[{ds} {i}/{len(files)}] " + " ".join(
                f"{n}={statistics.mean([r['latency_s'] for r in recs[n][e['id']] if r['latency_s']] or [0]):.1f}s"
                for n in engines), flush=True)
        session["excluded"][ds] = excluded
        for n in engines:
            rows = []
            for e in files:
                runs = recs[n][e["id"]]
                good = [r for r in runs if not r["error"]]
                rows.append({
                    "id": e["id"], "reference": e["reference"], "duration_s": e["duration_s"],
                    "excluded": e["id"] in excluded,
                    "hypothesis": good[0]["text"] if good else None,
                    "latencies_s": [r["latency_s"] for r in good],
                    "mean_latency_s": round(statistics.mean(r["latency_s"] for r in good), 3) if good else None,
                    "empty": bool(good) and not normalize(good[0]["text"]),
                })
            per[(n, ds)] = rows
    summaries = []
    for n in engines:
        for ds in [*datasets, "overall"]:
            rows = [r for d in (datasets if ds == "overall" else [ds]) for r in per[(n, d)] if not r["excluded"]]
            n_excl = sum(len(session["excluded"][d]) for d in (datasets if ds == "overall" else [ds]))
            if not rows:
                continue
            lats = [r["mean_latency_s"] for r in rows]
            summaries.append({
                "engine": n, "model": session["models"][n]["model"], "dataset": ds,
                "files": len(rows), "files_excluded": n_excl,
                "audio_hours": round(sum(r["duration_s"] for r in rows) / 3600, 4),
                "wer_percent": round(100 * compute_wer([r["reference"] for r in rows],
                                                       [r["hypothesis"] for r in rows]), 2),
                "mean_latency_s": round(statistics.mean(lats), 2),
                "median_latency_s": round(statistics.median(lats), 2),
                "price_per_hour_usd": session["models"][n]["price_per_hour_usd"],
                "tested_on": date.today().isoformat(),
            })
    for ds in datasets:
        for n in engines:
            (RESULTS / f"{n}_{ds}.json").write_text(json.dumps({
                "summary": next(s for s in summaries if s["engine"] == n and s["dataset"] == ds),
                "files": per[(n, ds)]}, indent=2))
    session["finished"] = datetime.now().isoformat(timespec="seconds")
    (RESULTS / "session.json").write_text(json.dumps({**session, "summaries": summaries}, indent=2))
    return summaries


def report():
    summaries = json.loads((RESULTS / "session.json").read_text())["summaries"]
    order = {n: i for i, n in enumerate(ENGINES)}
    dorder = {d: i for i, d in enumerate([*ALL_DATASETS, "overall"])}
    summaries.sort(key=lambda s: (dorder.get(s["dataset"], 99), order.get(s["engine"], 99)))
    with open(RESULTS / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(summaries)
    cell = lambda v: "" if v is None else str(v)
    lines = ["| Dataset | Engine | Model | Files | Excluded | WER % | Mean latency (s) | Median latency (s) | USD per audio hour |",
             "|---|---|---|---|---|---|---|---|---|"]
    for s in summaries:
        lines.append("| " + " | ".join(cell(s[k]) for k in [
            "dataset", "engine", "model", "files", "files_excluded", "wer_percent",
            "mean_latency_s", "median_latency_s", "price_per_hour_usd"]) + " |")
    (RESULTS / "results.md").write_text("\n".join(lines) + "\n")
    plot(summaries)
    print("\n".join(lines))


def plot(summaries):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    PLOTS.mkdir(parents=True, exist_ok=True)
    datasets = [d for d in [*ALL_DATASETS, "overall"] if any(s["dataset"] == d for s in summaries)]
    engines = list(dict.fromkeys(s["engine"] for s in summaries))

    def bars(key, ylabel, fname, title):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        width = 0.8 / len(engines)
        for i, e in enumerate(engines):
            for j, d in enumerate(datasets):
                v = next((s[key] for s in summaries if s["engine"] == e and s["dataset"] == d), None)
                if v is not None:
                    b = ax.bar(j + i * width, v, width, color=f"C{i}", label=e if j == 0 else None)
                    ax.annotate(f"{v:g}", (j + i * width, v), ha="center", va="bottom", fontsize=7)
        ax.set_xticks([j + width * (len(engines) - 1) / 2 for j in range(len(datasets))])
        ax.set_xticklabels(datasets)
        ax.set_ylabel(ylabel); ax.set_title(title); ax.legend()
        fig.tight_layout(); fig.savefig(PLOTS / fname, dpi=150); plt.close(fig)

    bars("wer_percent", "WER (%), lower is lower error", "wer.png", "Word error rate")
    bars("mean_latency_s", "Mean latency per file (s)", "latency.png", "Latency per file (mean of 3 repeats)")
    bars("price_per_hour_usd", "USD per hour of audio", "cost_per_hour.png", "Published price per audio hour")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--engine", nargs="+", choices=list(ENGINES), help="one or more engines")
    p.add_argument("--dataset", nargs="+", default=["all"], help="librispeech voxpopuli commonvoice, or all")
    p.add_argument("--num-files", type=int, default=20)
    p.add_argument("--repeats", type=int, default=3, help="calls per file, latency is averaged")
    p.add_argument("--model", action="append", default=[], metavar="ENGINE=MODEL",
                   help="override an engine's model, e.g. velma=multilingual")
    p.add_argument("--report", action="store_true", help="rebuild CSV, markdown and plots from results/session.json")
    a = p.parse_args()
    load_dotenv(ROOT / ".env")
    if a.report:
        return report()
    if not a.engine:
        p.error("--engine is required unless --report is used")
    datasets = ALL_DATASETS if a.dataset == ["all"] else a.dataset
    for d in datasets:
        if not (DATASETS / "manifests" / f"{d}.json").exists():
            sys.exit(f"No manifest for {d}. Run: python download_datasets.py --dataset {d}")
    models = dict(m.split("=", 1) for m in a.model)
    try:
        run_session(a.engine, datasets, a.num_files, a.repeats, models)
    except EngineNotConfigured as e:
        sys.exit(str(e))
    report()


if __name__ == "__main__":
    main()
