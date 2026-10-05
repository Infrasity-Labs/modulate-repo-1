# Speech-to-Text Benchmark: Velma, Deepgram and AssemblyAI

A reproducible speech-to-text benchmark for [Modulate's Velma Transcribe](https://www.modulate.ai), [Deepgram](https://deepgram.com) and [AssemblyAI](https://www.assemblyai.com). It follows the layout of [Picovoice's speech-to-text-benchmark](https://github.com/Picovoice/speech-to-text-benchmark): one CLI, one file per engine, shared scoring, and results and plots checked into the repo.

> The samples are small (20 files and 163 to 482 reference words per dataset), so a difference of one or two words moves WER by about 0.2 to 0.6 points. Read the numbers as indicative, not as a ranking. See [Limitations](#limitations).

## Table of contents

- [Data](#data)
- [Metrics](#metrics)
- [Engines and models](#engines-and-models)
- [Usage](#usage)
- [Results](#results)
- [Text normalisation](#text-normalisation)
- [Adding a new engine](#adding-a-new-engine)
- [Repository layout](#repository-layout)
- [Limitations](#limitations)

## Data

20 English files per dataset. Audio is downloaded on demand into `datasets/audio/` and is **not** committed. The files used are recorded in `datasets/manifests/<dataset>.json` (id, path, reference transcript, duration).

| Dataset | Source | Slice | Audio | Reference words |
|---|---|---|---|---|
| LibriSpeech | `openslr/librispeech_asr`, `clean`, `test` | first 20 | 164 s | 441 |
| VoxPopuli | `facebook/voxpopuli`, `en`, `test` | first 20 | 183 s | 482 |
| Common Voice | `fixie-ai/common_voice_17_0`, `en`, `test` (parquet mirror of Mozilla Common Voice 17) | first 20 | 108 s | 163 |

## Metrics

| Metric | Definition |
|---|---|
| WER | Word error rate with [`jiwer`](https://github.com/jitsi/jiwer), computed over the whole slice (total errors divided by total reference words) after [normalisation](#text-normalisation). |
| Latency | Wall-clock seconds for one request including upload from the test machine and any server-side wait. Each file is sent 3 times per engine and the 3 values are averaged per file. The table reports the mean and median of those per-file averages. Batch latency, not streaming latency. |
| USD per audio hour | The vendor's published price for the model used. A price lookup, not a measurement. |

How latency is measured per engine:
- **Velma and Deepgram:** one HTTP request. The timer covers sending the file and receiving the transcript.
- **AssemblyAI:** a three-step flow (upload, submit, poll every 0.25 s). The timer starts before the upload and stops when the status is `completed`, so it covers all three steps and is comparable with the single-call engines. The submit-to-final time is stored in the raw response but is not what the table reports.

## Engines and models

| Engine | File | Model used | Settings | USD per audio hour | Price source |
|---|---|---|---|---|---|
| Velma Transcribe | `engines/velma.py` | `velma-2-stt-batch-english-vfast` (English Fast) | none | 0.025 | [modulate.ai/api-pricing](https://www.modulate.ai/api-pricing) |
| Deepgram | `engines/deepgram.py` | `nova-3` | `language=en`, `smart_format=true` | 0.258 ($0.0043 per minute) | [deepgram.com/pricing](https://deepgram.com/pricing) |
| AssemblyAI | `engines/assemblyai.py` | `universal-3-5-pro` (`speech_models`), reported back as `speech_model_used` | `language_code=en` | 0.21 | [assemblyai.com/pricing](https://www.assemblyai.com/pricing) |
| Slot A, Slot B | `engines/slot_a.py`, `slot_b.py` | not configured | | | |

Each model is the vendor's current recommended or default general-purpose English model as given in its docs on the test date. Prices are the pay-as-you-go pre-recorded (batch) rates read from the vendors' pricing pages on 2026-10-05 and 2026-10-06, and plans differ.

API references: [Velma](https://docs.modulate.ai/api-reference/stt/batch-english-vfast), [Deepgram](https://developers.deepgram.com/docs/pre-recorded-audio), [AssemblyAI](https://www.assemblyai.com/docs/getting-started/transcribe-an-audio-file). All wrappers retry transient errors (408, 429 and 5xx) with exponential backoff.

Language is set to English for Deepgram and AssemblyAI. In an early test AssemblyAI with automatic language detection returned Slovenian text for English VoxPopuli audio, so the language is pinned for fairness with the English-only Velma model.

## Usage

```bash
git clone https://github.com/Infrasity-Labs/modulate-repo-1 && cd modulate-repo-1
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # set VELMA_API_KEY, DEEPGRAM_API_KEY, ASSEMBLYAI_API_KEY
```

Keys are read from the environment only. `.env` is git-ignored. Never commit keys.

```bash
# 1. fetch the data slices (audio is git-ignored, manifests are committed)
python download_datasets.py --dataset all --num-files 20

# 2. run all engines in one session, 3 repeats per file
python benchmark.py --engine velma deepgram assemblyai --dataset all --num-files 20 --repeats 3

# 3. rebuild the table and plots from results/session.json
python benchmark.py --report

# tests (fake text, no API needed)
python -m pytest
```

| Flag | Meaning |
|---|---|
| `--engine` | one or more of `velma`, `deepgram`, `assemblyai`, `slot_a`, `slot_b` |
| `--dataset` | `librispeech`, `voxpopuli`, `commonvoice`, or `all` |
| `--num-files` | files per dataset from the manifest (default 20) |
| `--repeats` | calls per file, latency is averaged (default 3) |
| `--model ENGINE=MODEL` | override a model, for example `velma=multilingual` |
| `--report` | regenerate `results/results.csv`, `results/results.md` and `results/plots/` |

How a session works: engines are called one after another for each file, so all engines see similar network conditions. Every call is cached in `results/call_cache.jsonl` (git-ignored), so an interrupted run resumes where it stopped. If any engine fails on a file after retries, the file is excluded for every engine and the count is shown in the results. To start a fresh run, delete `results/call_cache.jsonl` and `results/session.json`.

## Results

Test run: started 2026-10-05 22:51 and finished 2026-10-06 00:20 (local time of the test machine), one session, one machine, sequential calls, over a consumer internet connection. Test location (city or region): _to be filled in._ Machine: macOS (Darwin 25.3), Python 3.9.

540 calls (3 engines x 60 files x 3 repeats). Every file succeeded for every engine, so 0 files were excluded. One Deepgram call on `voxpopuli_006` first failed with an HTTP 408 upload timeout, because the wrapper did not yet retry 408. After adding 408 to the retry list, that single call was re-run after the main session finished. The other two repeats for that file were measured during the main session.

| Dataset | Engine | Model | Files | Excluded | WER % | Mean latency (s) | Median latency (s) | USD per audio hour |
|---|---|---|---|---|---|---|---|---|
| librispeech | velma | english-fast | 20 | 0 | 0.68 | 7.47 | 6.87 | 0.025 |
| librispeech | deepgram | nova-3 | 20 | 0 | 2.72 | 3.79 | 2.78 | 0.258 |
| librispeech | assemblyai | universal-3-5-pro | 20 | 0 | 1.81 | 8.34 | 6.68 | 0.21 |
| voxpopuli | velma | english-fast | 20 | 0 | 4.77 | 9.71 | 6.93 | 0.025 |
| voxpopuli | deepgram | nova-3 | 20 | 0 | 8.3 | 5.85 | 3.91 | 0.258 |
| voxpopuli | assemblyai | universal-3-5-pro | 20 | 0 | 8.3 | 9.53 | 7.02 | 0.21 |
| commonvoice | velma | english-fast | 20 | 0 | 9.82 | 18.64 | 20.57 | 0.025 |
| commonvoice | deepgram | nova-3 | 20 | 0 | 12.27 | 4.5 | 4.52 | 0.258 |
| commonvoice | assemblyai | universal-3-5-pro | 20 | 0 | 8.59 | 7.6 | 7.59 | 0.21 |
| overall | velma | english-fast | 60 | 0 | 3.87 | 11.94 | 8.65 | 0.025 |
| overall | deepgram | nova-3 | 60 | 0 | 6.63 | 4.71 | 3.72 | 0.258 |
| overall | assemblyai | universal-3-5-pro | 60 | 0 | 5.71 | 8.49 | 7.04 | 0.21 |

Machine-readable: [`results/results.csv`](results/results.csv), [`results/results.md`](results/results.md), [`results/session.json`](results/session.json). Per-file transcripts, references and per-repeat latencies: `results/<engine>_<dataset>.json`.

### Word error rate

![WER](results/plots/wer.png)

### Latency

![Latency](results/plots/latency.png)

### Cost per audio hour

![Cost per hour](results/plots/cost_per_hour.png)

### Notes on the numbers

- **One Common Voice clip is unusable.** For `commonvoice_010` (reference "I guess you must think I'm kinda Batty.") all three engines fail differently: Velma returned "Russians can't handle Bhakti.", Deepgram returned an empty transcript, and AssemblyAI returned "question was written on the paper". This points to a problem with the clip or its reference, not with one engine. It is kept in the tables because exclusion is only applied to engine failures. Without it, Common Voice WER is 5.16 for Velma, 7.74 for Deepgram and 3.87 for AssemblyAI, and overall WER is 3.15, 5.94 and 5.01.
- **Latency is noisy and changed during the run.** Velma's Common Voice latency (median 20.6 s) is about three times its LibriSpeech latency, even though the Common Voice clips are shorter. A follow-up probe on the same Common Voice files, run sequentially after the session, gave 22.3, 17.9, 9.7 and 7.6 s, and LibriSpeech files gave 6.0 and 7.0 s. So Velma's latency varied over time and is not a stable property of the dataset. Other engines were steadier in this run. Latency includes upload from the test machine and depends on network conditions and server load at the time. A rerun at another time of day is needed before drawing conclusions about latency.
- **Part of the WER is reference style, not recognition.** LibriSpeech references contain "to day" and "to morrow", while Deepgram and AssemblyAI write "today" and "tomorrow". AssemblyAI wrote "2010" for the spoken "two thousand and ten", which the number rule renders without "and". Neither engine is wrong about the audio.
- **Contractions and possessives.** All engines drop the possessive in "country's" and "master's" in one LibriSpeech file, and "all's" against "all is" counts as an error for engines that write the latter.
- **No empty outputs** except Deepgram on `commonvoice_010`. No wrong-language output after language was pinned.
- **Common Voice has only 163 reference words.** One word is 0.6 WER points.

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
9. British spellings become American using the spelling map from the [`whisper-normalizer`](https://pypi.org/project/whisper-normalizer/) package (`travellers` to "travelers", `honour` to "honor").

Change log: rule 9 was added after the fairness check on 2026-10-05. On five test files, Deepgram and AssemblyAI returned American spellings while the VoxPopuli references use British ones, which counted against those two engines only. All results in this README use rule 9. Earlier Velma-only numbers (for example 0.91 WER on LibriSpeech) were produced without it and are superseded.

Pairs with an empty reference are dropped. An empty hypothesis counts as all deletions. No engine-specific cleanup is allowed. The fairness check found no speaker labels, filler-word markup or leftover digits in any engine's output after normalisation.

## Adding a new engine

1. Open the placeholder in `engines/` or copy `engines/velma.py`.
2. Subclass `Engine`, set `name` and `price_per_hour` (USD per audio hour from the vendor's published price, or `None` if unknown), read the key from the environment, and implement `transcribe(audio_path)` returning a `Transcription` (text and measured latency).
3. Register the class in `engines/__init__.py`.
4. Add the key name to `.env.example` and set it in your `.env`.
5. Run all engines together so the comparison stays in one session: `python benchmark.py --engine velma deepgram assemblyai <name> --dataset all --repeats 3`. Delete `results/call_cache.jsonl` and `results/session.json` first for a fresh session.

## Repository layout

```
benchmark.py            single CLI entry point (run and report)
download_datasets.py    downloads slices and writes manifests
engines/                base.py plus one file per engine
scoring/                normalize.py and wer.py, shared by all engines
tests/                  unit tests on fake text
datasets/manifests/     files used (audio is git-ignored)
results/                results.csv, results.md, session.json, per-file JSON
results/plots/          wer.png, latency.png, cost_per_hour.png
```

## Limitations

- Small samples: 20 files and 163 to 482 reference words per dataset. One word changes WER by about 0.2 to 0.6 points, and the differences between engines on a single dataset are often a handful of words.
- One run, one machine, one network, one time window. Latency includes upload from the test machine and server-side load, and Velma's latency in particular varied over the session.
- Common Voice comes from a third-party Hugging Face mirror, not Mozilla's own distribution, and one clip in it is unusable.
- English only. The first 20 files of each split are used, not a random sample.
- Each engine is run with one model and one setting. Other models, settings (for example Deepgram without `smart_format`) and plans may behave differently and are priced differently.
- The normaliser does not expand contractions, does not unify compound words such as "today" and "to day", and renders numbers without British "and".
- The Velma docs do not state rate limits.
