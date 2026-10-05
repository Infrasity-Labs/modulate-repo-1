# Phase 1 Velma results (archived)

Velma-only results from the first run, kept for reference. They are superseded by the three-engine results in the parent folder.

- **Run date:** 2026-10-05, before Deepgram and AssemblyAI were added.
- **Model:** `velma-2-stt-batch-english-vfast`, 20 files per dataset (same files as phase 2).
- **One call per file.** Latency is a single measurement per file, not an average of 3 repeats.
- **Older normaliser.** These numbers were scored without the British to American spelling rule that was added later, so WER is not comparable with the phase 2 table. For example LibriSpeech WER was 0.91 here and is 0.68 in phase 2, which is a fresh run of the same 20 files scored with the newer normaliser.
- **Not run in the same session as other engines.**

These files are copies from git commit `5b4e866`. The original per-file transcripts are in `velma_*.json`.
