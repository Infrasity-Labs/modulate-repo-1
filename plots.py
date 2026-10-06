"""Dashboard-style charts for the benchmark results.

Every chart is drawn on one pixel-coordinate canvas (1 data unit = 1 px at 100 dpi) so the same
panel functions build both the single-metric images and the combined overview image.
Colors are assigned per engine and every engine gets the same treatment; no engine is highlighted.
"""
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, to_rgb  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch  # noqa: E402

plt.rcParams["font.family"] = ["Avenir Next", "Helvetica Neue", "Arial", "DejaVu Sans"]

BG, BG2 = "#080D1C", "#101A3A"
CARD, EDGE, TRACK = "#111A33", "#22305A", "#1A2547"
TEXT, MUTED, FAINT = "#F1F5F9", "#8EA0C4", "#4B5C85"
HOSTED_DOT, LOCAL_DOT = "#38BDF8", "#FBBF24"

PALETTE = {
    "velma": "#818CF8", "deepgram": "#38BDF8", "assemblyai": "#FB7185", "chirp_3": "#A3E635",
    "mai_transcribe_2": "#2DD4BF", "moonshine_tiny": "#FBBF24", "moonshine_base": "#FB923C",
    "whisper_cpp_tiny": "#F0ABFC", "whisper_cpp_base": "#C084FC", "whisper_hf": "#34D399",
}
NAMES = {
    "velma": "Velma Fast", "deepgram": "Deepgram nova-3", "assemblyai": "AssemblyAI 3.5 Pro",
    "chirp_3": "Google Chirp 3", "mai_transcribe_2": "MAI-Transcribe 2",
    "moonshine_tiny": "Moonshine Tiny", "moonshine_base": "Moonshine Base",
    "whisper_cpp_tiny": "whisper.cpp tiny.en", "whisper_cpp_base": "whisper.cpp base.en",
    "whisper_hf": "Whisper large-v3 (HF)",
}
# Model files on disk for the local engines: Moonshine from the Hugging Face cache, whisper.cpp from its README
MODEL_SIZE = {"moonshine_tiny": "105 MiB", "moonshine_base": "237 MiB",
              "whisper_cpp_tiny": "75 MiB", "whisper_cpp_base": "142 MiB"}
DATASET_NAMES = {"librispeech": "LibriSpeech", "voxpopuli": "VoxPopuli", "commonvoice": "Common Voice"}


def _fs(px):  # pixel size to points at 100 dpi
    return px * 0.72


def _mix(color, other, t):
    a, b = np.array(to_rgb(color)), np.array(to_rgb(other))
    return tuple(a * (1 - t) + b * t)


def _t(ax, x, y, s, size, color=TEXT, weight="normal", ha="left", va="center", **kw):
    return ax.text(x, y, s, fontsize=_fs(size), color=color, fontweight=weight, ha=ha, va=va, **kw)


def _canvas(w, h):
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis("off")
    grad = np.linspace(0, 1, 256)[:, None]
    ax.imshow(grad, extent=(0, w, h, 0), cmap=LinearSegmentedColormap.from_list("bg", [BG, BG2]),
              aspect="auto", zorder=0)
    # soft color blobs for depth
    yy, xx = np.mgrid[0:h:6, 0:w:6]
    for cx, cy, rad, col in [(0.05 * w, 0.0, 0.55 * w, "#6366F1"), (w, h, 0.6 * w, "#EC4899")]:
        a = np.clip(1 - np.hypot(xx - cx, yy - cy) / rad, 0, 1) ** 2 * 0.22
        rgba = np.zeros(a.shape + (4,))
        rgba[..., :3] = to_rgb(col)
        rgba[..., 3] = a
        ax.imshow(rgba, extent=(0, w, h, 0), aspect="auto", zorder=1)
    return fig, ax


def _card(ax, x, y, w, h):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=22", fc=CARD, ec=EDGE,
                                lw=1.3, zorder=2))


def _grad_bar(ax, x, y, w, h, color, z=5):
    """Rounded bar with a horizontal gradient and a soft glow."""
    r = min(h / 2, w / 2)
    for k, alpha in [(8, 0.05), (5, 0.08), (2.5, 0.12)]:
        ax.add_patch(FancyBboxPatch((x - k, y - k), w + 2 * k, h + 2 * k,
                                    boxstyle=f"round,pad=0,rounding_size={r + k}", fc=color, ec="none",
                                    alpha=alpha, zorder=z - 1))
    clip = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc="none", ec="none",
                          zorder=z)
    ax.add_patch(clip)
    cmap = LinearSegmentedColormap.from_list("g", [_mix(color, "#000000", 0.45), color, _mix(color, "#FFFFFF", 0.3)])
    im = ax.imshow(np.linspace(0, 1, 256)[None, :], extent=(x, x + w, y + h, y), cmap=cmap, aspect="auto",
                   zorder=z, interpolation="bicubic")
    im.set_clip_path(clip)
    # thin highlight along the top edge
    ax.plot([x + r, x + w - r], [y + 2.5, y + 2.5], color="#FFFFFF", alpha=0.25, lw=1.2, zorder=z + 1,
            solid_capstyle="round")


def _dot(ax, x, y, color, r=4.5, z=6):
    ax.add_patch(Circle((x, y), r, fc=color, ec="none", zorder=z))


def panel_bars(ax, rect, title, subtitle, items, fmt, local, log=False, compact=False, price=False):
    """Ranked horizontal bars. items: list of (engine, value); best (lowest) first."""
    x, y, w, h = rect
    _card(ax, x, y, w, h)
    _t(ax, x + 30, y + 42, title, 25 if not compact else 21, weight="bold")
    _t(ax, x + 30, y + 74, subtitle, 15 if not compact else 13, color=MUTED)
    items = sorted(items, key=lambda it: it[1])
    n = len(items)
    top, bottom = y + (108 if not compact else 100), y + h - 22
    rh = (bottom - top) / n
    name_w = 262 if not compact else 196
    bx0, bx1 = x + 30 + 30 + name_w - 30, x + w - 30 - (92 if not compact else 78)
    bx0 = x + 40 + name_w
    vals = [v for _, v in items]
    vmax = max(vals) or 1
    pos = [v for v in vals if v > 0]
    lo = (min(pos) * 0.45) if (log and pos) else 0
    for i, (e, v) in enumerate(items):
        cy = top + rh * (i + 0.5)
        col = PALETTE.get(e, "#94A3B8")
        # rank badge
        ax.add_patch(Circle((x + 48, cy), 14, fc=_mix(col, BG, 0.78), ec=col, lw=1.4, zorder=4))
        _t(ax, x + 48, cy + 0.5, str(i + 1), 12.5, color=col, weight="bold", ha="center", zorder=5)
        # name and tag
        _t(ax, x + 74, cy - 9, NAMES.get(e, e), 17.5 if not compact else 15, weight="bold", zorder=5)
        is_local = e in local
        _dot(ax, x + 79, cy + 13, LOCAL_DOT if is_local else HOSTED_DOT, 3.6)
        tag = ("LOCAL  ·  " + MODEL_SIZE[e]) if (is_local and e in MODEL_SIZE) else ("LOCAL" if is_local else "HOSTED API")
        _t(ax, x + 90, cy + 13, tag, 12 if not compact else 11, color=MUTED, weight="600", zorder=5)
        # track and bar
        ax.add_patch(FancyBboxPatch((bx0, cy - 10), bx1 - bx0, 20, boxstyle="round,pad=0,rounding_size=10",
                                    fc=TRACK, ec="none", zorder=3))
        if log and v > 0:
            frac = (np.log10(v) - np.log10(lo)) / (np.log10(vmax * 1.05) - np.log10(lo))
        else:
            frac = v / (vmax * 1.0)
        length = max(frac * (bx1 - bx0), 14)
        _grad_bar(ax, bx0, cy - 10, length, 20, col)
        lab = fmt(v)
        _t(ax, bx0 + length + 12, cy, lab, 18 if not compact else 15.5, weight="bold", zorder=6)
        if price and v == 0:
            pass


def panel_scatter(ax, rect, items, local):
    """WER against latency. items: list of (engine, wer, latency)."""
    x, y, w, h = rect
    _card(ax, x, y, w, h)
    _t(ax, x + 30, y + 42, "Accuracy against speed", 25, weight="bold")
    _t(ax, x + 30, y + 74, "Top right is more accurate and faster · rings run locally, no network", 15, color=MUTED)
    px0, px1, py0, py1 = x + 88, x + w - 40, y + 116, y + h - 66
    wers = [i[1] for i in items]
    lats = [i[2] for i in items]
    wmin, wmax = 0, max(wers) * 1.12
    lmin, lmax = min(lats) * 0.6, max(lats) * 1.9

    def X(wv):  # reversed: lower WER on the right
        return px0 + (wmax - wv) / (wmax - wmin) * (px1 - px0)

    def Y(lv):  # log, faster at the top
        return py0 + (np.log10(lv) - np.log10(lmin)) / (np.log10(lmax) - np.log10(lmin)) * (py1 - py0)

    # glow in the "better" corner
    yy, xx = np.mgrid[int(py0):int(py1):4, int(px0):int(px1):4]
    a = np.clip(1 - np.hypot(xx - px1, yy - py0) / ((px1 - px0) * 0.62), 0, 1) ** 2 * 0.30
    rgba = np.zeros(a.shape + (4,))
    rgba[..., :3] = to_rgb("#34D399")
    rgba[..., 3] = a
    ax.imshow(rgba, extent=(px0, px1, py1, py0), aspect="auto", zorder=3)
    for gv in [0.1, 1, 10]:
        if lmin <= gv <= lmax:
            ax.plot([px0, px1], [Y(gv)] * 2, color=EDGE, lw=1, zorder=3)
            _t(ax, px0 - 12, Y(gv), f"{gv:g}s", 13.5, color=MUTED, ha="right")
    step = 2 if wmax > 8 else 1
    for wv in range(0, int(wmax) + 1, step):
        ax.plot([X(wv)] * 2, [py0, py1], color=EDGE, lw=1, zorder=3)
        _t(ax, X(wv), py1 + 20, f"{wv}%", 13.5, color=MUTED, ha="center")
    _t(ax, (px0 + px1) / 2, y + h - 22, "Word error rate (lower is better, axis reversed)", 14, color=MUTED, ha="center")
    ax.text(x + 30, (py0 + py1) / 2, "Mean latency per file (log scale)", fontsize=_fs(14), color=MUTED,
            rotation=90, ha="center", va="center")
    # label placement (dx, dy, ha) in px, chosen to keep labels apart
    off = {"velma": (0, -24, "center"), "deepgram": (-18, -22, "right"), "assemblyai": (20, 4, "left"),
           "chirp_3": (-18, 24, "right"), "mai_transcribe_2": (0, 26, "center"),
           "moonshine_tiny": (0, -24, "center"), "moonshine_base": (0, 26, "center"),
           "whisper_cpp_tiny": (22, 4, "left"), "whisper_cpp_base": (0, 26, "center")}
    for e, wv, lv in items:
        col = PALETTE.get(e, "#94A3B8")
        cx, cy = X(wv), Y(lv)
        for rr, al in [(22, 0.07), (16, 0.12)]:
            ax.add_patch(Circle((cx, cy), rr, fc=col, ec="none", alpha=al, zorder=4))
        if e in local:
            ax.add_patch(Circle((cx, cy), 9.5, fc=CARD, ec=col, lw=3, zorder=6))
        else:
            ax.add_patch(Circle((cx, cy), 9.5, fc=col, ec="#FFFFFF", lw=1.4, zorder=6))
        dx, dy, ha = off.get(e, (0, -24, "center"))
        _t(ax, cx + dx, cy + dy, NAMES.get(e, e), 14.5, weight="bold", ha=ha, zorder=7)


def _header(ax, w, subtitle):
    _t(ax, 60, 62, "Speech-to-Text Benchmark", 46, weight="bold")
    _t(ax, 62, 112, subtitle, 20, color=MUTED)
    # legend pills
    px = w - 60
    for label, col in [("LOCAL  ·  this machine", LOCAL_DOT), ("HOSTED API", HOSTED_DOT)]:
        wd = 56 + len(label) * 12.6
        ax.add_patch(FancyBboxPatch((px - wd, 40), wd, 40, boxstyle="round,pad=0,rounding_size=20", fc=CARD,
                                    ec=EDGE, lw=1.2, zorder=3))
        _dot(ax, px - wd + 22, 60, col, 5.5)
        _t(ax, px - wd + 38, 60, label, 15.5, color=TEXT, weight="600", zorder=4)
        px -= wd + 14


def _overall(summaries):
    return {r["engine"]: r for r in summaries if r["dataset"] == "overall"}


def make_all(summaries, out_dir, engines):
    local = {e for e, c in engines.items() if c.local}
    ov = _overall(summaries)
    n_eng = len(ov)
    pw, ph = 1260, 720
    pct = lambda v: f"{v:g}%"
    secs = lambda v: f"{v:.2f}s"
    usd = lambda v: "$0" if v == 0 else f"${v:.3f}"
    wer = [(e, r["wer_percent"]) for e, r in ov.items()]
    lat = [(e, r["mean_latency_s"]) for e, r in ov.items()]
    cost = [(e, r["price_per_hour_usd"]) for e, r in ov.items() if r.get("price_per_hour_usd") is not None]
    sc = [(e, r["wer_percent"], r["mean_latency_s"]) for e, r in ov.items()]
    note_wer = "Lower means fewer word errors · all 60 files"
    note_lat = "Mean seconds per file · log scale · local engines have no network, so are not directly comparable"
    note_cost = "USD per hour of audio · local engines: no API charge (compute not counted)"
    subtitle = f"{n_eng} engines  ·  LibriSpeech, VoxPopuli and Common Voice  ·  60 files  ·  one shared scoring pipeline"

    def single(name, draw):
        fig, ax = _canvas(pw + 80, ph + 80)
        draw(ax, (40, 40, pw, ph))
        fig.savefig(out_dir / name, dpi=100, facecolor=BG)
        plt.close(fig)

    single("wer.png", lambda ax, r: panel_bars(ax, r, "Word error rate", note_wer, wer, pct, local))
    single("latency.png", lambda ax, r: panel_bars(ax, r, "Latency per file", note_lat, lat, secs, local, log=True))
    single("cost_per_hour.png", lambda ax, r: panel_bars(ax, r, "Cost per audio hour", note_cost, cost, usd, local))
    single("wer_vs_latency.png", lambda ax, r: panel_scatter(ax, r, sc, local))

    # per-dataset detail: three panels side by side
    for key, fname, title, fmt, log in [("wer_percent", "wer_by_dataset.png", "Word error rate", pct, False),
                                         ("mean_latency_s", "latency_by_dataset.png", "Latency per file", secs, True)]:
        cw, chh, gap = 880, 720, 30
        fig, ax = _canvas(3 * cw + 4 * gap, chh + 2 * gap)
        for i, ds in enumerate(["librispeech", "voxpopuli", "commonvoice"]):
            items = [(r["engine"], r[key]) for r in summaries if r["dataset"] == ds]
            panel_bars(ax, (gap + i * (cw + gap), gap, cw, chh), f"{title} · {DATASET_NAMES[ds]}",
                       "20 files" + (" · log scale" if log else ""), items, fmt, local, log=log, compact=True)
        fig.savefig(out_dir / fname, dpi=100, facecolor=BG)
        plt.close(fig)

    # overview: everything on one image
    gap, head = 40, 170
    W, H = 2 * pw + 3 * gap, head + 2 * ph + 3 * gap
    fig, ax = _canvas(W, H)
    _header(ax, W, subtitle)
    panel_bars(ax, (gap, head, pw, ph), "Word error rate", note_wer, wer, pct, local)
    panel_bars(ax, (2 * gap + pw, head, pw, ph), "Latency per file", note_lat, lat, secs, local, log=True)
    panel_bars(ax, (gap, head + ph + gap, pw, ph), "Cost per audio hour", note_cost, cost, usd, local)
    panel_scatter(ax, (2 * gap + pw, head + ph + gap, pw, ph), sc, local)
    fig.savefig(out_dir / "overview.png", dpi=100, facecolor=BG)
    plt.close(fig)
