"""Download a small slice of each dataset and write a manifest (audio stays out of Git).

Usage: python download_datasets.py --dataset librispeech --num-files 20
"""
import argparse
import json
import os
import sys
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).parent / "datasets"
AUDIO = ROOT / "audio"
MANIFESTS = ROOT / "manifests"

# name -> (hf repo, config, split, text column, extra kwargs)
SOURCES = {
    "librispeech": ("openslr/librispeech_asr", "clean", "test", "text", {}),
    "voxpopuli": ("facebook/voxpopuli", "en", "test", "normalized_text", {}),
    "commonvoice": ("fixie-ai/common_voice_17_0", "en", "test", "sentence", {}),
}


def download(name: str, num_files: int) -> Path:
    from datasets import Audio, load_dataset

    repo, config, split, text_col, kw = SOURCES[name]
    ds = load_dataset(repo, config, split=split, streaming=True, **kw)
    ds = ds.cast_column("audio", Audio(decode=False))
    out_dir = AUDIO / name
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for i, ex in enumerate(ds):
        if len(entries) >= num_files:
            break
        ref = (ex.get(text_col) or "").strip()
        if not ref:
            continue
        a = ex["audio"]
        raw = a.get("bytes")
        if raw is None:
            continue
        ext = Path(a.get("path") or "x.flac").suffix or ".flac"
        path = out_dir / f"{name}_{len(entries):03d}{ext}"
        path.write_bytes(raw)
        info = sf.info(str(path))
        entries.append({
            "id": ex.get("id") or path.stem,
            "file": str(path.relative_to(ROOT)),
            "reference": ref,
            "duration_s": round(info.duration, 3),
        })
    MANIFESTS.mkdir(exist_ok=True)
    manifest = MANIFESTS / f"{name}.json"
    manifest.write_text(json.dumps(
        {"dataset": name, "source": f"{repo}/{config}/{split}", "files": entries}, indent=2))
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", choices=[*SOURCES, "all"], default="all")
    p.add_argument("--num-files", type=int, default=20)
    args = p.parse_args()
    names = list(SOURCES) if args.dataset == "all" else [args.dataset]
    failed = []
    for n in names:
        try:
            m = download(n, args.num_files)
            print(f"[ok] {n}: manifest {m}")
        except Exception as e:
            failed.append(n)
            print(f"[skipped] {n}: {type(e).__name__}: {str(e)[:300]}", file=sys.stderr)
    if failed and args.dataset == "all":
        print(f"Skipped: {failed}", file=sys.stderr)
    # HF streaming leaves background threads that can block interpreter exit
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
