# velma-stt-benchmark

A speech-to-text benchmark CLI for Modulate's Velma Transcribe API. One CLI, one file per engine, shared scoring, results checked into the repo.

> **Status: Velma only.** No other engine has been run yet. The table below is not a comparison. Deepgram, AssemblyAI and two generic slots are empty placeholders until their keys are added.

## Results (Velma English Fast, batch)

Tested on 2026-10-05 from a local macOS machine, over the public internet, one file at a time, 20 files per dataset. Test location (city/region): _to be filled in by the person running the final numbers_.

| Engine | Model | Dataset | Files | WER % | Mean latency (s) | Median latency (s) | USD per audio hour | Tested on |
|---|---|---|---|---|---|---|---|---|
| velma | english-fast | librispeech | 20 | 0.91 | 4.41 | 3.63 | 0.025 | 2026-10-05 |
| velma | english-fast | voxpopuli | 20 | 4.77 | 5.41 | 4.58 | 0.025 | 2026-10-05 |
| velma | english-fast | commonvoice | 20 | 9.2 | 4.69 | 3.93 | 0.025 | 2026-10-05 |
| deepgram | | | | not run | | | | |
| assemblyai | | | | not run | | | | |
| slot_a | | | | not run | | | | |
| slot_b | | | | not run | | | | |

Generated files: `results/results.csv`, `results/results.md`, `results/wer.png`, `results/latency.png`, `results/cost_per_hour.png`. Per-file transcripts are in `results/<engine>_<dataset>.json`.

Notes on the numbers:
- Samples are small (20 files, 108 to 184 seconds of audio per dataset). One bad file moves CommonVoice WER noticeably.
- Latency is wall-clock time for one upload plus transcription call and includes network time. It is not a streaming latency.
- Price is Modulate's published batch price per hour of audio (https://www.modulate.ai/api-pricing): English Fast $0.025, Multilingual $0.03, Multilingual Fast $0.03.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then put your key in VELMA_API_KEY
```

The key is read from the environment only. `.env` is git-ignored.

## Run

```bash
python download_datasets.py --dataset all --num-files 20      # writes audio (git-ignored) and manifests
python benchmark.py --engine velma --dataset librispeech --num-files 20
python benchmark.py --engine velma --dataset voxpopuli --num-files 20
python benchmark.py --engine velma --dataset commonvoice --num-files 20
python benchmark.py --report                                   # rebuild table and plots
python -m pytest                                               # scoring unit tests, no API needed
```

Use `--model multilingual` or `--model multilingual-fast` to pick another Velma model (default `english-fast`).

## Layout

```
benchmark.py            single CLI entry point
download_datasets.py    downloads slices, writes manifests
engines/                base.py plus one file per engine
scoring/                normalize.py and wer.py, shared by every engine
datasets/manifests/     list of files used (audio is not committed)
results/                CSV, markdown, plots, per-file transcripts
tests/                  unit tests with fake text
```

## Datasets

| Dataset | Source | Slice |
|---|---|---|
| LibriSpeech | `openslr/librispeech_asr`, config `clean`, split `test` | first 20 files |
| VoxPopuli | `facebook/voxpopuli`, `en`, split `test` | first 20 files |
| CommonVoice | `fixie-ai/common_voice_17_0`, `en`, split `test` (a parquet mirror of Mozilla Common Voice 17) | first 20 files |

Audio is stored under `datasets/audio/` and is not committed. The manifests in `datasets/manifests/` record the exact files, references and durations used.

## Text normalisation

Every engine's output and every reference goes through `scoring/normalize.py` before WER. The rules, in order:

1. Unicode NFKC, then lowercase.
2. Curly apostrophes become straight apostrophes.
3. Bracketed or angle-bracket markers such as `[laughter]` are removed.
4. `%` becomes "percent" and `&` becomes "and".
5. Digits become words with `num2words` (`3` to "three", `2nd` to "second", `1,000` to "one thousand", `2.5` to "two point five").
6. Hyphens split words (`well-known` to "well known").
7. All other punctuation is removed. Apostrophes inside words are kept.
8. Whitespace is collapsed.

WER is computed with `jiwer` over the whole set (total errors divided by total reference words). Pairs with an empty reference are dropped. An empty hypothesis counts as all deletions.

Known limits: the normaliser does not expand contractions ("all's" vs "all is" counts as errors) and does not unify British and American spelling ("honour" vs "honor"). These affect every engine equally.

## Adding a new engine

1. Open the placeholder in `engines/` (`deepgram.py`, `assemblyai.py`, `slot_a.py`, `slot_b.py`) or copy `engines/velma.py`.
2. Subclass `Engine`, set `name` and `price_per_hour` (USD per audio hour, from the vendor's published price, or `None` if unknown), read the key from the environment, and implement `transcribe(audio_path)` returning a `Transcription` with the text and measured latency.
3. Register the class in `engines/__init__.py`.
4. Add the key name to `.env.example` and your `.env`.
5. Run `python benchmark.py --engine <name> --dataset <dataset>` for each dataset, then `python benchmark.py --report`.

Do not hardcode keys, and do not apply engine-specific text cleanup. Scoring must stay shared.

## Velma API reference used

Endpoint `POST https://platform.modulate.ai/api/velma-2-stt-batch-english-vfast` (also `velma-2-stt-batch` and `velma-2-stt-batch-multilingual-vfast`), header `X-API-Key`, multipart field `upload_file`, JSON response with `text` and `duration_ms`. See https://docs.modulate.ai/api-reference/stt/batch-english-vfast. The wrapper retries 429, 502, 503 and 504 with exponential backoff and fails fast on other errors.
