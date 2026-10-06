"""whisper.cpp, run LOCALLY with its bundled HTTP server (no network, no API key).

Source: https://github.com/ggml-org/whisper.cpp (server docs: examples/server/README.md).
Setup (see README): build whisper.cpp with cmake, download the ggml models with
models/download-ggml-model.sh (tiny.en, base.en), and point WHISPER_CPP_DIR at the checkout.

The engine starts `whisper-server` on a free localhost port with the model loaded, posts each
file to /inference (multipart, response_format=json) and stops the server on exit. Defaults are
used for everything else (4 threads, temperature 0.0 with fallback, language en). On Apple
Silicon the build uses Metal, so inference runs on the GPU.

Latency is a LOCAL measurement: wall-clock for the HTTP request to the local server, which
includes inference but excludes model loading (done once at start) and excludes the untimed
warm-up call. The server reads 16 kHz mono 16-bit WAV, so each file is converted once, before
the timer starts, into datasets/audio/_wav16k/ (git-ignored). Latency depends on this machine
and on what else is running, so it must not be compared with hosted API latency.
price_per_hour is 0.0: no API charge. Local compute and electricity are not counted.
"""
import atexit
import os
import socket
import subprocess
import time
from pathlib import Path

import requests

from .audio_utils import to_wav16k
from .base import Engine, Transcription


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class WhisperCppLocal(Engine):
    local = True
    price_per_hour = 0.0
    model_file = "ggml-base.en.bin"

    def __init__(self, model: str = None, timeout: float = 120):
        root = os.environ.get("WHISPER_CPP_DIR")
        if not root:
            raise RuntimeError("WHISPER_CPP_DIR is not set (path to a built whisper.cpp checkout)")
        binary = Path(root) / "build" / "bin" / "whisper-server"
        model_path = Path(model) if model else Path(root) / "models" / self.model_file
        for p in (binary, model_path):
            if not p.exists():
                raise RuntimeError(f"{p} not found; build whisper.cpp and download the model first")
        self.model = f"{model_path.name} (whisper.cpp)"
        self.timeout = timeout
        self._port = _free_port()
        self._proc = subprocess.Popen(
            [str(binary), "-m", str(model_path), "--host", "127.0.0.1", "--port", str(self._port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        atexit.register(self.close)
        self._url = f"http://127.0.0.1:{self._port}"
        deadline = time.time() + 120
        while True:
            if self._proc.poll() is not None:
                raise RuntimeError("whisper-server exited during start-up")
            try:
                if requests.get(self._url + "/", timeout=2).status_code == 200:
                    break
            except requests.RequestException:
                pass
            if time.time() > deadline:
                self.close()
                raise RuntimeError("whisper-server did not become ready")
            time.sleep(0.5)

    def close(self):
        if getattr(self, "_proc", None) and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def _post(self, wav: str) -> str:
        with open(wav, "rb") as f:
            r = requests.post(self._url + "/inference", files={"file": f},
                              data={"response_format": "json", "temperature": "0.0"},
                              timeout=self.timeout)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        return " ".join(r.json().get("text", "").split())

    def warmup(self, audio_path: str) -> None:
        self._post(to_wav16k(audio_path))

    def transcribe(self, audio_path: str) -> Transcription:
        wav = to_wav16k(audio_path)  # conversion happens before the timer starts
        start = time.perf_counter()
        try:
            text = self._post(wav)
        except (requests.RequestException, RuntimeError) as e:
            raise RuntimeError(f"whisper.cpp request failed for {audio_path}: {e}")
        return Transcription(text=text, latency_s=time.perf_counter() - start)


class WhisperCppTiny(WhisperCppLocal):
    name = "whisper_cpp_tiny"
    model_file = "ggml-tiny.en.bin"


class WhisperCppBase(WhisperCppLocal):
    name = "whisper_cpp_base"
    model_file = "ggml-base.en.bin"
