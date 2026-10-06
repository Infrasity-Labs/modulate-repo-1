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
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    PLOTS.mkdir(parents=True, exist_ok=True)
    datasets = [d for d in [*ALL_DATASETS, "overall"] if any(s["dataset"] == d for s in summaries)]
    engines = list(dict.fromkeys(s["engine"] for s in summaries))

    dataset_display = {
        "librispeech": "LibriSpeech",
        "voxpopuli": "VoxPopuli",
        "commonvoice": "Common Voice",
        "overall": "Overall",
    }
    engine_display = {
        "velma": "Velma (Fast)",
        "deepgram": "Deepgram (nova-3)",
        "assemblyai": "AssemblyAI (3.5 Pro)",
    }
    engine_palette = {
        "velma": "#4F46E5",       # Vibrant Indigo
        "deepgram": "#0EA5E9",    # Sky Blue
        "assemblyai": "#F43F5E",  # Rose Red
        "slot_a": "#10B981",      # Emerald
        "slot_b": "#F59E0B",      # Amber
    }

    def render_chart(key, ylabel, fname, title, subtitle, unit="", is_currency=False):
        fig, ax = plt.subplots(figsize=(9, 4.8), dpi=200)
        fig.patch.set_facecolor("#FAFAFB")
        ax.set_facecolor("#FFFFFF")

        n = len(engines)
        x = np.arange(len(datasets))
        total_width = 0.72
        width = total_width / n

        max_val = 0
        for i, e in enumerate(engines):
            vals = []
            for d in datasets:
                s = next((row for row in summaries if row["engine"] == e and row["dataset"] == d), None)
                vals.append(s[key] if s and s.get(key) is not None else 0)
            max_val = max(max_val, max(vals) if vals else 0)

            offset = (i - (n - 1) / 2) * width
            color = engine_palette.get(e, f"C{i}")
            label = engine_display.get(e, e)
            rects = ax.bar(x + offset, vals, width * 0.88, label=label,
                           color=color, alpha=0.92, edgecolor="none", zorder=3)

            for rect, val in zip(rects, vals):
                if val > 0:
                    h = rect.get_height()
                    if is_currency:
                        txt = f"${val:.3f}"
                    elif unit == "%":
                        txt = f"{val:g}%"
                    else:
                        txt = f"{val:.2f}{unit}"
                    ax.annotate(
                        txt,
                        xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 4),
                        textcoords="offset points",
                        ha="center", va="bottom",
                        fontsize=8.5, fontweight="bold",
                        color="#334155"
                    )

        ax.set_title(title, fontsize=13, fontweight="bold", color="#0F172A", pad=22, loc="left")
        ax.text(0.0, 1.025, subtitle, transform=ax.transAxes, fontsize=9, color="#64748B", va="bottom")

        ax.set_xticks(x)
        ax.set_xticklabels([dataset_display.get(d, d) for d in datasets], fontsize=9.5, fontweight="600", color="#334155")
        ax.set_ylabel(ylabel, fontsize=9.5, fontweight="600", color="#475569", labelpad=8)

        ax.set_ylim(0, max(max_val * 1.28, 0.1))
        ax.tick_params(colors="#64748B", which="both", labelsize=8.5)
        ax.grid(axis="y", linestyle="--", alpha=0.5, color="#E2E8F0", zorder=0)
        ax.grid(axis="x", visible=False)

        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color("#CBD5E1")
            ax.spines[spine].set_linewidth(1)

        ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0",
                  fontsize=9, loc="upper right", framealpha=0.95)

        fig.tight_layout()
        fig.savefig(PLOTS / fname, dpi=200, bbox_inches="tight")
        plt.close(fig)

    render_chart("wer_percent", "Word Error Rate (%)", "wer.png",
                 "Word Error Rate (WER) by Dataset",
                 "Lower is better · % of word errors across benchmark test slices", unit="%")
    render_chart("mean_latency_s", "Mean Latency (s)", "latency.png",
                 "Latency per File Comparison",
                 "Lower is faster · Request duration including network transfer and inference", unit="s")
    render_chart("price_per_hour_usd", "USD per Audio Hour ($)", "cost_per_hour.png",
                 "Pricing Comparison: USD per Audio Hour",
                 "Lower is cheaper · Published vendor pre-recorded (batch) API rates", is_currency=True)


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
