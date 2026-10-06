**Hosted APIs**

| Dataset | Engine | Model | Files | Excluded | WER % | Mean latency (s) | Median latency (s) | USD per audio hour |
|---|---|---|---|---|---|---|---|---|
| librispeech | velma | english-fast | 20 | 0 | 0.91 | 4.41 | 3.63 | 0.025 |
| librispeech | deepgram | nova-3 | 20 | 0 | 2.72 | 3.79 | 2.78 | 0.258 |
| librispeech | assemblyai | universal-3-5-pro | 20 | 0 | 1.81 | 8.34 | 6.68 | 0.21 |
| voxpopuli | velma | english-fast | 20 | 0 | 4.77 | 5.41 | 4.58 | 0.025 |
| voxpopuli | deepgram | nova-3 | 20 | 0 | 8.3 | 5.85 | 3.91 | 0.258 |
| voxpopuli | assemblyai | universal-3-5-pro | 20 | 0 | 8.3 | 9.53 | 7.02 | 0.21 |
| commonvoice | velma | english-fast | 20 | 0 | 9.2 | 4.69 | 3.93 | 0.025 |
| commonvoice | deepgram | nova-3 | 20 | 0 | 12.27 | 4.5 | 4.52 | 0.258 |
| commonvoice | assemblyai | universal-3-5-pro | 20 | 0 | 8.59 | 7.6 | 7.59 | 0.21 |
| overall | velma | english-fast | 60 | 0 | 3.87 | 4.83 | 4.0 | 0.025 |
| overall | deepgram | nova-3 | 60 | 0 | 6.63 | 4.71 | 3.72 | 0.258 |
| overall | assemblyai | universal-3-5-pro | 60 | 0 | 5.71 | 8.49 | 7.04 | 0.21 |

**Local engines (this machine)**

| Dataset | Engine | Model | Files | Excluded | WER % | Mean latency (s) | Median latency (s) | USD per audio hour |
|---|---|---|---|---|---|---|---|---|
| librispeech | moonshine_tiny | moonshine-ai/moonshine-tiny | 20 | 0 | 2.49 | 0.17 | 0.13 | 0.0 |
| librispeech | moonshine_base | moonshine-ai/moonshine-base | 20 | 0 | 1.13 | 0.33 | 0.25 | 0.0 |
| librispeech | whisper_cpp_tiny | ggml-tiny.en.bin (whisper.cpp) | 20 | 0 | 3.85 | 0.09 | 0.07 | 0.0 |
| librispeech | whisper_cpp_base | ggml-base.en.bin (whisper.cpp) | 20 | 0 | 3.4 | 0.13 | 0.11 | 0.0 |
| voxpopuli | moonshine_tiny | moonshine-ai/moonshine-tiny | 20 | 0 | 14.52 | 0.18 | 0.19 | 0.0 |
| voxpopuli | moonshine_base | moonshine-ai/moonshine-base | 20 | 0 | 11.62 | 0.35 | 0.4 | 0.0 |
| voxpopuli | whisper_cpp_tiny | ggml-tiny.en.bin (whisper.cpp) | 20 | 0 | 11.0 | 0.09 | 0.1 | 0.0 |
| voxpopuli | whisper_cpp_base | ggml-base.en.bin (whisper.cpp) | 20 | 0 | 10.17 | 0.14 | 0.14 | 0.0 |
| commonvoice | moonshine_tiny | moonshine-ai/moonshine-tiny | 20 | 0 | 27.61 | 0.09 | 0.08 | 0.0 |
| commonvoice | moonshine_base | moonshine-ai/moonshine-base | 20 | 0 | 19.02 | 0.14 | 0.14 | 0.0 |
| commonvoice | whisper_cpp_tiny | ggml-tiny.en.bin (whisper.cpp) | 20 | 0 | 25.15 | 0.06 | 0.06 | 0.0 |
| commonvoice | whisper_cpp_base | ggml-base.en.bin (whisper.cpp) | 20 | 0 | 22.09 | 0.09 | 0.09 | 0.0 |
| overall | moonshine_tiny | moonshine-ai/moonshine-tiny | 60 | 0 | 11.6 | 0.15 | 0.11 | 0.0 |
| overall | moonshine_base | moonshine-ai/moonshine-base | 60 | 0 | 8.47 | 0.27 | 0.19 | 0.0 |
| overall | whisper_cpp_tiny | ggml-tiny.en.bin (whisper.cpp) | 60 | 0 | 10.22 | 0.08 | 0.06 | 0.0 |
| overall | whisper_cpp_base | ggml-base.en.bin (whisper.cpp) | 60 | 0 | 9.21 | 0.12 | 0.1 | 0.0 |

