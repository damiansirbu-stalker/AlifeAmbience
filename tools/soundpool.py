#!/usr/bin/env python3
"""soundpool.py - Zone Soundscape build tooling.

Owns the pipeline that turns a set of read-only audio pools into a curated
selection and validates referential integrity. Standard library only; drives
ffprobe, ffmpeg (aspectralstats), and fpcalc (Chromaprint) as external CLIs.

Subcommands
  inventory   ffprobe every ogg in every pool  -> manifest.json
  select      dedupe by fingerprint + quality gate -> selection.json + ties.txt
  generate    emit sounds= lists into the channel LTX (phase 2; contract below)
  validate    bidirectional referential integrity (the release gate)

Design rules live in ../doc/architecture.md (invariants I1-I8). Key ones here:
  I5 quality = spectral truth (rolloff), not claimed bitrate; bitrate is tie-break.
  I6 never re-encode; select the least-degraded existing file and copy verbatim.

External tools are resolved from $PORTX_ROOT/packages (default C:/App/PORTX), or
$FFPROBE / $FFMPEG / $FPCALC overrides, or PATH.
"""

import argparse
import array
import json
import math
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORTX_ROOT = Path(os.environ.get("PORTX_ROOT", "C:/App/PORTX"))
DEF_JOBS = min(16, (os.cpu_count() or 4))

# tool -> (env var, portx package, exe name)
_TOOLS = {
    "ffprobe": ("FFPROBE", "ffmpeg", "ffprobe.exe"),
    "ffmpeg": ("FFMPEG", "ffmpeg", "ffmpeg.exe"),
    "fpcalc": ("FPCALC", "chromaprint", "fpcalc.exe"),
}


def tool(name):
    env, pkg, exe = _TOOLS[name]
    override = os.environ.get(env)
    if override:
        return override
    cand = PORTX_ROOT / "packages" / pkg / exe
    if cand.exists():
        return str(cand)
    found = shutil.which(name)
    if found:
        return found
    sys.exit(f"error: cannot find {name} (set ${env} or install to {cand})")


def run(argv):
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")


def pmap(fn, items, jobs):
    """Parallel map. subprocess calls release the GIL while waiting, so threads
    give real concurrency for the external-CLI workload."""
    items = list(items)
    if jobs <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        return list(ex.map(fn, items))


def load_config(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --- classification -------------------------------------------------------

def categorize(rel_path, categories):
    p = rel_path.replace("\\", "/").lower()
    for c in categories:
        for m in c["match"]:
            if m == "" or m.lower() in p:
                return c["name"], c.get("prefer", "any")
    return "other", "any"


def sound_key(rel_path):
    """Human-readable identity of a sound: parent dir + base name with a trailing
    _<digits> variant index stripped. Metadata only; sameness is decided by
    fingerprint, not by this key."""
    p = Path(rel_path.replace("\\", "/"))
    stem = p.stem.lower()
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        stem = parts[0]
    return f"{p.parent.as_posix()}::{stem}"


# --- probes ---------------------------------------------------------------

def probe(path):
    r = run([tool("ffprobe"), "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name,sample_rate,channels,duration,bit_rate",
             "-show_entries", "format=bit_rate,size", "-of", "json", path])
    if r.returncode != 0:
        return None
    try:
        j = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    st = (j.get("streams") or [{}])[0]
    fmt = j.get("format") or {}

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    br = num(st.get("bit_rate")) or num(fmt.get("bit_rate"))
    return {
        "codec": st.get("codec_name"),
        "sample_rate": int(num(st.get("sample_rate")) or 0),
        "channels": int(num(st.get("channels")) or 0),
        "duration": num(st.get("duration")) or num(fmt.get("duration")) or 0.0,
        "bit_rate": int(br) if br else 0,
        "size": int(num(fmt.get("size")) or 0),
    }


def fingerprint(path, length):
    r = run([tool("fpcalc"), "-raw", "-length", str(length), path])
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        if line.startswith("FINGERPRINT="):
            try:
                return [int(x) & 0xFFFFFFFF for x in line[12:].split(",") if x]
            except ValueError:
                return None
    return None


def fp_similarity(a, b):
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    bits = sum((a[i] ^ b[i]).bit_count() for i in range(n))
    return 1.0 - bits / (32.0 * n)


# --- PCM cross-correlation: the same-recording decider (architecture.md I3) -----
# Chromaprint proposes candidates (recall) but cannot decide - its similarity ranges
# for same-vs-distinct overlap (a distinct sound can score 1.0, a re-encode 0.93).
# md5 alone misses re-encodes. The decider is the normalized cross-correlation of the
# decoded waveforms: a re-encode correlates ~1.0, a genuinely distinct sound ~0. The
# constants below are FROZEN as validated (MANGLE=0 over the corpus); do not tune them
# without re-running the same-vs-distinct separation check.
PCM_RATE = 4000            # decode sample rate (Hz); enough to capture pitch + transients
PCM_ENV_FRAME = 100        # envelope frame (samples) for the coarse offset search
PCM_REFINE = 120           # sample window around the envelope offset for the fine search
PCM_REFINE_STEP = 6        # stride of the fine search
_PCM_SILENCE = 150         # |sample| below this is treated as silence when trimming ends


def decode_pcm(path):
    """Decode to a mono list of int16 samples at PCM_RATE, near-silence trimmed off
    both ends (so leading/trailing padding differences do not defeat alignment)."""
    r = subprocess.run([tool("ffmpeg"), "-v", "error", "-i", path, "-ac", "1",
                        "-ar", str(PCM_RATE), "-f", "s16le", "-"], capture_output=True)
    a = array.array("h")
    a.frombytes(r.stdout)
    a = a.tolist()
    lo, hi = 0, len(a)
    while lo < hi and abs(a[lo]) < _PCM_SILENCE:
        lo += 1
    while hi > lo and abs(a[hi - 1]) < _PCM_SILENCE:
        hi -= 1
    return a[lo:hi]


def _pcm_envelope(a):
    F = PCM_ENV_FRAME
    return [math.sqrt(sum(a[i + k] * a[i + k] for k in range(F)) / F)
            for i in range(0, len(a) - F, F)]


def _pcm_norm(v):
    if not v:
        return v
    m = sum(v) / len(v)
    d = [x - m for x in v]
    e = math.sqrt(sum(x * x for x in d)) or 1.0
    return [x / e for x in d]


def _pcm_best_offset(e1, e2):
    """Coarse alignment: envelope offset (in samples) maximizing envelope correlation."""
    a, b = _pcm_norm(e1), _pcm_norm(e2)
    if not a or not b:
        return 0
    bo, bs = 0, -2.0
    for off in range(-len(a) + 1, len(b)):
        s = sum(x * y for x, y in zip(a[max(0, off):], b[max(0, -off):]))
        if s > bs:
            bs, bo = s, off
    return bo * PCM_ENV_FRAME


def _pcm_pearson_at(a, b, off):
    if off >= 0:
        x, y = a[off:], b
    else:
        x, y = a, b[-off:]
    n = min(len(x), len(y))
    if n < 50:
        return 0.0
    x, y = x[:n], y[:n]
    mx, my = sum(x) / n, sum(y) / n
    sx = sy = sxy = 0.0
    for i in range(n):
        dx, dy = x[i] - mx, y[i] - my
        sx += dx * dx
        sy += dy * dy
        sxy += dx * dy
    return sxy / (math.sqrt(sx * sy) or 1.0)


def pcm_correlation(samples_a, samples_b):
    """Same-recording confidence in [-1, 1]: normalized cross-correlation of two decoded
    PCM signals (from decode_pcm), aligned by envelope offset then refined by Pearson
    over the overlap. ~1.0 = the same recording (re-encode); ~0 = a distinct sound.
    Robust to bitrate, codec and silence padding."""
    if not samples_a or not samples_b:
        return 0.0
    off = _pcm_best_offset(_pcm_envelope(samples_a), _pcm_envelope(samples_b))
    best = -2.0
    for o in range(off - PCM_REFINE, off + PCM_REFINE + 1, PCM_REFINE_STEP):
        r = _pcm_pearson_at(samples_a, samples_b, o)
        if r > best:
            best = r
    return best


def mean_rolloff(path):
    """Average spectral rolloff (Hz) over frames = true high-frequency content.
    Higher is better (less transcoded/upsampled). ametadata prints to stdout via
    file=-; the null muxer target is the OS null device (no temp file, no race
    under parallelism)."""
    r = run([tool("ffmpeg"), "-v", "error", "-i", path,
             "-af", "aspectralstats,ametadata=mode=print:file=-",
             "-f", "null", os.devnull])
    vals = []
    for line in r.stdout.splitlines():
        if ".rolloff=" in line:
            try:
                vals.append(float(line.split("=", 1)[1]))
            except ValueError:
                pass
    return sum(vals) / len(vals) if vals else 0.0


# --- inventory ------------------------------------------------------------

def cmd_inventory(args):
    cfg = load_config(args.config)
    cats = cfg["categories"]
    include = set(cfg.get("include_roots") or [])
    tasks = []
    for pool in cfg["pools"]:
        root = Path(pool["root"])
        if not root.exists():
            print(f"  WARN pool root missing: {pool['name']} -> {root}", file=sys.stderr)
            continue
        oggs = sorted(root.rglob("*.ogg"))
        if include:
            oggs = [f for f in oggs if f.relative_to(root).parts[0] in include]
        print(f"  {pool['name']}: {len(oggs)} oggs (ambient-scoped)", file=sys.stderr)
        for f in oggs:
            tasks.append((pool, root, f))

    def do(t):
        pool, root, f = t
        rel = f.relative_to(root).as_posix()
        info = probe(str(f))
        if info is None:
            return None
        cat, prefer = categorize(rel, cats)
        return {"pool": pool["name"], "priority": pool["priority"], "rel": rel,
                "abs": str(f), "category": cat, "prefer": prefer,
                "key": sound_key(rel), **info}

    out = [r for r in pmap(do, tasks, args.jobs) if r is not None]
    Path(args.manifest).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {args.manifest} ({len(out)} files, {len(tasks) - len(out)} unreadable)")


# --- select ---------------------------------------------------------------

def _fit(rec, q):
    """Hard fitness gate (invariant I4): correct codec and sample rate. Channel
    layout is a preference handled in ranking, not a gate - stereo beds are valid
    in the ambient system, and mono is only preferred for directional cues."""
    return (rec["codec"] == q["require_codec"]
            and rec["sample_rate"] == q["require_sample_rate"])


def _pref_rank(rec):
    """0 if the file matches its category's channel preference, 1 otherwise.
    'any' always matches. Used ahead of quality so the right SHAPE is chosen
    first, then the best-quality file within that shape."""
    pref = rec.get("prefer", "any")
    if pref == "any":
        return 0
    if pref == "mono":
        return 0 if rec["channels"] == 1 else 1
    if pref == "stereo":
        return 0 if rec["channels"] >= 2 else 1
    return 0


def _cluster(recs, fps, thr):
    """Split a (category, duration) bucket into same-sound clusters by fingerprint
    similarity. Files whose fingerprint failed become their own singletons."""
    clusters = []
    for r in recs:
        placed = False
        for cl in clusters:
            fa, fb = fps.get(id(r)), fps.get(id(cl[0]))
            if fa and fb and fp_similarity(fa, fb) >= thr:
                cl.append(r)
                placed = True
                break
        if not placed:
            clusters.append([r])
    return clusters


def _pick(grp, q):
    """Apply the quality gate to one same-sound cluster.
    Returns (winner, tie, fit). fit is False when no candidate passes fitness."""
    fit = [r for r in grp if _fit(r, q)]
    pool = fit or grp
    # right channel shape first, then true quality, then bitrate, size, priority
    ranked = sorted(pool, key=lambda r: (_pref_rank(r), -(r.get("rolloff") or 0),
                                         -r["bit_rate"], -r["size"], r["priority"]))
    winner = ranked[0]
    tie = False
    if fit and len(ranked) > 1:
        b = ranked[1]
        same_shape = _pref_rank(winner) == _pref_rank(b)
        close_roll = abs((winner.get("rolloff") or 0) - (b.get("rolloff") or 0)) < 250
        close_br = abs(winner["bit_rate"] - b["bit_rate"]) < 16000
        tie = same_shape and close_roll and close_br
    return winner, (tie or not fit), bool(fit)


def cmd_select(args):
    cfg = load_config(args.config)
    q = cfg["quality"]
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    # Bucket cross-pool candidates by (category, rounded duration) so the same
    # sound meets even under different names; the fingerprint confirms sameness.
    buckets = {}
    for rec in manifest:
        db = round(rec["duration"] / q["duration_bucket_seconds"])
        buckets.setdefault((rec["category"], db), []).append(rec)

    # Fingerprint every file that shares a bucket with others (parallel).
    need_fp = [r for recs in buckets.values() if len(recs) > 1 for r in recs]
    print(f"  fingerprinting {len(need_fp)} candidates ({args.jobs} jobs)...", file=sys.stderr)
    fp_vals = pmap(lambda r: fingerprint(r["abs"], q["fpcalc_length_seconds"]), need_fp, args.jobs)
    fps = {id(r): v for r, v in zip(need_fp, fp_vals)}

    # Cluster within each bucket.
    clusters = []
    for recs in buckets.values():
        clusters.extend(_cluster(recs, fps, q["dup_similarity_threshold"]))

    # Rolloff only for eligible files in multi-candidate clusters (parallel).
    need_roll = [r for cl in clusters if len(cl) > 1 for r in cl if _fit(r, q)]
    print(f"  measuring rolloff on {len(need_roll)} contested files ({args.jobs} jobs)...", file=sys.stderr)
    roll_vals = pmap(lambda r: mean_rolloff(r["abs"]), need_roll, args.jobs)
    for r, v in zip(need_roll, roll_vals):
        r["rolloff"] = v

    selection, ties, nofit = [], [], 0
    for cl in clusters:
        winner, tie, fit = _pick(cl, q)
        if not fit:
            nofit += 1
        selection.append({
            "key": winner["key"], "category": winner["category"],
            "prefer": winner["prefer"], "fit": fit, "tie": tie,
            "winner": {"pool": winner["pool"], "rel": winner["rel"], "abs": winner["abs"],
                       "bit_rate": winner["bit_rate"], "sample_rate": winner["sample_rate"],
                       "channels": winner["channels"], "rolloff": winner.get("rolloff")},
            "alternates": [{"pool": r["pool"], "rel": r["rel"], "bit_rate": r["bit_rate"]}
                           for r in cl if r is not winner],
        })
        if tie or not fit:
            tag = "TIE" if fit else "NO-FIT"
            ties.append(f"{tag}\t{winner['category']}\t{winner['key']}\t"
                        + " | ".join(f"{r['pool']}:{r['rel']}" for r in cl))

    Path(args.selection).write_text(json.dumps(selection, indent=1), encoding="utf-8")
    Path(args.ties).write_text("\n".join(ties), encoding="utf-8")
    print(f"wrote {args.selection} ({len(selection)} sounds; {nofit} no-fit; "
          f"{sum(1 for s in selection if s['tie'] and s['fit'])} ties) and {args.ties}")


# --- validate -------------------------------------------------------------

def _ltx_refs(ltx_text):
    refs = set()
    for line in ltx_text.splitlines():
        line = line.split(";", 1)[0]
        if "sounds" in line and "=" in line:
            rhs = line.split("=", 1)[1]
            for tok in rhs.split(","):
                tok = tok.strip().replace("\\", "/")
                if tok and tok != "ambient/no_sound":
                    refs.add(tok)
    return refs


def _expand(ref, roots):
    """A sounds= entry is a stem without .ogg. Resolve against the VFS roots (our
    mod first, then lower-priority mods like 304); the channel files list each
    variant explicitly, so a single exact match per root is the normal case."""
    found = set()
    for root in roots:
        cand = root / (ref + ".ogg")
        if cand.exists():
            found.add((root, cand))
    return found


def cmd_validate(args):
    roots = [Path(r) for r in args.sounds_root]
    refs = _ltx_refs(Path(args.channels).read_text(encoding="utf-8", errors="replace"))
    dangling = []
    referenced = set()  # (root, path)
    for ref in sorted(refs):
        files = _expand(ref, roots)
        if not files:
            dangling.append(ref)
        referenced |= files
    orphans = []
    if args.check_orphans:
        own = roots[0]  # only our own mod's files can be orphans; lower mods are shared
        ref_own = {p for (r, p) in referenced if r == own}
        for f in own.rglob("*.ogg"):
            if f not in ref_own:
                orphans.append(f.relative_to(own).as_posix())
    print(f"refs={len(refs)}  resolved={len(refs) - len(dangling)}  "
          f"dangling={len(dangling)}  orphans={len(orphans)}")
    if dangling:
        print("\nDANGLING (referenced, no file):")
        for r in dangling:
            print(f"  {r}")
    if orphans:
        print(f"\nORPHANS (file, never referenced): {len(orphans)}")
        for o in orphans[:50]:
            print(f"  {o}")
        if len(orphans) > 50:
            print(f"  ... and {len(orphans) - 50} more")
    sys.exit(1 if dangling else 0)


# --- generate (phase 2) ---------------------------------------------------

def cmd_generate(args):
    """Build our sound_channels.ltx from a base (304's proven structure) by
    refilling the channels named in channels.json from the selection, and copy
    the chosen files into gamedata/sounds/. Distances and periods are inherited
    from the base verbatim; only the sounds= lines of filled channels change."""
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    sel = json.loads(Path(args.selection).read_text(encoding="utf-8"))

    by_cat = {}
    for s in sel:
        if s["fit"]:
            by_cat.setdefault(s["category"], []).append(s["winner"])
    for lst in by_cat.values():
        lst.sort(key=lambda w: (-w["bit_rate"], -(w.get("rolloff") or 0)))

    base = Path(spec["base"]).read_text(encoding="utf-8", errors="replace")
    sounds_out = Path(args.sounds_out)
    copied = 0
    for chan, rule in spec["fill"].items():
        cands = by_cat.get(rule["category"], [])
        if rule.get("match"):
            rx = re.compile(rule["match"], re.I)
            cands = [w for w in cands if rx.search(w["rel"])]
        if rule.get("prefer") == "mono":
            cands = [w for w in cands if w["channels"] == 1] or cands
        elif rule.get("prefer") == "stereo":
            cands = [w for w in cands if w["channels"] >= 2] or cands
        chosen = cands[:rule.get("limit", 40)]
        if not chosen:
            print(f"  WARN no candidates for [{chan}]", file=sys.stderr)
            continue
        stems = []
        for w in chosen:
            dst = sounds_out / w["rel"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(w["abs"], dst)
                copied += 1
            stems.append(w["rel"][:-4].replace("/", "\\"))  # drop .ogg
        pat = re.compile(r"(\[" + re.escape(chan) + r"\][^\[]*?\bsounds\s*=)[^\r\n]*", re.S)
        base, n = pat.subn(lambda m: m.group(1) + " " + ", ".join(stems), base, count=1)
        if n == 0:
            print(f"  WARN channel [{chan}] not found in base", file=sys.stderr)
        else:
            print(f"  filled [{chan}] with {len(stems)} sounds", file=sys.stderr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(base, encoding="utf-8")
    print(f"wrote {out}; copied {copied} new files into {sounds_out}")


# --- cli ------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Zone Soundscape build tooling")
    ap.add_argument("--config", default=str(HERE / "pools.json"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("inventory", help="ffprobe every ogg -> manifest.json")
    p.add_argument("--manifest", default=str(HERE / "manifest.json"))
    p.add_argument("--jobs", type=int, default=DEF_JOBS)
    p.set_defaults(func=cmd_inventory)

    p = sub.add_parser("select", help="dedupe + quality gate -> selection.json")
    p.add_argument("--manifest", default=str(HERE / "manifest.json"))
    p.add_argument("--selection", default=str(HERE / "selection.json"))
    p.add_argument("--ties", default=str(HERE / "ties.txt"))
    p.add_argument("--jobs", type=int, default=DEF_JOBS)
    p.set_defaults(func=cmd_select)

    mod = HERE.parent
    p = sub.add_parser("generate", help="build sound_channels.ltx + copy content")
    p.add_argument("--spec", default=str(HERE / "channels.json"))
    p.add_argument("--selection", default=str(HERE / "selection.json"))
    p.add_argument("--out", default=str(mod / "gamedata/configs/environment/sound_channels.ltx"))
    p.add_argument("--sounds-out", default=str(mod / "gamedata/sounds"))
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("validate", help="bidirectional referential integrity")
    p.add_argument("--channels", required=True, help="sound_channels.ltx to check")
    p.add_argument("--sounds-root", required=True, nargs="+",
                   help="VFS sounds/ roots, our mod first then lower-priority mods")
    p.add_argument("--check-orphans", action="store_true")
    p.set_defaults(func=cmd_validate)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
