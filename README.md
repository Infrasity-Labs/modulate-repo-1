# Speech-to-Text Benchmark for Velma Transcribe

A reproducible speech-to-text benchmark built around [Modulate's Velma Transcribe](https://www.modulate.ai) batch API. It follows the layout of [Picovoice's speech-to-text-benchmark](https://github.com/Picovoice/speech-to-text-benchmark): one CLI, one file per engine, shared scoring, and results and plots checked into the repo.

> **Status: Velma only.** Deepgram, AssemblyAI and two generic engines are empty slots that have not been run. Nothing below is a comparison between vendors yet.

## Table of contents

- [Data](#data)
- [Metrics](#metrics)
- [Engines](#engines)
- [Usage](#usage)
- [Results](#results)
- [Text normalisation](#text-normalisation)
- [Adding a new engine](#adding-a-new-engine)
- [Repository layout](#repository-layout)
- [Limitations](#limitations)

## Data

20 files per dataset, English. Audio is downloaded on demand into `datasets/audio/` and is **not** committed. The files used are recorded in `datasets/manifests/<dataset>.json` (id, path, reference transcript, duration).

| Dataset | Source | Slice | Audio |
|---|---|---|---|
| LibriSpeech | `openslr/librispeech_asr`, `clean`, `test` | first 20 | 164 s |
| VoxPopuli | `facebook/voxpopuli`, `en`, `test` | first 20 | 183 s |
| Common Voice | `fixie-ai/common_voice_17_0`, `en`, `test` (parquet mirror of Mozilla Common Voice 17) | first 20 | 108 s |

## Metrics

| Metric | Definition |
|---|---|
| WER | Word error rate with [`jiwer`](https://github.com/jitsi/jiwer), computed over the whole slice (total errors divided by total reference words) after [normalisation](#text-normalisation). Lower is better. |
| Latency | Wall-clock seconds for one request (upload plus transcription, including network), reported as mean and median over files. Files are sent one at a time. This is batch latency, not streaming latency. |
| Cost per audio hour | The vendor's published price in USD per hour of audio. It is a price lookup, not a measurement, so it is identical across datasets for a given model. Left blank when a price is unknown. |

## Engines

| Engine | File | Status | Model(s) | Price (USD per audio hour, batch) |
|---|---|---|---|---|
| Velma Transcribe | `engines/velma.py` | tested | `english-fast` (default), `multilingual`, `multilingual-fast` | 0.025, 0.03, 0.03 ([pricing](https://www.modulate.ai/api-pricing)) |
| Deepgram | `engines/deepgram.py` | slot, not configured | | |
| AssemblyAI | `engines/assemblyai.py` | slot, not configured | | |
| Slot A | `engines/slot_a.py` | slot, not configured | | |
| Slot B | `engines/slot_b.py` | slot, not configured | | |

Velma API details come from the [official docs](https://docs.modulate.ai/api-reference/stt/batch-english-vfast): `POST https://platform.modulate.ai/api/velma-2-stt-batch-english-vfast`, header `X-API-Key`, multipart field `upload_file`, response fields `text` and `duration_ms`. The wrapper retries 429, 502, 503 and 504 with exponential backoff and fails fast on other errors. Only the English Fast model has been benchmarked so far.

## Usage

```bash
git clone https://github.com/Infrasity-Labs/modulate-repo-1 && cd modulate-repo-1
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set VELMA_API_KEY in .env
```

The API key is read from the environment only. `.env` is git-ignored. Never commit keys.

```bash
# 1. fetch the data slices (audio is git-ignored, manifests are committed)
python download_datasets.py --dataset all --num-files 20

# 2. run an engine
python benchmark.py --engine velma --dataset librispeech --num-files 20
python benchmark.py --engine velma --dataset voxpopuli --num-files 20
python benchmark.py --engine velma --dataset commonvoice --num-files 20

# 3. rebuild the table and plots from results/
python benchmark.py --report

# tests (fake text, no API needed)
python -m pytest
```

| Flag | Meaning |
|---|---|
| `--engine` | `velma`, `deepgram`, `assemblyai`, `slot_a`, `slot_b` (unconfigured engines exit with a clear message) |
| `--dataset` | `librispeech`, `voxpopuli`, `commonvoice` |
| `--num-files` | number of files from the manifest (default 20) |
| `--model` | engine model variant, for Velma `english-fast`, `multilingual` or `multilingual-fast` |
| `--report` | regenerate `results/results.csv`, `results/results.md` and `results/plots/` |

## Results

**Velma only, English Fast model, batch API.** Tested on 2026-10-05 from a local macOS machine over the public internet. Test location (city or region): _to be filled in._ The Deepgram, AssemblyAI and slot rows have not been run.

| Engine | Model | Dataset | Files | WER % | Mean latency (s) | Median latency (s) | USD per audio hour | Tested on |
|---|---|---|---|---|---|---|---|---|
| velma | english-fast | librispeech | 20 | 0.91 | 4.41 | 3.63 | 0.025 | 2026-10-05 |
| velma | english-fast | voxpopuli | 20 | 4.77 | 5.41 | 4.58 | 0.025 | 2026-10-05 |
| velma | english-fast | commonvoice | 20 | 9.2 | 4.69 | 3.93 | 0.025 | 2026-10-05 |
| deepgram | | | | not run | | | | |
| assemblyai | | | | not run | | | | |
| slot_a | | | | not run | | | | |
| slot_b | | | | not run | | | | |

Machine-readable: [`results/results.csv`](results/results.csv), [`results/results.md`](results/results.md). Per-file transcripts, references and latencies: `results/<engine>_<dataset>.json`.

### Word error rate

![WER](results/plots/wer.png)

### Latency

![Latency](results/plots/latency.png)

### Cost per audio hour

![Cost per hour](results/plots/cost_per_hour.png)

### Observations

- WER rises from clean read speech (LibriSpeech) to parliamentary speech (VoxPopuli) to crowd-sourced recordings (Common Voice), which is the expected order.
- No empty outputs and no wrong-language output in the 60 files.
- One Common Voice clip (`commonvoice_010`, reference "I guess you must think I'm kinda Batty.", output "Russians can't handle Bhakti.") is a full miss and accounts for a large share of the 9.2%. We have not established whether it is a recognition error or a poor reference.
- Some VoxPopuli errors are dropped or altered words, for example a sentence truncated at the end.
- Part of the remaining WER is formatting that the normaliser does not unify, such as "all's" against "all is" and "honour" against "honor".

## Text normalisation

Every engine's output and every reference passes through `scoring/normalize.py` before scoring. Rules, in order:

1. Unicode NFKC, then lowercase.
2. Curly apostrophes become straight apostrophes.
3. Bracketed or angle-bracket markers such as `[laughter]` are removed.
4. `%` becomes "percent" and `&` becomes "and".
5. Digits become words with `num2words` (`3` to "three", `2nd` to "second", `1,000` to "one thousand", `2.5` to "two point five").
6. Hyphens split words (`well-known` to "well known").
7. All other punctuation is removed. Apostrophes inside words are kept.
8. Whitespace is collapsed.

Pairs with an empty reference are dropped. An empty hypothesis counts as all deletions. No engine-specific cleanup is allowed.

## Adding a new engine

1. Open the placeholder in `engines/` or copy `engines/velma.py`.
2. Subclass `Engine`, set `name` and `price_per_hour` (USD per audio hour from the vendor's published price, or `None` if unknown), read the key from the environment, and implement `transcribe(audio_path)` returning a `Transcription` (text and measured latency).
3. Register the class in `engines/__init__.py`.
4. Add the key name to `.env.example` and set it in your `.env`.
5. Run `python benchmark.py --engine <name> --dataset <dataset>` for each dataset, then `python benchmark.py --report`.

## Repository layout

```
benchmark.py            single CLI entry point (run and report)
download_datasets.py    downloads slices and writes manifests
engines/                base.py plus one file per engine
scoring/                normalize.py and wer.py, shared by all engines
tests/                  unit tests on fake text
datasets/manifests/     files used (audio is git-ignored)
results/                results.csv, results.md, per-file JSON
results/plots/          wer.png, latency.png, cost_per_hour.png
```

## Limitations

- Small samples (20 files per dataset), so a single file can shift WER noticeably.
- Latency includes network time from the test machine and varies by location and connection.
- Common Voice comes from a third-party Hugging Face mirror, not Mozilla's own distribution.
- English only so far.
- The Velma docs do not state rate limits.
