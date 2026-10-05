#!/usr/bin/env python
"""Speech-to-text benchmark CLI.

  python benchmark.py --engine velma --dataset librispeech --num-files 20
  python benchmark.py --report          # rebuild table and plots from results/
"""
import argparse
import csv
import json
import statistics
import sys
from datetime import date
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
PLACEHOLDER_ENGINES = ["deepgram", "assemblyai", "slot_a", "slot_b"]
FIELDS = ["engine", "model", "dataset", "files", "audio_hours", "wer_percent",
          "mean_latency_s", "median_latency_s", "price_per_hour_usd", "tested_on"]


def run(engine_name, dataset, num_files, model):
    manifest = json.loads((DATASETS / "manifests" / f"{dataset}.json").read_text())
    files = manifest["files"][:num_files]
    kwargs = {"model": model} if model else {}
    engine = ENGINES[engine_name](**kwargs)
    rows, refs, hyps, lats = [], [], [], []
    for i, e in enumerate(files, 1):
        try:
            t = engine.transcribe(str(DATASETS / e["file"]))
        except RuntimeError as err:
            print(f"  [{i}/{len(files)}] FAILED {e['id']}: {err}", file=sys.stderr)
            rows.append({"id": e["id"], "reference": e["reference"], "hypothesis": None,
                         "duration_s": e["duration_s"], "error": str(err)})
            continue
        refs.append(e["reference"]); hyps.append(t.text); lats.append(t.latency_s)
        rows.append({"id": e["id"], "reference": e["reference"], "hypothesis": t.text,
                     "latency_s": round(t.latency_s, 3), "duration_s": e["duration_s"],
                     "empty": not normalize(t.text)})
        print(f"  [{i}/{len(files)}] {e['id']} {t.latency_s:.2f}s")
    if not lats:
        sys.exit("no successful transcriptions")
    scored = [r for r in rows if r.get("hypothesis") is not None]
    summary = {
        "engine": engine_name,
        "model": getattr(engine, "model", ""),
        "dataset": dataset,
        "files": len(scored),
        "files_failed": len(rows) - len(scored),
        "audio_hours": round(sum(r["duration_s"] for r in scored) / 3600, 4),
        "wer_percent": round(100 * compute_wer(refs, hyps), 2),
        "mean_latency_s": round(statistics.mean(lats), 2),
        "median_latency_s": round(statistics.median(lats), 2),
        "price_per_hour_usd": engine.price_per_hour,
        "tested_on": date.today().isoformat(),
    }
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{engine_name}_{dataset}.json"
    out.write_text(json.dumps({"summary": summary, "files": rows}, indent=2))
    print(json.dumps(summary, indent=2))
    return summary


def report():
    summaries = [json.loads(p.read_text())["summary"] for p in sorted(RESULTS.glob("*_*.json"))]
    if not summaries:
        sys.exit("no results found in results/")
    order = {n: i for i, n in enumerate(ENGINES)}
    summaries.sort(key=lambda s: (order.get(s["engine"], 99), s["dataset"]))
    with open(RESULTS / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(summaries)

    def cell(v):
        return "" if v is None else str(v)

    lines = ["| Engine | Model | Dataset | Files | WER % | Mean latency (s) | Median latency (s) | USD per audio hour | Tested on |",
             "|---|---|---|---|---|---|---|---|---|"]
    for s in summaries:
        lines.append("| " + " | ".join(cell(s[k]) for k in [
            "engine", "model", "dataset", "files", "wer_percent", "mean_latency_s",
            "median_latency_s", "price_per_hour_usd", "tested_on"]) + " |")
    done = {s["engine"] for s in summaries}
    for n in PLACEHOLDER_ENGINES:
        if n not in done:
            lines.append(f"| {n} | | | | not run | | | | |")
    (RESULTS / "results.md").write_text("\n".join(lines) + "\n")
    plot(summaries)
    print("\n".join(lines))


def plot(summaries):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    PLOTS.mkdir(parents=True, exist_ok=True)
    datasets = sorted({s["dataset"] for s in summaries})
    engines = list(dict.fromkeys(s["engine"] for s in summaries))

    def bars(key, ylabel, fname, title):
        fig, ax = plt.subplots(figsize=(7, 4))
        width = 0.8 / len(engines)
        for i, e in enumerate(engines):
            vals = [next((s[key] for s in summaries if s["engine"] == e and s["dataset"] == d), None)
                    for d in datasets]
            xs = [j + i * width for j in range(len(datasets))]
            ax.bar([x for x, v in zip(xs, vals) if v is not None],
                   [v for v in vals if v is not None], width, label=e)
        ax.set_xticks([j + width * (len(engines) - 1) / 2 for j in range(len(datasets))])
        ax.set_xticklabels(datasets)
        ax.set_ylabel(ylabel); ax.set_title(title); ax.legend()
        fig.tight_layout(); fig.savefig(PLOTS / fname, dpi=150); plt.close(fig)

    bars("wer_percent", "WER (%), lower is better", "wer.png", "Word error rate")
    bars("median_latency_s", "Median latency (s)", "latency.png", "Latency per file")
    bars("price_per_hour_usd", "USD per hour of audio", "cost_per_hour.png", "Cost per audio hour (published price)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--engine", choices=list(ENGINES))
    p.add_argument("--dataset", choices=["librispeech", "voxpopuli", "commonvoice"])
    p.add_argument("--num-files", type=int, default=20)
    p.add_argument("--model", help="engine model variant (velma: english-fast, multilingual, multilingual-fast)")
    p.add_argument("--report", action="store_true", help="rebuild CSV, markdown and plots from results/")
    a = p.parse_args()
    load_dotenv(ROOT / ".env")
    if a.report:
        return report()
    if not (a.engine and a.dataset):
        p.error("--engine and --dataset are required unless --report is used")
    if not (DATASETS / "manifests" / f"{a.dataset}.json").exists():
        sys.exit(f"No manifest for {a.dataset}. Run: python download_datasets.py --dataset {a.dataset}")
    try:
        run(a.engine, a.dataset, a.num_files, a.model)
    except EngineNotConfigured as e:
        sys.exit(str(e))
    report()


if __name__ == "__main__":
    main()
