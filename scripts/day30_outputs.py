"""Read the Nov 1 (Day 30) run outputs and print the exact values for the post placeholders; draw the chart.

  python scripts/day30_outputs.py                                  # after any step; missing steps say "not run yet"
  python scripts/day30_outputs.py --credits-before 4950 --credits-after 4890
  python scripts/day30_outputs.py --rehearsal --png <scratch>/gnani_ownvoice.png ...   # stand-in / mock inputs

Placeholders (posts/day30-28_gnani.md, never edited here): update 2 [N] clips and [CREDITS]; update 3 the small
CPU model and teacher [RESULT] lines; update 4 [N] answers and Prisma v2.5 -> v3.0 [X] -> [Y]; update 5 the
[DECISION CODE]s and [LATENCY]. Every printed number comes from a file written by the run; the "suggested
wording" lines are drafts to edit, and words like "sounds close" ([3 WORDS]) are never generated.

Inputs (defaults; each is optional):
  clone run     artifacts/gnani_cache/jobs_demo_builder_voice.csv (+ the cached clips), artifacts/gnani_usage.jsonl
  credits       --credits-before/--credits-after, else artifacts/gnani_cache/credits.json {"before": .., "after": ..}
  trials (CPU)  artifacts/ivr_trials_ownvoice_<condition>_scores.csv  (python -m ivr_demo.trials ... --tag ownvoice_<condition>)
  teacher       artifacts/ownvoice_teacher_scores.csv                 (cm.teacher.score_folder, Modal or CPU)
  Prisma        artifacts/prisma_phrase_check.json                    (python -m ivr_demo.phrase_check --execute ...)
  live IVR      artifacts/ivr_live.json                               (python -m ivr_demo.demo --live ...)
Chart: posts/img/gnani_ownvoice.png (outside the repo): real vs clone scores per codec for both models, with the
dev-fixed FAR 1% (solid) and minDCF (dotted) thresholds. If any input is a mock or stand-in (``--rehearsal``, or a
file whose ``mode`` is mock), the chart is watermarked REHEARSAL and the default posts/ path is refused.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
XJOB = ROOT.parents[1]
DEFAULT_PNG = XJOB / "posts" / "img" / "gnani_ownvoice.png"
CONDITIONS = ("g711u", "amrnb_4k75")
COND_LABEL = {"g711u": "G.711 mu-law", "amrnb_4k75": "AMR-NB 4.75k (held out)", "nb_pcm": "clean 8 kHz", "gsm_fr": "GSM-FR (held out)"}
DECISIONS = {0: "Success", 1: "Spoof Failure", 2: "Voice Failure", 3: "Internal Error"}
# Chart tokens (dataviz reference palette, light surface; validated: all checks pass for the pair).
SURFACE, INK, INK2, GRID, REAL, CLONE = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3de", "#2a78d6", "#eb6834"


def _read_json(path: Path) -> dict | list | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def clone_section(jobs: Path, ledger: Path, since: str, credits: tuple[float | None, float | None]) -> list[str]:
    out = ["== update 2: the clone run =="]
    if not jobs.is_file():
        return out + [f"[N]: not run yet (no {jobs.relative_to(ROOT).as_posix() if jobs.is_relative_to(ROOT) else jobs})"]
    with jobs.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["kind"] == "vc_tts"]
    done = [r for r in rows if (ROOT / r["path"]).is_file()]
    wav = sum(r["path"].endswith(".wav") for r in done)
    mu = sum(r["path"].endswith(".mulaw") for r in done)
    out.append(f"[N] = {len(done)} clips ({wav} as 16 kHz WAV, {mu} synthesized straight to 8 kHz mu-law) of {len(rows)} planned")
    if ledger.is_file():
        calls: dict[str, int] = {}
        for line in ledger.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["ts"][:10] >= since:
                k = f"{r['endpoint']} ({r['model']}, HTTP {r['status']})"
                calls[k] = calls.get(k, 0) + 1
        out.append(f"REST calls in the ledger since {since}: {sum(calls.values())} " + (json.dumps(calls) if calls else ""))
        out.append("  (the realtime Prisma sessions are not in the ledger; the live IVR JSON counts them)")
    before, after = credits
    if before is not None and after is not None:
        spent = before - after
        out.append(f"[CREDITS] = {spent:g} credits ({before:g} before, {after:g} after, read on app.gnani.ai)"
                   + (f"; about {spent / len(done):.2f} per clip" if done else ""))
    else:
        out.append("[CREDITS]: not available (the API reports no usage; read the balance on app.gnani.ai before and after "
                   "and pass --credits-before/--credits-after)")
    return out


def cpu_scores(trials_dir: Path, conditions: tuple[str, ...], tag: str) -> pd.DataFrame | None:
    frames = []
    for c in conditions:
        p = trials_dir / f"ivr_trials_{tag}_{c}_scores.csv"
        if p.is_file():
            d = pd.read_csv(p)
            d["condition"] = c
            frames.append(d)
    return pd.concat(frames, ignore_index=True) if frames else None


def counts(label: pd.Series, accept: pd.Series) -> tuple[int, int, int, int]:
    b, s = label.eq("bonafide"), label.eq("spoof")
    return int((accept & b).sum()), int(b.sum()), int((accept & s).sum()), int(s.sum())


def model_lines(name: str, df: pd.DataFrame | None, accept_col: dict[str, str], conditions: tuple[str, ...]) -> tuple[list[str], dict]:
    if df is None:
        return [f"{name}: not run yet"], {}
    out, res = [f"{name}:"], {}
    for c in conditions:
        g = df[df.condition == c]
        if g.empty:
            out.append(f"   {COND_LABEL.get(c, c)}: no trials")
            continue
        for op, col in accept_col.items():
            gb, nb, gs, ns = counts(g.label, g[col].astype(bool))
            res[(c, op)] = (gb, nb, gs, ns)
            out.append(f"   {COND_LABEL.get(c, c)}, {op}: clones let in {gs}/{ns}, my real answers accepted {gb}/{nb}")
    return out, res


def trials_section(cpu: pd.DataFrame | None, teacher: pd.DataFrame | None, conditions: tuple[str, ...]) -> list[str]:
    out = ["== update 3: my real voice vs my clone (dev-fixed thresholds, nothing tuned on these clips) =="]
    if cpu is not None:
        cpu = cpu.copy()
        for op in ("far1", "min_dcf"):
            cpu[f"acc_{op}"] = cpu[f"code_{op}"].eq(0)
    lines, rc = model_lines("small CPU model (LFCC-LCNN lcnn8_aug, 170k params)", cpu,
                            {"dev FAR 1%": "acc_far1", "minDCF": "acc_min_dcf"}, conditions)
    out += lines
    lines, rt = model_lines("300M XLS-R + AASIST fine-tuned at 8 kHz (teacher)", teacher,
                            {"dev FAR 1%": "accept_far1", "minDCF": "accept_min_dcf"}, conditions)
    out += lines
    for name, r in (("small CPU", rc), ("teacher", rt)):
        if r:
            parts = [f"{COND_LABEL.get(c, c).split(' (')[0]}: {gs}/{ns} clones got in, {gb}/{nb} real accepted"
                     for (c, op), (gb, nb, gs, ns) in r.items() if op == "dev FAR 1%"]
            out.append(f"suggested [RESULT] ({name}, dev FAR 1%): " + "; ".join(parts))
    if cpu is not None and cpu.cm_llr.isna().any():
        out.append(f"note: {int(cpu.cm_llr.isna().sum())} CPU trials had under 1 s of speech (short_audio): neither accepted nor caught")
    return out


def phrase_section(path: Path) -> tuple[list[str], str | None]:
    out = ["== update 4: Prisma v2.5 vs v3.0 phrase check =="]
    d = _read_json(path)
    if d is None:
        return out + ["not run yet"], None
    s25, s30 = d["summary"]["v2.5"], d["summary"]["v3.0"]
    out.append(f"[N] = {d['n_answers']} spoken answers (digits + Hinglish), {d['channel']} line, language_code {d['language_code']}")
    out.append(f"[X] -> [Y] = {s25['match']}/{s25['n_scored']} -> {s30['match']}/{s30['n_scored']} (phrase match, the IVR's own rule)")
    out.append(f"digits right: {s25['digits_ok']}/{s25['n_scored']} -> {s30['digits_ok']}/{s30['n_scored']}; "
               f"mean edit distance {s25['mean_distance']} -> {s30['mean_distance']}; errors {s25['errors']} / {s30['errors']}")
    out.append(f"served_by: v2.5 {s25['served_by']}, v3.0 {s30['served_by']}; v3.0 opt-in confirmed: {d.get('v3_opt_in_confirmed')}")
    if d.get("v3_opt_in_confirmed") is False:
        out.append("DO NOT POST the comparison: the v3.0 responses do not report prisma-v3.0")
    if d.get("stopped"):
        out.append(f"run stopped early: {d['stopped']}")
    return out, d.get("mode")


def live_section(path: Path) -> tuple[list[str], str | None]:
    out = ["== update 5: end-to-end IVR =="]
    d = _read_json(path)
    if d is None:
        return out + ["not run yet"], None
    out.append(f"challenge: {d['challenge']} | operating point {d['operating_point']} (tau_llr {d['tau_llr']}), "
               f"channel {d['channel']}, identity gate {d['asv']}")
    for c in d["callers"]:
        who = "my voice" if c["caller"] == "genuine" else "my clone"
        out.append(f"[DECISION CODE] {who}: DecisionCode {c['DecisionCode']} ({DECISIONS.get(c['DecisionCode'], '?')}, "
                   f"reason {c['reason']}), StatusCode {c['StatusCode']}; transcript {c.get('transcript')!r}")
        others = ", ".join(f"{op}: {o['DecisionCode']} ({o['reason']})" for op, o in c.get("other_operating_points", {}).items())
        if others:
            out.append(f"   same call at other dev-fixed points: {others}")
        if c.get("latency_ms") is not None:
            out.append(f"[LATENCY] {who}: {c['latency_ms']} ms local decision (CM + fusion, after the transcript); "
                       f"Prisma end of speech to final transcript {c.get('stt_final_delay_ms')} ms")
    return out, d.get("mode")


def chart(cpu: pd.DataFrame | None, teacher: pd.DataFrame | None, conditions: tuple[str, ...], png: Path, rehearsal: bool) -> bool:
    if cpu is None and teacher is None:
        return False
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    fig, axes = plt.subplots(1, 2, figsize=(8, 4.5), dpi=200, facecolor=SURFACE)
    panels = (("Small CPU model (170k params)", "calibrated LLR", cpu, "cm_llr", "tau_far1", "tau_min_dcf"),
              ("XLS-R 300M fine-tuned at 8 kHz", "logit difference", teacher, "score", "tau_far1", "tau_min_dcf"))
    rng = np.random.default_rng(0)
    for ax, (title, ylab, df, col, t1, t2) in zip(axes, panels):
        ax.set_facecolor(SURFACE)
        ax.set_title(title, color=INK, fontsize=10, loc="left", pad=18)  # room for the per-cluster counts
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=INK2, labelsize=8)
        ax.set_ylabel(f"{ylab} (higher = more real)", color=INK2, fontsize=8)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.set_xticks(range(len(conditions)), [COND_LABEL.get(c, c).replace(" (held out)", "\n(held out)") for c in conditions])
        ax.set_xlim(-0.6, len(conditions) - 0.4)
        if df is None:
            ax.text(0.5, 0.5, "not run yet", transform=ax.transAxes, ha="center", color=INK2)
            continue
        tau1 = float(df[t1].dropna().iloc[0]) if t1 in df and df[t1].notna().any() else None
        for i, c in enumerate(conditions):
            g = df[df.condition == c]
            for label, dx, color, marker in (("bonafide", -0.17, REAL, "o"), ("spoof", 0.17, CLONE, "^")):
                gl = g[g.label == label]
                v = gl[col].dropna().to_numpy(float)
                ax.scatter(i + dx + rng.uniform(-0.06, 0.06, len(v)), v, s=22, color=color, marker=marker,
                           edgecolors=SURFACE, linewidths=0.8, zorder=3)
                if tau1 is not None and len(gl):  # direct label: how many of this cluster pass the FAR 1% threshold
                    ax.text(i + dx, 1.01, f"{int((gl[col] >= tau1).sum())}/{len(gl)}", transform=ax.get_xaxis_transform(),
                            ha="center", va="bottom", fontsize=7.5, color=INK)
        for tcol, style, name in ((t1, "-", "FAR 1%"), (t2, ":", "minDCF")):
            if tcol in df and df[tcol].notna().any():
                tau = float(df[tcol].dropna().iloc[0])
                ax.axhline(tau, color=INK2, linestyle=style, linewidth=1.2, zorder=2)
                ax.annotate(name, (0.0, tau), xycoords=("axes fraction", "data"), xytext=(3, 2),
                            textcoords="offset points", ha="left", va="bottom", fontsize=7, color=INK2)
    handles = [Line2D([], [], marker="o", linestyle="", color=REAL, label="my real voice"),
               Line2D([], [], marker="^", linestyle="", color=CLONE, label="my Gnani clone (vachana-vc-v1)")]
    fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=8, labelcolor=INK, ncol=2, bbox_to_anchor=(0.98, 0.99))
    fig.suptitle("Real vs clone over a simulated phone line", x=0.02, y=0.985, ha="left", color=INK, fontsize=12, weight="bold")
    ref = cpu if cpu is not None else teacher
    n = {lab: int((ref.label == lab).sum() / max(1, len(conditions))) for lab in ("bonafide", "spoof")}  # type: ignore[union-attr]
    fig.text(0.02, 0.012, f"{n['bonafide']} real answers and {n['spoof']} clones per codec. Above each cluster: how many score above the "
             "FAR 1% line (accepted).\nLines: thresholds fixed on ASVspoof 2019 dev, never tuned on these clips. Small sample.",
             color=INK2, fontsize=6.5, linespacing=1.4)
    if rehearsal:
        fig.text(0.5, 0.5, "REHEARSAL: stand-in clips, mock run", ha="center", va="center", rotation=20, fontsize=26,
                 color="#e34948", alpha=0.35, weight="bold")
    fig.tight_layout(rect=(0, 0.06, 1, 0.94))
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, facecolor=SURFACE)
    plt.close(fig)
    return True


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jobs", type=Path, default=ROOT / "artifacts" / "gnani_cache" / "jobs_demo_builder_voice.csv")
    ap.add_argument("--ledger", type=Path, default=ROOT / "artifacts" / "gnani_usage.jsonl")
    ap.add_argument("--since", default=date.today().isoformat(), help="count ledger calls from this date (UTC, YYYY-MM-DD)")
    ap.add_argument("--credits-before", type=float)
    ap.add_argument("--credits-after", type=float)
    ap.add_argument("--trials-dir", type=Path, default=ROOT / "artifacts")
    ap.add_argument("--tag", default="ownvoice", help="trials tag prefix: files are ivr_trials_<tag>_<condition>_scores.csv")
    ap.add_argument("--teacher", type=Path, default=ROOT / "artifacts" / "ownvoice_teacher_scores.csv")
    ap.add_argument("--phrase", type=Path, default=ROOT / "artifacts" / "prisma_phrase_check.json")
    ap.add_argument("--live", type=Path, default=ROOT / "artifacts" / "ivr_live.json")
    ap.add_argument("--conditions", nargs="+", default=list(CONDITIONS))
    ap.add_argument("--png", type=Path, default=DEFAULT_PNG)
    ap.add_argument("--rehearsal", action="store_true", help="inputs are stand-ins or mock: watermark the chart")
    a = ap.parse_args(argv)
    credits = (a.credits_before, a.credits_after)
    cfile = ROOT / "artifacts" / "gnani_cache" / "credits.json"
    if None in credits and cfile.is_file():
        c = json.loads(cfile.read_text())
        credits = (c.get("before"), c.get("after"))
    conds = tuple(a.conditions)
    cpu = cpu_scores(a.trials_dir, conds, a.tag)
    teacher = pd.read_csv(a.teacher) if a.teacher.is_file() else None
    lines = clone_section(a.jobs, a.ledger, a.since, credits)
    lines += trials_section(cpu, teacher, conds)
    pl, pmode = phrase_section(a.phrase)
    ll, lmode = live_section(a.live)
    lines += pl + ll
    rehearsal = a.rehearsal or "mock" in (pmode, lmode)
    if rehearsal:
        lines.insert(0, "*** REHEARSAL / MOCK INPUTS: nothing below may be posted ***")
    print("\n".join(lines))
    if rehearsal and a.png.resolve() == DEFAULT_PNG.resolve():
        print(f"refusing to write a rehearsal chart to {DEFAULT_PNG}: pass --png <scratch path>")
        return 1
    if chart(cpu, teacher, conds, a.png, rehearsal):
        print(f"chart: {a.png.as_posix()}")
    else:
        print("chart: skipped (no trial scores yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
