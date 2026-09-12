"""AlifeAmbience mastering mill: the hand-authored config is the source of truth; this tool
materializes, masters, reports, and proves what the config says. It never chooses content.

The config (sound_channels.ltx, ambient_channels/*, ambients/*) is authored by hand
(doc/architecture.md: the channel is the unit of curation). Content choices live in the config and in
sources.py (DISPOSITIONS, DEPLOY_EXTRA). The mill's stages:

  materialize  pull exactly the referenced files from the source packs into gamedata/sounds,
               delete deployed files nothing references (deployed set == referenced set)  -> manifest.json
  fmt          mechanical config guard: dedup pool tokens, normalize preset lines, strip refs to
               deleted channels/files, cap spawn distances, FAIL any pool line over LINE_CAP
  fold         stereo -> mono (re-encode) + resample off-rate to 44100                    -> fold_blobs
  level        crest-inverted min floor + loudness band, one crest+LUFS pass              -> level_cache
  fingerprint  acoustic-duplicate WARNING report (Chromaprint); the curator resolves      -> stdout
  dead         dead-audio report (content at/below DEAD_LUFS); the curator excludes       -> stdout
  verify       the gate ledger (closure + retention + density + veto + load rules, 18 gates) -> ledger.tsv
  audit        wired min/felt-far ratio + crushed share (acceptance report)               -> stdout
  stage NAME   materialize a source folder under sounds/stage/ for in-game audition
  unstage      remove the whole stage tree
  import [SRC] one-time config baseline from a source pack's own sound-routing config (explicit only,
               refuses over an existing config; default source: the Amplified spine)
  all          materialize -> fmt -> fold -> level -> fingerprint -> dead -> verify -> audit

Audibility is an ENGINE problem, not loudness: stereo plays 2D, min 1-2 is crushed by OpenAL, quiet
content stays quiet. Fixed by lossless blob edits keyed to an ear calibration: fold stereo->mono; a
crest-inverted min-distance floor; a base_volume loudness BAND to the ear-anchored -30/-36 floors and
-24/-28 ceilings. See doc/library/anomaly/internals/sound-source-and-emitter.md. Strike files
(DEPLOY_EXTRA, sounds/nature/) get the fold only: the engine overrides their attenuation range per
strike (thunderbolt.cpp:235), so blob distances do nothing there.
"""
import os, sys, json, hashlib, shutil, re, struct, subprocess, math, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
GD = os.path.join(REPO, "gamedata")
sys.path.insert(0, HERE)
import sources  # noqa

# only these sound roots are ambience-scope in a source pack; excludes weapons/voice/monsters/etc.
# /sounds/nature/ is the engine thunderbolt strike set (vanilla paths, thunderbolts.ltx `sound=`).
AMBIENT_MARKERS = ("/sounds/ambient/", "/sounds/ambience_exp/", "/sounds/nature/")
# packs never swept for path resolution (huge full unpacks / proven fully redundant)
RESOLVE_SKIP = {"vanilla", "ShrikeInterior"}

ENV = os.path.join(GD, "configs", "environment")
PRESETS = os.path.join(ENV, "ambients", "presets")
LEVELS = os.path.join(ENV, "ambients")
CHANNEL_FILES = [os.path.join(ENV, "ambient_channels", "backgrounds.ltx"),
                 os.path.join(ENV, "ambient_channels", "blowout_channels.ltx"),
                 os.path.join(ENV, "sound_channels.ltx")]
SC = os.path.join(ENV, "sound_channels.ltx")
SROOT = os.path.join(GD, "sounds")
META_SCRIPT = os.path.join(GD, "scripts", "aa_sound_metadata.script")
STAGE_DIR = "stage"                     # sounds/stage/<family>: audition staging, exempt from gates

# The AtmosFear ambient-state vocabulary (the weather matrix columns). Stock Anomaly 1.5.3 and
# Atmospherics both emit exactly this set (both weather trees swept 2026-09-03).
WEATHER_STATES = ["day", "morning", "evening", "night", "rain", "rain_day", "rain_night",
                  "storm_day", "storm_night", "tuman", "tuman_night", "indoor_underground"]
UNDERGROUND_STATE = "indoor_underground"
# The System B volume table (sound_ambient.script:147-165): an `indoor` channel plays at 0.0 in an
# outdoor state, an outdoor channel at 0.3 in an underground one. Gate 15 uses the state split.
UNDERGROUND_STATES = {"indoor_underground", "indoor", "indoor_x8"}
# thunderbolt collections the active weather mod references (Atmospherics weathers sweep, 2026-08-31)
# vs the collections the base game defines (vanilla thunderbolt_collections.ltx). Gate 10.
COLLECTIONS_REQUIRED = {"collection_close", "collection_default", "collection_distant"}
COLLECTIONS_BASE = {"collection_close", "collection_distant", "collection_default",
                    "collection_stancia", "collection_surge", "collection_test"}

# The base game's playable level set (game_maps_single.ltx sections carrying a `weathers` key,
# vanilla 1.5.3 sweep 2026-09-03). Gate 12: every one must bind an ambients/<level>.ltx, else the
# level plays vanilla wiring through the MO2 VFS (the 9 labs, found 2026-09-03) or a bare
# ambients.ltx fallback with zero dynamic layers (y04_pole).
LEVELS_BASE = {
    "jupiter", "k00_marsh", "k01_darkscape", "k02_trucks_cemetery", "l01_escape",
    "l02_garbage", "l03_agroprom", "l03u_agr_underground", "l04_darkvalley", "l04u_labx18",
    "l05_bar", "l06_rostok", "l07_military", "l08_yantar", "l08u_brainlab",
    "l09_deadcity", "l10_limansk", "l10_radar", "l10u_bunker", "l10_red_forest",
    "l11_hospital", "l11_pripyat", "l12_stancia", "l12_stancia_2", "l13_generators",
    "l12u_sarcofag", "l12u_control_monolith", "l13u_warlab", "zaton", "jupiter_underground",
    "pripyat", "labx8", "fake_start", "y04_pole",
}
LEVELS_EXEMPT = {"fake_start"}   # the menu background level; never played

# The effect-id vocabulary (the third weather coupling next to ambient states and collections).
# effect_0..9 are defined by vanilla effects.ltx AND Atmospherics' (both swept 2026-09-03);
# blowout_effect_01..48 come from vanilla blowout_effects.ltx via the effects.ltx include (both
# editions). An `effects =` ref outside this set is a CTD: create_effect reads life_time with a
# throwing r_float (Environment_misc.cpp:119-146). Gate 17.
EFFECTS_BASE = ({f"effect_{i}" for i in range(10)}
                | {f"blowout_effect_{i:02d}" for i in range(1, 49)})

# the engine reads each `sounds =` value into a fixed ~4096 buffer (SoundRender_Core.cpp:249,
# r_stringZ; FS.cpp:467 asserts sz < tgt_sz). A line over the buffer is a hard CTD on config load.
LINE_CAP = 3900

# per-state density budgets (events per minute), keyed by state class. Armed 2026-09-09 as LOUD
# regression ceilings (roughly 1.8x the measured round-robin-capped max per class), a guard against
# a future density blowout - NOT the tight ear-calibrated budget (doc/architecture.md: Density). The
# ear tightens these once the player calibration sets real values. {} = report-only.
# The epm sum excludes no_sound channels (they fire the scheduler but produce silence); the ceilings stay
# loose regression guards that cannot false-fail. Tighten to the ear-calibrated budgets via the player.
DENSITY_BUDGET = {
    "storm_day": 80, "storm_night": 80, "pre_storm": 75,
    "night": 65, "evening": 65, "morning": 65, "day": 65,
    "rain": 60, "rain_day": 60, "rain_night": 60,
    "tuman": 60, "tuman_day": 60, "tuman_night": 60,
    "indoor": 40, "indoor_underground": 40, "indoor_x8": 40,
}
ENTRY_BURST_MS = 15000     # a channel with period0 below this fires within the state's entry window

# Gentle per-category spawn-distance cap: a category's channels should not spawn TOO far (System B felt ~
# max_distance/2). Channel-name keyed, lower-only, guarded so max stays > min (engine assert). Applied by
# fmt, not by hand. Values are ear-tune starting points, like the loudness floors.
SPAWN_CAP = {"wind": 130.0}   # wind 200 -> 130 (felt ~100 -> ~65): nudge the far ones without collapsing them

# AlifeSpooks static veto overlay (gate 11): DLTX `<sounds` element removals applied to OUR resolved
# sound_channels.ltx at load. Any pool path listed there would be silently stripped in-game.
SPOOKS_VETO = os.path.join(os.path.dirname(REPO), "AlifeSpooks", "gamedata", "configs",
                           "environment", "mod_sound_channels_alifespooks.ltx")


def _read(p):
    return open(p, encoding="utf-8", errors="replace").read()


def _hash(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _iter_oggs(root):
    for dp, _, fns in os.walk(root):
        dpn = (dp + os.sep).replace("\\", "/").lower()
        if not any(m in dpn for m in AMBIENT_MARKERS):
            continue
        for fn in fns:
            if fn.lower().endswith(".ogg"):
                full = os.path.join(dp, fn)
                # relative path under sounds/ (the X-Ray sound key, forward-slashed, lowercased)
                i = full.lower().replace("\\", "/").find("/sounds/")
                rel = full.replace("\\", "/")[i + len("/sounds/"):]
                yield full, rel


def _load_hashes():
    p = os.path.join(HERE, "hashes.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def _save_hashes(h):
    json.dump(h, open(os.path.join(HERE, "hashes.json"), "w"))


def _tok_ok(t):
    t = t.strip().replace("\\", "/").lower()
    # a real sound path: has a folder separator, no key/space garbage, not the silent placeholder
    if not t or t == "ambient/no_sound" or "=" in t or " " in t or "\t" in t or "/" not in t:
        return None
    return t


def _defined_channels():
    ch = set()
    for f in CHANNEL_FILES:
        if os.path.exists(f):
            ch |= {m.lower() for m in re.findall(r"^\s*\[([A-Za-z0-9_]+)\]", _read(f), re.M)}
    return ch


def _channel_paths():
    paths = set()
    for f in CHANNEL_FILES:
        if os.path.exists(f):
            # anchor to a line that STARTS with `sounds`/`soundsN` (not add_sounds, not `ambient =`)
            for m in re.findall(r"(?im)^\s*sounds\d*\s*=\s*(.+)$", _read(f)):
                for one in re.split(r"[,;]", m):
                    t = _tok_ok(one)
                    if t:
                        paths.add(t)
    return paths


def _preset_refs():
    # channels referenced anywhere in the ambient chain: the per-state presets AND ambients.ltx
    # (the master [day]/[night]/... states, whose `sound_channels = default_ambient_*` are otherwise
    # invisible -- pruning them = a "can't open section" CTD).
    refs = set()
    files = [os.path.join(PRESETS, fn) for fn in os.listdir(PRESETS)]
    amb = os.path.join(ENV, "ambients.ltx")
    if os.path.exists(amb):
        files.append(amb)
    for pp in files:
        for m in re.findall(r"(?im)^\s*sound_channels(?:_dynamic)?\s*=\s*(.+)$", _read(pp)):
            for one in re.split(r"[,;]", m):
                one = one.strip().lower()
                if one and "=" not in one and " " not in one:
                    refs.add(one)
    return refs


def _extra_targets():
    """deploy-rel (lower) -> (source name, source rel) for the curated extra deploys (strike set)."""
    out = {}
    for src, src_rel, dst_rel, _reason in sources.DEPLOY_EXTRA:
        out[dst_rel.replace("\\", "/").lower()] = (src, src_rel)
    return out


def _iter_deployed():
    for dp, _, fns in os.walk(SROOT):
        for fn in fns:
            if fn.lower().endswith(".ogg"):
                full = os.path.join(dp, fn)
                rel = os.path.relpath(full, SROOT).replace("\\", "/")
                yield full, rel[:-4].lower()


def _is_staged(rel_lc):
    return rel_lc.startswith(STAGE_DIR + "/")


# ---- import: one-time baseline from the spine's own config (the old deploy stage's config half) ----
# The sound-routing config subset a baseline import copies, and the bundled non-sound logic it NEVER
# copies (thunderbolt/weather/surge configs fight the weather mod). Import is a mechanical copy of the
# spine author's OWN wiring; curation then owns the result. Explicit-only, never part of `all`, and it
# refuses to touch an existing config.
IMPORT_SOURCE = "Amplified"
KEEP_CONFIG_DIRS = [
    "configs/environment/ambients",
    "configs/environment/ambient_channels",
]
KEEP_CONFIG_FILES = [
    "configs/environment/ambients.ltx",
    "configs/environment/sound_channels.ltx",
]
DROP_CONFIG_RE = re.compile(
    r"(dynamic_weather_graphs|thunderbolt|weather_effects|surge_manager|psi_storm_manager"
    r"|mod_system_|mod_animations_settings)", re.I)


def cmd_import():
    """import [source] - bootstrap the config baseline from a source pack's own sound-routing config
    (default: the Amplified spine). Refuses if any config file already exists: the authored config is
    the source of truth and an import must never overwrite curation."""
    src_name = sys.argv[2] if len(sys.argv) > 2 else IMPORT_SOURCE
    gd_src = dict(sources.mods()).get(src_name)
    if not gd_src or not os.path.isdir(gd_src):
        raise SystemExit(f"unknown or absent source {src_name} (see sources.py)")
    existing = [f for f in CHANNEL_FILES + [os.path.join(ENV, "ambients.ltx")] if os.path.exists(f)]
    if existing or os.path.isdir(PRESETS):
        raise SystemExit("import: config already exists - the authored config is the source of truth; "
                         "remove it deliberately before re-importing")
    copied = 0
    src_root = gd_src.replace("/", os.sep)
    for base in KEEP_CONFIG_DIRS:
        src = os.path.join(src_root, base.replace("/", os.sep))
        for dp, _dirs, fns in os.walk(src):
            for fn in fns:
                if not fn.lower().endswith(".ltx") or DROP_CONFIG_RE.search(fn):
                    continue
                full = os.path.join(dp, fn)
                rel = os.path.relpath(full, src_root)
                dst = os.path.join(GD, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(full, dst)
                copied += 1
    for rel in KEEP_CONFIG_FILES:
        full = os.path.join(src_root, rel.replace("/", os.sep))
        if os.path.exists(full) and not DROP_CONFIG_RE.search(os.path.basename(full)):
            dst = os.path.join(GD, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(full, dst)
            copied += 1
    print(f"  import: {copied} sound-routing ltx copied from {src_name}; the config is now yours to curate")


# ---- materialize: deployed set == referenced set ---------------------------------------------------

def _source_index():
    """rel(lower) -> [(source name, full path, md5)] over all resolvable packs, registry order.
    md5s come from the hash cache (hashes.json) and are computed lazily only on conflicts. PICK_SKIP
    (source, rel-prefix) pairs drop a pack's copy of a path, so a later-registry pack wins the pick."""
    skip = [(s, p.replace("\\", "/").lower()) for s, p in sources.PICK_SKIP]
    idx = {}
    for name, gd in sources.mods():
        if name in RESOLVE_SKIP:
            continue
        if not os.path.isdir(gd):
            continue
        for full, rel in _iter_oggs(gd):
            rl = rel.lower()
            if any(s == name and rl.startswith(p) for s, p in skip):
                continue
            idx.setdefault(rl, []).append((name, full))
    return idx


def cmd_materialize():
    """Deploy exactly what the config + DEPLOY_EXTRA reference; remove what nothing references.
    A referenced path is resolved across the source packs in registry order; a path present in
    several packs with DIFFERENT bytes is a duplicate-pick conflict, reported for the curator."""
    refs = _channel_paths()
    extra = _extra_targets()
    idx = _source_index()
    cache = _load_hashes()

    # expand folder refs against the source index and the deployed tree
    want_files = set(p for p in refs if (p + ".ogg") in idx or
                     os.path.exists(os.path.join(SROOT, p.replace("/", os.sep) + ".ogg")))
    want_dirs = refs - want_files
    for rel in idx:
        d = os.path.dirname(rel[:-4] if rel.endswith(".ogg") else rel)
        # a folder ref pulls every source ogg under it
        if any(d == wd or d.startswith(wd + "/") for wd in want_dirs):
            want_files.add(rel[:-4])
    want_ogg = {p + ".ogg" for p in want_files} | set(extra.keys())

    # PICK_SKIP redirects a referenced path to a later pack, so an already-deployed file may now be the
    # wrong source. Verify those paths' AUDIO against the current winner and re-pull on mismatch (the
    # deployed blob is rewritten by level, so compare audio pages, not full bytes). Non-redirected paths
    # keep the fast exists -> skip: their source never changes within a deployed tree.
    skip_prefixes = [p.replace("\\", "/").lower() for _s, p in sources.PICK_SKIP]

    copied = conflicts = repulled = 0
    for rel in sorted(want_ogg):
        dst = os.path.join(SROOT, rel.replace("/", os.sep))
        redirected = any(rel.lower().startswith(p) for p in skip_prefixes)
        if os.path.exists(dst) and not redirected:
            continue
        if rel in extra:
            name, src_rel = extra[rel]
            src_gd = dict(sources.mods()).get(name)
            cand = [(name, os.path.join(src_gd, "sounds", src_rel.replace("/", os.sep)))] if src_gd else []
        else:
            cand = idx.get(rel, [])
        cand = [(n, f) for n, f in cand if os.path.exists(f)]
        if not cand:
            continue                                   # gate 4 (missing path) will report it
        if len(cand) > 1:
            md5s = set()
            for _n, f in cand:
                if f not in cache:
                    cache[f] = _hash(f)
                md5s.add(cache[f])
            if len(md5s) > 1:
                conflicts += 1
                print(f"  CONFLICT {rel}: differing bytes in {[n for n, _ in cand]} "
                      f"(registry order wins: {cand[0][0]})")
        win = cand[0][1]
        if os.path.exists(dst):                        # reached for a redirected path: keep only if audio matches
            if _hash_audio(dst) == _hash_audio(win):
                continue
            repulled += 1
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(win, dst)
        copied += 1

    # deployed set == referenced set: delete what nothing references (it stays in the packs;
    # retention gate 7 demands a disposition for its absence). A folder keeps its files only when a
    # channel references the FOLDER as a token (random-pick ref), never because a sibling file is
    # referenced - that leak is how unreferenced strike claps once sat deployed invisibly.
    removed = 0
    for full, rel_lc in list(_iter_deployed()):
        if _is_staged(rel_lc):
            continue
        d = os.path.dirname(rel_lc)
        if (rel_lc in want_files or rel_lc + ".ogg" in extra
                or any(d == wd or d.startswith(wd + "/") for wd in want_dirs)):
            continue
        os.remove(full)
        removed += 1
    for dp, _, _ in os.walk(SROOT, topdown=False):
        try:
            if not os.listdir(dp):
                os.rmdir(dp)
        except OSError:
            pass
    _save_hashes(cache)

    manifest = {}
    for full, rel_lc in _iter_deployed():
        if _is_staged(rel_lc):
            continue
        srcs = idx.get(rel_lc + ".ogg") or []
        manifest[rel_lc] = {"source": srcs[0][0] if srcs else "deployed"}
    json.dump(manifest, open(os.path.join(HERE, "manifest.json"), "w"), indent=1)
    print(f"  materialize: copied {copied} ({repulled} re-pulled over a redirected stale file), "
          f"removed {removed} unreferenced, {conflicts} duplicate-pick conflicts, {len(manifest)} deployed")


# ---- fmt: mechanical config guard ------------------------------------------------------------------

def _cap_spawn_distances():
    """Cap each channel's spawn max_distance to its category cap. Only lowers a max above the cap; never
    raises; keeps max > min. Channel-name keyed (SPAWN_CAP)."""
    capped = 0
    for f in CHANNEL_FILES:
        if not os.path.exists(f):
            continue
        out, cap, cmin = [], None, 0.0
        for ln in _read(f).split("\n"):
            mh = re.match(r"\s*\[([^\]]+)\]", ln)
            if mh:
                nm = mh.group(1).lower()
                cap = next((c for k, c in SPAWN_CAP.items() if k in nm), None)
                cmin = 0.0
            mn = re.match(r"\s*min_distance\s*=\s*([\d.]+)", ln, re.I)
            if mn:
                cmin = float(mn.group(1))
            mx = re.match(r"(\s*max_distance\s*=\s*)([\d.]+)", ln, re.I)
            if mx and cap is not None:
                cur = float(mx.group(2))
                lim = max(cap, cmin + 10.0)          # keep max > min (engine asserts max > min, strict)
                if cur > lim:
                    ln = f"{mx.group(1)}{lim:g}"
                    capped += 1
            out.append(ln)
        open(f, "w", encoding="utf-8").write("\n".join(out))
    print(f"  spawn-cap: capped {capped} channel max_distances (wind <= {SPAWN_CAP.get('wind')})")


def _normalize_dynamic(defined):
    """Preset sound_channels / _dynamic lines: dedupe tokens, drop `;` comment traps, strip refs to
    channels that no longer exist (a deleted channel must not dangle in any preset)."""
    fixed = stripped = 0
    for fn in os.listdir(PRESETS):
        pp = os.path.join(PRESETS, fn)
        out = []
        for ln in _read(pp).split("\n"):
            m = re.match(r"(\s*sound_channels(?:_dynamic)?\s*=\s*)(.+)$", ln, re.I)
            if not m:
                out.append(ln)
                continue
            seen, chans = set(), []
            for tok in re.split(r"[,;]", m.group(2)):
                tok = tok.strip()
                if not tok or tok.lower() in seen:
                    continue
                if tok.lower() not in defined:
                    stripped += 1
                    continue
                seen.add(tok.lower())
                chans.append(tok)
            new = m.group(1) + ", ".join(chans)
            if new != ln:
                fixed += 1
            out.append(new)
        open(pp, "w", encoding="utf-8").write("\n".join(out))
    print(f"  normalize: fixed {fixed} preset lines, stripped {stripped} refs to deleted channels")


def cmd_fmt():
    """Mechanical guard over the hand-authored config. Curation decides the sets; fmt guards the
    strings: dedup pool tokens, normalize preset lines, strip dangling refs, cap spawn distances,
    FAIL on any pool line over LINE_CAP (the 4096 ini buffer is a CTD)."""
    over = []
    for f in CHANNEL_FILES:
        if not os.path.exists(f):
            continue
        out = []
        for ln in _read(f).split("\n"):
            mm = re.match(r"(\s*sounds\d*\s*=\s*)(\S.*)$", ln, re.I)
            if mm:
                seen, keys = [], set()
                for one in re.split(r"[,;]", mm.group(2)):
                    e = one.strip()
                    if not e:
                        continue
                    k = e.replace("\\", "/").lower()
                    if k not in keys:
                        keys.add(k)
                        seen.append(e)
                ln = mm.group(1) + ", ".join(seen)
                if len(ln) > LINE_CAP:
                    over.append((os.path.basename(f), seen[0] if seen else "?", len(ln)))
            out.append(ln)
        open(f, "w", encoding="utf-8").write("\n".join(out))
    _normalize_dynamic(_defined_channels())
    _cap_spawn_distances()
    if over:
        for f, first, n in over:
            print(f"  FMT FAIL {f}: pool line {n} chars > {LINE_CAP} (starts {first}) - split the channel")
        raise SystemExit("fmt: pool line over the engine ini buffer cap")
    print("  fmt: pools deduped, presets normalized, all lines under cap")


# ---- audibility: the engine facts behind the fold + the blob floors --------------------------------
# Two engine facts (doc/library/anomaly/internals/sound-source-and-emitter.md) make most of a merged
# ambient corpus INAUDIBLE at range even when the files sound fine at-ear:
#   1. A STEREO ogg force-plays 2D at-ear at full volume, escaping both distance rolloffs (":258-268").
#      Only MONO spatialises. So every stereo bed/one-shot plays in-head, ignoring placement.
#   2. Every 3D voice is attenuated TWICE - X-Ray's linear fade AND OpenAL's inverse model keyed on the
#      ogg blob's min_distance (":132-181"). min 1-2 (the unset ffmpeg-era default, ~84% of this corpus)
#      costs -26..-31 dB at a 25-50 m placement BEFORE the linear fade. base_volume can't rescue it.

FLOOR_MAX_FRAC = 0.8     # cap the min floor below blob max so a real fade band always survives.
DEFAULT_MAX    = 100.0   # blob max for a blob-less file (corpus median from the survey).
ENCODE_Q       = 6       # libvorbis -q for the mono re-encode (high quality, deterministic).
ANTIPHASE_DB   = 3.0     # side RMS this many dB above mid -> anti-phase pair, summing cancels -> drop R.
FOLD_BLOBS     = os.path.join(HERE, "fold_blobs.json")   # author blobs captured before the fold strips them

# --- ported audibility floors (proven in AlifeSpooks build.py, 2026-08-22) -------------------------
# Two lift-only, lossless blob floors, applied together after measuring content LUFS + crest:
#   1. min_distance floor, crest-INVERTED: a sustained (low-crest) tone carries in air -> higher ratio;
#      a sharp (high-crest) transient is a near-field detail -> lower ratio. floor = ratio*felt, cap 0.8*max.
#   2. base_volume LOUDNESS floor: lift a file whose DELIVERED loudness at felt-far sits below the ear-
#      anchored floor. Partial (close FRAC of the deficit), capped (MAXBV + a far-gain cap that keeps far
#      smooth_volume below the engine 1.0 clamp so falloff survives). Never lowers, overshoots, or flattens.
# AA floor split (2026-08-22 ear calibration): beds cross the audible line higher than one-shots -
#   bed faint ~-36 delivered, one-shot faint ~-42 delivered. With the -6 dB effects master (slider 0.5)
#   that is eff (content+blob) floor -30 for beds, -36 for one-shots.
RATIO_HI         = 0.60    # sustained (low crest): carries at distance
RATIO_LO         = 0.40    # transient (high crest): near-field
CREST_LO         = 6.0     # dB -> RATIO_HI
CREST_HI         = 24.0    # dB -> RATIO_LO
LOUD_FLOOR_BED   = -30.0   # eff floor, continuous beds   (= -36 delivered at effects slider 0.5)
LOUD_FLOOR_1SHOT = -36.0   # eff floor, one-shots         (= -42 delivered)
LOUD_MAXBV       = 6.0     # base_volume ceiling
LOUD_FARCAP      = 0.85    # keep far smooth_volume below the engine 1.0 clamp
LOUD_FRAC        = 0.7     # close this fraction of each file's deficit (partial lift)
LOUD_MASTER      = 0.5     # psSoundVEffects*psSoundVFactor at calibration
LOUD_ROLLOFF     = 0.75    # psSoundRolloff (fixed, SoundRender_Core.cpp:19)
DEAD_LUFS        = -60.0   # content LUFS at/below = silent/dead (ebur128 floors true silence at ~-70)
LOUD_CEIL_BED    = -24.0   # eff ceiling, beds: lower a file delivering louder than this (mirror of the floor)
LOUD_CEIL_1SHOT  = -28.0   # eff ceiling, one-shots: caps the hot tail (e.g. the loudest ~7% of crickets)
LOUD_MINBV       = 0.20    # base_volume floor when LOWERING an over-loud file (never kill it)
# continuous-bed path keys get LOUD_FLOOR_BED / LOUD_CEIL_BED; everything else is a one-shot
BED_KEYS = ("wind", "storm", "rain", "thunder", "tuman", "background",
            "ambient_forest", "ambient_swamp", "drone", "rumble")


def _crest_ratio(crest):
    """Crest dB -> min/felt-far ratio, INVERTED: high crest (transient) -> RATIO_LO, low (sustained) -> RATIO_HI."""
    t = (crest - CREST_LO) / (CREST_HI - CREST_LO)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return RATIO_HI - (RATIO_HI - RATIO_LO) * t


def _loud_floor_for(rel_lc):
    """The eff loudness floor for a file, by whether its path is a continuous bed or a one-shot."""
    return LOUD_FLOOR_BED if any(k in rel_lc for k in BED_KEYS) else LOUD_FLOOR_1SHOT


def _loudness_floor(bv, mn, mx, felt_far, lufs, floor):
    """Floored base_volume for one file (lift-only, partial, capped). mn/mx = the ALREADY min-floored blob
    range, felt_far = channel felt placement, lufs = deployed content loudness (or None). Model:
    delivered = base_volume*volume_att*al_gain; va=(mx-d)/(mx-mn) clamped; al=mn/(mn+0.75*(d-mn)). No lift
    when placed past its own max (silent by placement, not loudness) or when loudness is unknown."""
    if lufs is None or felt_far >= mx:
        return bv
    va = max(0.0, min(1.0, (mx - felt_far) / (mx - mn))) if mx > mn else 0.0
    d = min(max(felt_far, mn), mx)
    al = mn / (mn + LOUD_ROLLOFF * (d - mn)) if d > mn else 1.0
    if va * al <= 1e-6 or bv <= 0.0:
        return bv
    eff = lufs + 20.0 * math.log10(bv * va * al)
    if eff >= floor:
        return bv
    want = bv * (10 ** (LOUD_FRAC * (floor - eff) / 20.0))   # close FRAC of the deficit
    farcap = LOUD_FARCAP / (va * al * LOUD_MASTER)            # keep far gain below the 1.0 clamp
    return max(bv, min(want, farcap, LOUD_MAXBV))


def _ceil_for(rel_lc):
    """The eff loudness CEILING for a file (mirror of _loud_floor_for): beds tighter, one-shots wider."""
    return LOUD_CEIL_BED if any(k in rel_lc for k in BED_KEYS) else LOUD_CEIL_1SHOT


def _loudness_ceiling(bv, mn, mx, felt_far, lufs, ceil):
    """Mirror of _loudness_floor: LOWER base_volume of a file delivering ABOVE the ceiling at felt-far,
    partial (close FRAC of the excess), floored at LOUD_MINBV, never raised. Floor+ceiling form a per-
    category band; a file is only ever in one arm (below floor OR above ceiling), so the two never fight."""
    if lufs is None or felt_far >= mx:
        return bv
    va = max(0.0, min(1.0, (mx - felt_far) / (mx - mn))) if mx > mn else 0.0
    d = min(max(felt_far, mn), mx)
    al = mn / (mn + LOUD_ROLLOFF * (d - mn)) if d > mn else 1.0
    if va * al <= 1e-6 or bv <= 0.0:
        return bv
    eff = lufs + 20.0 * math.log10(bv * va * al)
    if eff <= ceil:
        return bv
    want = bv * (10 ** (LOUD_FRAC * (ceil - eff) / 20.0))    # ceil-eff < 0 -> lowers by FRAC of the excess
    return min(bv, max(want, LOUD_MINBV))


def _ogg_info(path):
    """(channels, sample_rate) from the vorbis identification header, or (None, None)."""
    with open(path, "rb") as f:
        d = f.read(4096)
    i = d.find(b"\x01vorbis")
    if i < 0 or i + 16 > len(d):
        return None, None
    return d[i + 11], struct.unpack("<I", d[i + 12:i + 16])[0]


# --- X-Ray ogg comment blob: read + lossless bitstream write (technique per the engine loader) ---

def _crc32(data):
    crc = 0
    for b in data:
        crc ^= b << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04c11db7) & 0xffffffff if (crc & 0x80000000) else (crc << 1) & 0xffffffff
    return crc


def _ogg_pages(d):
    off, out = 0, []
    while off < len(d) and d[off:off + 4] == b"OggS":
        nseg = d[off + 26]
        segs = d[off + 27:off + 27 + nseg]
        dlen = sum(segs)
        out.append((off, bytes(segs), d[off + 27 + nseg:off + 27 + nseg + dlen]))
        off += 27 + nseg + dlen
    return out, off


def _ogg_packets(segs, body):
    pkts, cur, start = [], 0, 0
    for s in segs:
        cur += s
        if s < 255:
            pkts.append(body[start:start + cur]); start += cur; cur = 0
    return pkts


def _read_blob(d):
    """comment[0] as (min, max, base_volume) for a valid X-Ray blob, else None."""
    i = d.find(b"\x03vorbis")
    if i < 0:
        return None
    p = i + 7
    try:
        (vl,) = struct.unpack("<I", d[p:p + 4]); p += 4 + vl
        (n,) = struct.unpack("<I", d[p:p + 4]); p += 4
        if n == 0:
            return None
        (cl,) = struct.unpack("<I", d[p:p + 4]); p += 4
        c0 = d[p:p + cl]
        if len(c0) < 4:
            return None
        (v,) = struct.unpack("<I", c0[:4])
        if v == 1 and len(c0) >= 16:
            mn, mx = struct.unpack("<ff", c0[4:12]); return (mn, mx, 1.0)
        if v in (2, 3) and len(c0) >= 20:
            mn, mx, bv = struct.unpack("<fff", c0[4:16]); return (mn, mx, bv)
    except struct.error:
        return None
    return None


def _build_page(htype, granule, serial, seq, packets):
    segtab, body = [], b""
    for packet in packets:
        seg_len = len(packet)
        while seg_len >= 255:
            segtab.append(255); seg_len -= 255
        segtab.append(seg_len); body += packet
    if len(segtab) > 255:
        return None
    page = (b"OggS" + bytes([0, htype]) + struct.pack("<q", granule) +
            struct.pack("<I", serial) + struct.pack("<I", seq) +
            struct.pack("<I", 0) + bytes([len(segtab)]) + bytes(segtab) + body)
    return page[:22] + struct.pack("<I", _crc32(page)) + page[26:]


def _write_blob(path, mn, mx, bv):
    """Write a 0x0003 X-Ray blob as comment[0] losslessly (only page 1 changes; audio pages
    byte-identical). Standard [ID | comment+setup | audio...] layout only; else returns False."""
    with open(path, "rb") as f:
        d = f.read()
    pg, end = _ogg_pages(d)
    if end != len(d) or len(pg) < 3:
        return False
    pkts = _ogg_packets(pg[1][1], pg[1][2])
    if len(pkts) != 2 or not pkts[0].startswith(b"\x03vorbis") or not pkts[1].startswith(b"\x05vorbis"):
        return False
    comment_pkt, setup_pkt = pkts
    p = 7
    (vl,) = struct.unpack("<I", comment_pkt[p:p + 4]); p += 4
    vendor = comment_pkt[p:p + vl]
    blob = struct.pack("<I", 3) + struct.pack("<fff", mn, mx, bv) + struct.pack("<I", 0) + struct.pack("<f", mx)
    new_comment = (b"\x03vorbis" + struct.pack("<I", len(vendor)) + vendor +
                   struct.pack("<I", 1) + struct.pack("<I", len(blob)) + blob + b"\x01")
    o = pg[1][0]
    htype = d[o + 5]
    gran = struct.unpack("<q", d[o + 6:o + 14])[0]
    serial = struct.unpack("<I", d[o + 14:o + 18])[0]
    seq = struct.unpack("<I", d[o + 18:o + 22])[0]
    new_p1 = _build_page(htype, gran, serial, seq, [new_comment, setup_pkt])
    if new_p1 is None:
        return False
    with open(path, "wb") as f:
        f.write(d[:pg[1][0]] + new_p1 + d[pg[2][0]:])
    return True


# --- channel felt-far (placement) mapping ---

def _channel_bands():
    """channel(lower) -> (felt_far, [sound tokens]). felt_far = ltx max_distance / 2 (System B places at
    ~ltx_max/2; ambient-sound-system.md). A token is a file path (no ext) or a folder path."""
    bands = {}
    for f in CHANNEL_FILES:
        if not os.path.exists(f):
            continue
        for blk in re.split(r"(?m)^(?=\[[A-Za-z0-9_]+\])", _read(f)):
            hm = re.match(r"\[([A-Za-z0-9_]+)\]", blk)
            if not hm:
                continue
            mx = re.search(r"(?im)^\s*max_distance\s*=\s*([\d.]+)", blk)
            toks = []
            for m in re.findall(r"(?im)^\s*sounds\d*\s*=\s*(.+)$", blk):
                for one in re.split(r"[,;]", m):
                    t = _tok_ok(one)
                    if t:
                        toks.append(t)
            bands[hm.group(1).lower()] = (float(mx.group(1)) / 2.0 if mx else 40.0, toks)
    return bands


def _channel_periods():
    """channel(lower) -> [period0..period3] in ms (missing keys -> None entries)."""
    out = {}
    for f in CHANNEL_FILES:
        if not os.path.exists(f):
            continue
        for blk in re.split(r"(?m)^(?=\[[A-Za-z0-9_]+\])", _read(f)):
            hm = re.match(r"\[([A-Za-z0-9_]+)\]", blk)
            if not hm:
                continue
            per = [None] * 4
            for i in range(4):
                m = re.search(rf"(?im)^\s*period{i}\s*=\s*([\d.]+)", blk)
                if m:
                    per[i] = float(m.group(1))
            out[hm.group(1).lower()] = per
    return out


def _channel_defs():
    """channel(lower) -> {min_distance, max_distance, period0..3, sounds_n, indoor} for the
    load-rule gates (13-15). Same block scan as _channel_periods, all keys at once."""
    out = {}
    for f in CHANNEL_FILES:
        if not os.path.exists(f):
            continue
        for blk in re.split(r"(?m)^(?=\[[A-Za-z0-9_]+\])", _read(f)):
            hm = re.match(r"\[([A-Za-z0-9_]+)\]", blk)
            if not hm:
                continue
            d = {}
            for k in ("min_distance", "max_distance", "period0", "period1", "period2", "period3"):
                m = re.search(rf"(?im)^\s*{k}\s*=\s*([\d.]+)", blk)
                d[k] = float(m.group(1)) if m else None
            m = re.search(r"(?im)^\s*sounds\d*\s*=\s*(\S.*)$", blk)
            d["sounds_n"] = len([t for t in re.split(r"[,;]", m.group(1)) if t.strip()]) if m else 0
            m = re.search(r"(?im)^\s*indoor\s*=\s*(\w+)", blk)
            d["indoor"] = bool(m and m.group(1).lower() in ("true", "1", "yes", "on"))
            out[hm.group(1).lower()] = d
    return out


def _preset_beds():
    """Channel names referenced as System A BEDS (the `sound_channels =` lines of the presets and
    ambients.ltx). These load through SSndChannel::load, so the engine asserts apply to them."""
    beds = set()
    files = [os.path.join(PRESETS, fn) for fn in os.listdir(PRESETS)]
    amb = os.path.join(ENV, "ambients.ltx")
    if os.path.exists(amb):
        files.append(amb)
    for pp in files:
        for m in re.findall(r"(?im)^\s*sound_channels\s*=\s*(.+)$", _read(pp)):
            for one in re.split(r"[,;]", m):
                one = one.strip().lower()
                if one and "=" not in one and " " not in one:
                    beds.add(one)
    return beds


def _file_felt_far(bands):
    """token(lower, file or folder) -> the MAX felt-far of any channel that references it. Max = the
    farthest placement the file is used at (the conservative floor: audible at its farthest use)."""
    ff = {}
    for _ch, (felt, toks) in bands.items():
        for t in toks:
            if felt > ff.get(t, 0.0):
                ff[t] = felt
    return ff


def _felt_for(rel_lc, ff):
    """felt-far for a deployed ogg (rel, lower, no ext): its own file token, or its folder token."""
    return max(ff.get(rel_lc, 0.0), ff.get(os.path.dirname(rel_lc), 0.0))


def _stereo_method(path):
    """'sum' ((L+R)/2) normally; 'drop' (keep L) for an anti-phase pair where summing cancels. One
    ffmpeg mid/side RMS probe. A >2-channel file has no mid/side -> 'sum' (-ac 1)."""
    ch, _ = _ogg_info(path)
    if ch != 2:
        return "sum"
    r = subprocess.run([_FFMPEG, "-hide_banner", "-i", path, "-af",
                        "pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0-0.5*c1,astats=metadata=1:reset=0",
                        "-f", "null", "-"], capture_output=True, text=True)
    rms = re.findall(r"RMS level dB:\s*(-?[\d.]+|-inf)", r.stderr)
    if len(rms) < 2:
        return "sum"
    def db(x):
        return -120.0 if x == "-inf" else float(x)
    mid, side = db(rms[0]), db(rms[1])
    return "drop" if side - mid > ANTIPHASE_DB else "sum"


def _find_ffmpeg():
    """Resolve a real ffmpeg.exe. Native Windows subprocess cannot exec the PORTX .CMD wrapper that
    `which` returns, so prefer a .exe: which-if-exe, then the PORTX exe, then parse the wrapper."""
    w = shutil.which("ffmpeg")
    if w and w.lower().endswith(".exe"):
        return w
    portx = r"C:\App\PORTX\packages\ffmpeg\ffmpeg.exe"
    if os.path.exists(portx):
        return portx
    if w and os.path.exists(w):
        try:
            for ln in open(w, encoding="utf-8", errors="replace"):
                m = re.search(r'"([^"]+\.exe)"', ln)
                if m and os.path.exists(m.group(1)):
                    return m.group(1)
        except OSError:
            pass
    return "ffmpeg"


_FFMPEG = _find_ffmpeg()


def cmd_fold():
    """Fold every STEREO file to mono and resample every OFF-RATE file to 44100, in place. Captures each
    file's author blob to fold_blobs.json BEFORE the re-encode strips it, so level can restore its
    min/max/base_volume. Re-encode is libvorbis -q6; the audio is no longer byte-identical (unavoidable:
    the engine only spatialises mono). Idempotent-ish: a file already mono+44100 is skipped. Applies to
    ALL 3D-played audio, ambient channels and strike files alike."""
    fold_blobs = json.load(open(FOLD_BLOBS)) if os.path.exists(FOLD_BLOBS) else {}
    folded = resampled = skipped = failed = 0
    n_sum = n_drop = 0
    for full, rel_lc in _iter_deployed():
        ch, sr = _ogg_info(full)
        need_mono = (ch is not None and ch >= 2)
        need_rate = (sr is not None and sr != 44100)
        if not (need_mono or need_rate):
            skipped += 1
            continue
        # capture the author blob before the re-encode strips it
        with open(full, "rb") as fh:
            b = _read_blob(fh.read(16384))
        fold_blobs[rel_lc] = list(b) if b else None
        method = _stereo_method(full) if need_mono else "sum"
        af = ["-ac", "1"] if method == "sum" else ["-af", "pan=mono|c0=c0"]
        tmp = full + ".fold.ogg"
        r = subprocess.run([_FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", full,
                            *af, "-ar", "44100", "-c:a", "libvorbis", "-q:a", str(ENCODE_Q),
                            "-map_metadata", "-1", tmp], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(tmp):
            failed += 1
            continue
        os.replace(tmp, full)
        if need_mono:
            folded += 1
            n_sum += method == "sum"
            n_drop += method == "drop"
        else:
            resampled += 1
    json.dump(fold_blobs, open(FOLD_BLOBS, "w"))
    print(f"  fold: {folded} stereo->mono ({n_sum} sum + {n_drop} drop), {resampled} resampled, "
          f"{skipped} already mono+44100; {failed} FAILED")


def cmd_audit():
    """Acceptance report: over the WIRED files, the min/felt-far ratio (the audibility ratio) and the
    crushed share (<0.15 = whisper). Target = the crest-inverted min floor's ratio band (0.40-0.60), so
    the median should sit ~0.4-0.5 with few crushed. Blob reads only, no ffmpeg."""
    ff = _file_felt_far(_channel_bands())
    ratios = []
    crushed = 0
    for full, rel_lc in _iter_deployed():
        felt = _felt_for(rel_lc, ff)
        if felt <= 0.0:
            continue
        with open(full, "rb") as fh:
            b = _read_blob(fh.read(16384))
        mn = b[0] if b else 1.0
        r = mn / felt
        ratios.append(r)
        if r < 0.15:
            crushed += 1
    if not ratios:
        print("  audit: no wired files"); return
    ratios.sort()
    n = len(ratios)
    med = ratios[n // 2]
    p25 = ratios[n // 4]
    p75 = ratios[(3 * n) // 4]
    print(f"  audit: wired={n}  min/felt-far median={med:.2f} p25={p25:.2f} p75={p75:.2f}  "
          f"crushed(<0.15)={100 * crushed // n}%  (target: crest-floor ratio {RATIO_LO}-{RATIO_HI}, low crushed)")


# ---- level: the two blob floors (min-distance + base_volume loudness) ---------
LEVEL_CACHE    = os.path.join(HERE, "level_cache.json")   # audio-hash -> [lufs, crest, peak]


def _hash_audio(path):
    """md5 of the audio pages only (after ID + comment/setup), so a comment-blob rewrite (level)
    does not invalidate the cached measure - the audio is what was measured."""
    with open(path, "rb") as f:
        pg, _ = _ogg_pages(f.read())
    return hashlib.md5(b"".join(p[2] for p in pg[2:])).hexdigest()


def _measure_audio(path):
    """(integrated LUFS, crest dB, true-peak dBFS) from one ffmpeg pass. crest = peak - rms (astats),
    LUFS = ebur128 I. Silence/failure -> (None, 0, 0)."""
    r = subprocess.run([_FFMPEG, "-hide_banner", "-nostats", "-i", path,
                        "-af", "astats=metadata=1:reset=0,ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    lufs = peak = rms = None
    for ln in r.stderr.splitlines():
        m = re.search(r"\bI:\s*(-?[0-9.]+)\s*LUFS", ln)
        if m:
            lufs = float(m.group(1))
        m = re.search(r"Peak level dB:\s*(-?[0-9.]+)", ln)
        if m:
            peak = float(m.group(1))
        m = re.search(r"RMS level dB:\s*(-?[0-9.]+)", ln)
        if m:
            rms = float(m.group(1))
    crest = (peak - rms) if (peak is not None and rms is not None) else 0.0
    return lufs, crest, (peak if peak is not None else 0.0)


def cmd_level():
    """Apply both lossless blob floors to each wired file, from one crest+LUFS measurement:
      1. min_distance -> max(author, crest-inverted ratio x felt-far), capped 0.8*max  (fixes OpenAL rolloff)
      2. base_volume -> the loudness band: lifted to the ear floor (-30 eff beds / -36 one-shots) or
         lowered from above the ceiling, partial + capped  (fixes content the min floor cannot)
    Skips emission (blowout/anomaly), strike files (the engine overrides their range per strike,
    thunderbolt.cpp:235 - blob distances do nothing there), staged and unwired files. Measure cached by
    audio hash; lossless rewrite."""
    cache = json.load(open(LEVEL_CACHE)) if os.path.exists(LEVEL_CACHE) else {}
    fold_blobs = json.load(open(FOLD_BLOBS)) if os.path.exists(FOLD_BLOBS) else {}
    ff = _file_felt_far(_channel_bands())
    total = wrote = floored = lifted = lowered = e_skip = u_skip = no_meas = measured = 0
    gains = []
    restored = 0
    for full, rel_lc in _iter_deployed():
        total += 1
        if rel_lc.startswith("nature/"):
            # strike files: no floors (the engine overrides their range per strike), but the fold
            # strips the author blob - restore the captured one verbatim (I7: preserve the source)
            with open(full, "rb") as fh:
                b = _read_blob(fh.read(16384))
            cap = fold_blobs.get(rel_lc)
            if b is None and cap and _write_blob(full, cap[0], cap[1], cap[2]):
                restored += 1
            e_skip += 1
            continue
        if (rel_lc.startswith("ambient/blowout") or rel_lc.startswith("ambient/anomaly")
                or _is_staged(rel_lc)):
            e_skip += 1
            continue
        felt = _felt_for(rel_lc, ff)
        if felt <= 0.0:
            u_skip += 1                        # unwired (orphan) - leave verbatim
            continue
        h = _hash_audio(full)
        m = cache.get(h)
        if m is None:
            m = list(_measure_audio(full))
            cache[h] = m
            measured += 1
        lufs, crest, _peak = m
        with open(full, "rb") as fh:
            b = _read_blob(fh.read(16384))
        if not b:                                                     # folded-stereo lost its blob -> recover
            cap = fold_blobs.get(rel_lc)
            b = tuple(cap) if cap else (1.0, DEFAULT_MAX, 1.0)
        mn, mx, bv = b
        if mn < 0.0:
            mn = 0.0
        floor = min(_crest_ratio(crest) * felt, mx * FLOOR_MAX_FRAC)  # (1) crest-inverted min floor
        if mn < floor:
            mn = floor
            floored += 1
        if lufs is not None:                                          # (2) loudness band: floor lifts, ceiling lowers
            bvn = _loudness_floor(bv, mn, mx, felt, lufs, _loud_floor_for(rel_lc))
            if bvn > bv + 1e-9:
                gains.append(20.0 * math.log10(bvn / bv))
                bv = bvn
                lifted += 1
            else:                                                     # not lifted -> maybe over the ceiling
                bvn = _loudness_ceiling(bv, mn, mx, felt, lufs, _ceil_for(rel_lc))
                if bvn < bv - 1e-9:
                    gains.append(20.0 * math.log10(bvn / bv))
                    bv = bvn
                    lowered += 1
        else:
            no_meas += 1
        if mx < mn + 0.1:                                             # engine (max-min) divide / loader safety
            mx = mn + 0.1
        # Idempotent write: the loudness floor closes only LOUD_FRAC of the deficit, so re-reading an
        # already-lifted blob and lifting again asymptotes toward the floor - every full run nudges bv and
        # rewrites the file. Skip a re-write once within an inaudible band of the target (bv within 1% =
        # ~0.09 dB, an order under the ~1 dB JND and under any real lift; mn/mx within 0.1), so the file
        # settles in one pass and a repeat run leaves the deployed tree clean.
        mn0, mx0, bv0 = b
        if abs(bv - bv0) <= bv0 * 1e-2 and abs(mn - mn0) <= 0.1 and abs(mx - mx0) <= 0.1:
            continue
        if _write_blob(full, mn, mx, bv):
            wrote += 1
    json.dump(cache, open(LEVEL_CACHE, "w"))
    gm = statistics.median(gains) if gains else 0.0
    gx = max(gains) if gains else 0.0
    print(f"  level: {total} files | min-floored {floored} (crest-inverted), loudness-lifted {lifted}, "
          f"lowered {lowered} (over ceiling) (median {gm:+.1f} dB, up to {gx:+.1f} dB)")
    print(f"         wrote {wrote} blobs, restored {restored} strike author blobs | "
          f"skipped {e_skip} emission/strike/staged, {u_skip} unwired, "
          f"{no_meas} unmeasurable | measured {measured} new, {len(cache) - measured} cached")


# --- acoustic-duplicate report (Chromaprint) --------------------------------------------------------
FP_EXE   = "C:/App/PORTX/packages/chromaprint/fpcalc.exe"
FP_CACHE = os.path.join(HERE, "fingerprint_cache.json")   # audio-page hash -> chromaprint fingerprint ("" = none)


def _fingerprint(path):
    """Chromaprint acoustic fingerprint of a file, or '' if fpcalc cannot read it (very short clips)."""
    try:
        r = subprocess.run([FP_EXE, "-raw", "-length", "30", path], capture_output=True, text=True, timeout=40)
        for ln in r.stdout.splitlines():
            if ln.startswith("FINGERPRINT="):
                return ln[12:]
    except Exception:
        pass
    return ""


def cmd_fingerprint():
    """Report acoustic duplicates (same recording under two deployed paths) for the CURATOR to resolve.
    Warns only - the authored config decides which path lives; nothing is repointed or deleted here."""
    cache = json.load(open(FP_CACHE)) if os.path.exists(FP_CACHE) else {}
    by_fp = {}
    n = measured = 0
    for full, rel_lc in _iter_deployed():
        if _is_staged(rel_lc):
            continue
        n += 1
        h = _hash_audio(full)
        fp = cache.get(h)
        if fp is None:
            fp = _fingerprint(full)
            cache[h] = fp
            measured += 1
        if fp:
            by_fp.setdefault(fp, []).append(rel_lc)
    json.dump(cache, open(FP_CACHE, "w"))
    groups = [sorted(set(v)) for v in by_fp.values() if len(set(v)) > 1]
    for g in groups[:20]:
        print(f"  DUP {g[0]} == {', '.join(g[1:])}")
    if len(groups) > 20:
        print(f"  ... {len(groups) - 20} more duplicate groups")
    print(f"  fingerprint: {n} files ({measured} measured) | {len(groups)} acoustic-duplicate groups "
          f"(curator resolves in config)")


def cmd_dead():
    """Report DEAD deployed files (content at/below DEAD_LUFS - true silence) for the CURATOR to
    exclude. Reuses the level cache; nothing is deleted here (a file leaves through the exclusions
    register + config, then materialize removes it)."""
    cache = json.load(open(LEVEL_CACHE)) if os.path.exists(LEVEL_CACHE) else {}
    dead = []
    for full, rel_lc in _iter_deployed():
        if _is_staged(rel_lc):
            continue
        m = cache.get(_hash_audio(full))
        if m is not None and (m[0] is None or m[0] <= DEAD_LUFS):
            dead.append(rel_lc)
    for d in dead[:20]:
        print(f"  DEAD {d}")
    if len(dead) > 20:
        print(f"  ... {len(dead) - 20} more")
    print(f"  dead: {len(dead)} silent files (curator excludes; materialize then removes)")


# ---- stage: candidate-family audition --------------------------------------------------------------

def cmd_stage():
    """stage <source>:<folder> - materialize a source folder under sounds/stage/<folder> so the player
    (ui_aa_player.script) can audition a candidate family in-game before it is picked. Exempt from all
    gates; folded on the next fold run; removed by unstage."""
    if len(sys.argv) < 3 or ":" not in sys.argv[2]:
        raise SystemExit("usage: merge.py stage <source>:<folder-under-sounds>")
    src_name, folder = sys.argv[2].split(":", 1)
    gd = dict(sources.mods()).get(src_name)
    if not gd:
        raise SystemExit(f"unknown source {src_name} (see sources.py)")
    src = os.path.join(gd, "sounds", folder.replace("/", os.sep))
    if not os.path.isdir(src):
        raise SystemExit(f"no folder {src}")
    dst = os.path.join(SROOT, STAGE_DIR, folder.replace("/", os.sep))
    os.makedirs(dst, exist_ok=True)
    ncop = 0
    for fn in sorted(os.listdir(src)):
        if fn.lower().endswith(".ogg"):
            shutil.copy2(os.path.join(src, fn), os.path.join(dst, fn))
            ncop += 1
    print(f"  stage: {ncop} files -> sounds/{STAGE_DIR}/{folder} (run fold, then audition; unstage removes)")


def cmd_unstage():
    d = os.path.join(SROOT, STAGE_DIR)
    if os.path.isdir(d):
        shutil.rmtree(d)
        print("  unstage: stage tree removed")
    else:
        print("  unstage: nothing staged")


# ---- verify: the gate ledger -----------------------------------------------------------------------

def _veto_by_section():
    """AlifeSpooks' veto as {section(lower) -> (removed paths, has_no_sound_append)}, from its static
    DLTX overlay (`![channel]` blocks: `<sounds = <path>` removals + a trailing `>sounds =
    ambient\\no_sound`). None if the sibling repo is not on this machine. The intersection is DESIGNED
    coexistence (no doubling of the director's captured sounds), and the generator's no_sound append
    keeps a fully-vetoed channel alive and silent (AlifeSpooks build.py:1065-1130 cites the
    Environment_misc.cpp:105-108 empty-sounds load failure it prevents). The hazard gate 11 guards is
    a touched channel WITHOUT that append."""
    if not os.path.exists(SPOOKS_VETO):
        return None
    out = {}
    cur = None
    for ln in _read(SPOOKS_VETO).split("\n"):
        mh = re.match(r"\s*!\[([^\]]+)\]", ln)
        if mh:
            cur = mh.group(1).lower()
            out.setdefault(cur, [set(), False])
            continue
        mm = re.match(r"\s*<sounds\s*=\s*(.+)$", ln)
        if mm and cur:
            t = _tok_ok(mm.group(1))
            if t:
                out[cur][0].add(t)
            continue
        ma = re.match(r"\s*>sounds\s*=\s*(.+)$", ln)
        if ma and cur and "no_sound" in ma.group(1).lower():
            out[cur][1] = True
    return out


def _preset_state_channels():
    """preset file -> state -> [channels] from the sound_channels_dynamic lines."""
    out = {}
    for fn in os.listdir(PRESETS):
        txt = _read(os.path.join(PRESETS, fn))
        states = {}
        cur = None
        for ln in txt.split("\n"):
            mh = re.match(r"\s*\[([A-Za-z0-9_]+)\]", ln)
            if mh:
                cur = mh.group(1).lower()
                continue
            md = re.match(r"\s*sound_channels_dynamic\s*=\s*(.+)$", ln, re.I)
            if md and cur:
                states[cur] = [t.strip().lower() for t in re.split(r"[,;]", md.group(1)) if t.strip()]
        out[fn] = states
    return out


def _retention():
    """(unaccounted list, per-source counts). Every ambience-scope source file must be referenced by
    the config / DEPLOY_EXTRA, or covered by a DISPOSITIONS prefix (sources.py)."""
    refs = _channel_paths()
    deployed = {rel_lc for _f, rel_lc in _iter_deployed()}
    # folder tokens only (see cmd_verify): a sibling file ref never covers a whole source folder
    folder_toks = {p for p in refs if p not in deployed}
    extra = set(_extra_targets().keys())
    disp = [(s, pre.replace("\\", "/").lower().rstrip("/"), verdict)
            for s, pre, verdict, _r in sources.DISPOSITIONS]
    unaccounted = []
    per_source = {}
    for name, gd in sources.mods():
        if name in RESOLVE_SKIP or not os.path.isdir(gd):
            continue
        acc = {"referenced": 0, "disposed": 0, "unaccounted": 0}
        for _full, rel in _iter_oggs(gd):
            rl = rel.lower()
            base = rl[:-4]
            d = os.path.dirname(base)
            if (base in refs or rl in extra
                    or any(d == ft or d.startswith(ft + "/") for ft in folder_toks)):
                acc["referenced"] += 1
                continue
            if any(s == name and rl.startswith(p) for s, p, _v in disp):
                acc["disposed"] += 1
                continue
            acc["unaccounted"] += 1
            if len(unaccounted) < 400:
                unaccounted.append(f"{name}:{rel}")
        per_source[name] = acc
    return unaccounted, per_source


def cmd_verify():
    defined = _defined_channels()
    referenced = _preset_refs()
    chan_paths = _channel_paths()
    extra = set(_extra_targets().keys())
    disk = set()
    for _full, rel_lc in _iter_deployed():
        if not _is_staged(rel_lc):
            disk.add(rel_lc)
    disk_dirs = {os.path.dirname(d) for d in disk}
    # a folder TOKEN is a channel ref that is not a deployed file (random-pick folder ref)
    folder_toks = {p for p in chan_paths if p not in disk}

    # 1 orphan files: on disk, no channel file ref, folder token, or DEPLOY_EXTRA covers it
    def tok_covers(rel):
        d = os.path.dirname(rel)
        return any(d == ft or d.startswith(ft + "/") for ft in folder_toks)
    orphan_files = sorted(d for d in disk
                          if d not in chan_paths and not tok_covers(d)
                          and (d + ".ogg") not in extra)
    # 2 orphan channels: defined, never referenced (INFO: dead weight for the curator)
    orphan_channels = sorted(defined - referenced)
    # 3 dangling refs: referenced, not defined
    dangling = sorted(referenced - defined)
    # 4 missing paths: channel path with no file on disk (file OR folder)
    def path_on_disk(p):
        return p in disk or p in disk_dirs or any(d.startswith(p + "/") for d in disk_dirs)
    missing_paths = sorted(p for p in chan_paths if not path_on_disk(p))
    # 5 level routing
    level_bad = []
    for fn in os.listdir(LEVELS):
        if not fn.endswith(".ltx") or fn == "ambients.ltx":
            continue
        inc = re.search(r"presets[\\/]environment_([A-Za-z0-9_]+)", _read(os.path.join(LEVELS, fn)))
        if not inc:
            level_bad.append((fn, "no-include"))
            continue
        pr = inc.group(1).lower()
        name = fn[:-4].lower()
        ug_name = any(t in name for t in ("bunker", "collaid", "x18", "x16", "katakomb", "sarcofag"))
        if ug_name and "underground" not in pr:
            level_bad.append((fn, f"underground level -> outdoor preset {pr}"))
    # 6 weather matrix
    matrix_gaps = []
    for fn in os.listdir(PRESETS):
        secs = {s.lower() for s in re.findall(r"^\s*\[([A-Za-z0-9_]+)\]", _read(os.path.join(PRESETS, fn)), re.M)}
        is_ug = "underground" in fn.lower()
        need = [UNDERGROUND_STATE] if is_ug else [s for s in WEATHER_STATES if s != UNDERGROUND_STATE]
        miss = [s for s in need if s not in secs]
        if miss:
            matrix_gaps.append((fn, miss))
    # 7 retention
    unaccounted, per_source = _retention()
    # 8 density (report; budget gate armed once DENSITY_BUDGET is calibrated)
    periods = _channel_periods()
    sounding = {ch for ch, (_felt, toks) in _channel_bands().items() if toks}   # a no_sound channel fires but is silent
    density_rows = []
    burst_worst = (0, "")
    for fn, states in _preset_state_channels().items():
        for st, chans in states.items():
            epm = 0.0
            burst = 0
            for c in chans:
                if c not in sounding:            # exclude silent channels from the density sum (the n003 over-count)
                    continue
                per = periods.get(c)
                if not per:
                    continue
                p2, p3 = per[2], per[3]
                if p2 and p3 and (p2 + p3) > 0:
                    # the round-robin evaluates ONE channel per tick (~1 s), so a channel cannot
                    # fire more often than once per len(chans) seconds regardless of its periods
                    mean_ms = (p2 + p3) / 2.0
                    epm += 60000.0 / max(mean_ms, len(chans) * 1000.0)
                if per[0] is not None and per[0] < ENTRY_BURST_MS:
                    burst += 1
            density_rows.append((fn, st, round(epm, 1), burst))
            if burst > burst_worst[0]:
                burst_worst = (burst, f"{fn}[{st}]")
    over_budget = [r for r in density_rows
                   if DENSITY_BUDGET.get(r[1]) is not None and r[2] > DENSITY_BUDGET[r[1]]]
    # 9 line cap
    over_cap = []
    for f in CHANNEL_FILES:
        if os.path.exists(f):
            for ln in _read(f).split("\n"):
                if re.match(r"\s*sounds\d*\s*=", ln, re.I) and len(ln) > LINE_CAP:
                    over_cap.append((os.path.basename(f), len(ln)))
    # 10 collection coverage (static: we deploy strike audio at vanilla paths, ship no collection cfg)
    missing_coll = sorted(COLLECTIONS_REQUIRED - COLLECTIONS_BASE)
    # 11 veto simulation: a touched channel is a hazard only if the overlay leaves it EMPTY -
    # the generator's `>sounds = ambient\no_sound` append normally prevents that (silenced, INFO)
    veto = _veto_by_section()
    veto_emptied = None
    veto_silenced = []
    veto_shrunk = []
    if veto is not None:
        veto_emptied = []
        for ch, (_felt, toks) in _channel_bands().items():
            pool = set(toks)
            if not pool or ch not in veto:
                continue
            removed, has_guard = veto[ch]
            after = pool - removed
            if not after and not has_guard:
                veto_emptied.append(ch)
            elif not after:
                veto_silenced.append(ch)
            elif len(after) < len(pool):
                veto_shrunk.append((ch, len(pool), len(after)))

    # 12 level coverage: every playable base-game level binds an ambients/<level>.ltx
    bound = {fn[:-4].lower() for fn in os.listdir(LEVELS) if fn.endswith(".ltx") and fn != "ambients.ltx"}
    unbound_levels = sorted(LEVELS_BASE - LEVELS_EXEMPT - bound)
    extra_bindings = sorted(bound - LEVELS_BASE)
    # 13 bed load asserts (SSndChannel::load: strict max>min, ordered periods, non-empty sounds)
    defs = _channel_defs()
    bed_bad = []
    for b in sorted(_preset_beds()):
        d = defs.get(b)
        if not d:
            continue                                    # gate 3 owns the missing definition
        per = [d[f"period{i}"] for i in range(4)]
        if (d["min_distance"] is None or d["max_distance"] is None
                or not d["max_distance"] > d["min_distance"]
                or None in per or per[0] > per[1] or per[2] > per[3]
                or d["sounds_n"] == 0):
            bed_bad.append(b)
    # 14 dynamic completeness (the sound_ambient.script nil rule: 4 periods + both distances)
    dyn = set()
    for _fn, states in _preset_state_channels().items():
        for _st, chs in states.items():
            dyn.update(chs)
    dyn_bad = []
    for c in sorted(dyn):
        d = defs.get(c)
        if not d:
            continue
        per = [d[f"period{i}"] for i in range(4)]
        if None in per or d["min_distance"] is None or d["max_distance"] is None:
            dyn_bad.append(c)
    # 15 indoor routing (INFO): an indoor channel in an outdoor state plays at 0.0 while the player
    # is in the open and at 1.0 inside safe cover - the vanilla shelter mechanism (inside_noise in
    # environment_forest). Reported so the wiring is deliberate, never a FAIL.
    indoor_out = set()
    outdoor_in = 0
    for fn, states in _preset_state_channels().items():
        for st, chs in states.items():
            for c in chs:
                d = defs.get(c)
                if not d:
                    continue
                if d["indoor"] and st not in UNDERGROUND_STATES:
                    indoor_out.add(f"{c}@{fn}[{st}]")
                if not d["indoor"] and st in UNDERGROUND_STATES:
                    outdoor_in += 1
    # 16 strike palette (INFO): reachable bolt sounds carrying our deploy vs vanilla audio.
    # Reachable = named by a bolt section inside a collection the weathers reference (gate 10 set).
    strike_ours = strike_reach = None
    van = dict(sources.mods()).get("vanilla")
    tb_p = van and os.path.join(van, "configs", "environment", "thunderbolts.ltx")
    tc_p = van and os.path.join(van, "configs", "environment", "thunderbolt_collections.ltx")
    if tb_p and os.path.exists(tb_p) and os.path.exists(tc_p):
        sec_sound = {}
        sect = None
        for ln in _read(tb_p).split("\n"):
            mh = re.match(r"\s*\[([A-Za-z0-9_\-]+)\]", ln)
            if mh:
                sect = mh.group(1).lower()
                continue
            ms = re.match(r"\s*sound\s*=\s*(\S+)", ln)
            if ms and sect:
                sec_sound[sect] = ms.group(1).replace("\\", "/").lower()
        reach = set()
        cur = None
        for ln in _read(tc_p).split("\n"):
            mh = re.match(r"\s*\[([A-Za-z0-9_]+)\]", ln)
            if mh:
                cur = mh.group(1).lower()
                continue
            mk = re.match(r"\s*([A-Za-z0-9_\-]+)\s*(=|$)", ln)
            if mk and cur in COLLECTIONS_REQUIRED:
                reach.add(mk.group(1).lower())
        reach_sounds = {sec_sound[s] for s in reach if s in sec_sound}
        strike_reach = len(reach_sounds)
        strike_ours = len(reach_sounds & {k[:-4] for k in extra})

    # 17 effect vocabulary: every effect id any preset or ambients.ltx wires must exist in the
    # base effect set, or CEnvAmbient::load CTDs on the missing section
    eff_refs = set()
    eff_files = [os.path.join(PRESETS, fn) for fn in os.listdir(PRESETS)]
    amb_p = os.path.join(ENV, "ambients.ltx")
    if os.path.exists(amb_p):
        eff_files.append(amb_p)
    for pp in eff_files:
        for m in re.findall(r"(?im)^\s*effects\s*=\s*(\S.*)$", _read(pp)):
            for one in re.split(r"[,;]", m):
                one = one.strip().lower()
                if one and "=" not in one and " " not in one:
                    eff_refs.add(one)
    eff_unknown = sorted(eff_refs - EFFECTS_BASE)

    # 18 effect sound paths: every sound = in the effect override must resolve to a file on disk, or
    # the effect plays silent - GamePersistent WeathersUpdate skips a null handle with no other trace.
    # No channel reads the override, so gate 4 never sees these paths (silent-ship found 2026-09-07).
    eff_snd_missing = []
    eff_override = os.path.join(ENV, "mod_effects_alifeambience.ltx")
    if os.path.exists(eff_override):
        for m in re.findall(r"(?im)^\s*sound\s*=\s*(\S+)", _read(eff_override)):
            p = m.strip().lower().replace("\\", "/")
            if p.endswith(".ogg"):
                p = p[:-4]
            if not path_on_disk(p):
                eff_snd_missing.append(p)
    eff_snd_missing = sorted(set(eff_snd_missing))

    rows = [
        ("1 orphan files (on disk, unwired)", len(orphan_files), "FAIL"),
        ("2 orphan channels (defined, unreferenced)", len(orphan_channels), "INFO"),
        ("3 dangling refs (referenced, undefined)", len(dangling), "FAIL"),
        ("4 missing paths (channel -> no file)", len(missing_paths), "FAIL"),
        ("5 level-routing errors", len(level_bad), "FAIL"),
        ("6 weather-matrix gaps", len(matrix_gaps), "FAIL"),
        ("7 retention: unaccounted source files", len(unaccounted), "FAIL"),
        ("8 density: states over budget", len(over_budget), "FAIL" if DENSITY_BUDGET else "INFO"),
        ("9 pool lines over the ini buffer cap", len(over_cap), "FAIL"),
        ("10 weather-mod collections unresolved", len(missing_coll), "FAIL"),
        ("11 pools the AlifeSpooks veto empties WITHOUT its no_sound guard",
         len(veto_emptied) if veto_emptied is not None else 0,
         "FAIL" if veto_emptied is not None else "INFO"),
        ("12 base levels without an ambient binding", len(unbound_levels), "FAIL"),
        ("13 bed channels violating the engine load asserts", len(bed_bad), "FAIL"),
        ("14 dynamic channels with incomplete definitions", len(dyn_bad), "FAIL"),
        ("15 indoor channels in outdoor states (shelter-only)", len(indoor_out), "INFO"),
        ("16 reachable strike sounds still on vanilla audio",
         (strike_reach - strike_ours) if strike_reach is not None else 0, "INFO"),
        ("17 effect ids outside the base effect set", len(eff_unknown), "FAIL"),
        ("18 effect sounds with no file on disk", len(eff_snd_missing), "FAIL"),
    ]
    with open(os.path.join(HERE, "ledger.tsv"), "w") as fh:
        fh.write("invariant\tcount\tseverity\n")
        for k, v, sev in rows:
            fh.write(f"{k}\t{v}\t{sev}\n")
    print("  GATE LEDGER")
    failed = False
    for k, v, sev in rows:
        status = "INFO" if sev == "INFO" else ("PASS" if v == 0 else "FAIL")
        failed = failed or (status == "FAIL")
        print(f"    {status}  {k}: {v}")
    if dangling:
        print("    dangling:", dangling[:12])
    if orphan_files:
        print("    orphans:", orphan_files[:8])
    if unaccounted:
        print("    unaccounted:", unaccounted[:8])
    if veto_emptied:
        print("    veto-emptied pools (NO no_sound guard):", veto_emptied[:8])
    if veto_silenced:
        print(f"    veto-silenced channels (guarded, Spooks-owned content): {len(veto_silenced)}",
              veto_silenced[:6])
    if veto_shrunk:
        worst = sorted(veto_shrunk, key=lambda r: r[2] / r[1])[:4]
        print("    veto shrink (designed coexistence, worst): " +
              "; ".join(f"{c} {b}->{a}" for c, b, a in worst))
    if veto is None:
        print("    (AlifeSpooks repo not present - veto gate skipped)")
    if unbound_levels:
        print("    unbound levels:", unbound_levels)
    if extra_bindings:
        print(f"    bindings outside the base level set (inert on a base install): "
              f"{len(extra_bindings)} {extra_bindings[:6]}")
    if bed_bad:
        print("    bed assert violations:", bed_bad[:8])
    if dyn_bad:
        print("    incomplete dynamics:", dyn_bad[:8])
    if indoor_out:
        print("    indoor-in-outdoor:", sorted(indoor_out)[:8])
    if outdoor_in:
        print(f"    outdoor channels inside underground states (play at 0.3): {outdoor_in}")
    if strike_reach is not None:
        print(f"    strike palette: {strike_ours}/{strike_reach} reachable bolt sounds carry our deploy")
    else:
        print("    (vanilla configs not present - strike palette gate skipped)")
    if eff_unknown:
        print("    unknown effect ids:", eff_unknown[:10])
    dmax = max(density_rows, key=lambda r: r[2]) if density_rows else None
    if dmax:
        print(f"    density: max {dmax[2]} events/min at {dmax[0]}[{dmax[1]}]; "
              f"entry-burst worst {burst_worst[0]} channels at {burst_worst[1]} "
              f"(budget {'unset - report only' if not DENSITY_BUDGET else 'per-class regression ceilings'})")
    print("    retention per source: " +
          "; ".join(f"{n} ref {a['referenced']} disp {a['disposed']} un {a['unaccounted']}"
                    for n, a in per_source.items()))
    json.dump({"orphan_files": orphan_files[:200], "orphan_channels": orphan_channels,
               "dangling": dangling, "missing_paths": missing_paths, "level_bad": level_bad,
               "matrix_gaps": matrix_gaps, "unaccounted": unaccounted,
               "density": sorted(density_rows, key=lambda r: -r[2])[:40],
               "veto_emptied": veto_emptied or [], "veto_silenced": sorted(veto_silenced),
               "veto_shrunk": sorted(veto_shrunk),
               "unbound_levels": unbound_levels, "extra_bindings": extra_bindings,
               "bed_bad": bed_bad, "dyn_bad": dyn_bad, "indoor_out": sorted(indoor_out)},
              open(os.path.join(HERE, "ledger_detail.json"), "w"), indent=1)
    if failed:
        raise SystemExit("verify: gate ledger has failures")


def _write_meta_script(rows):
    """Write the generated per-sound profile module: path -> { lufs, crest, peak, bv, mn, mx }."""
    def num(x, nd):
        return "nil" if x is None else repr(round(x, nd))
    lines = [
        "--- aa_sound_metadata: GENERATED by tools/merge.py, do not edit. Deployed path -> measured profile.",
        "--- Loaded once at start into the xsound meta registry (xsound.load_meta), then read by path.",
        '-- @novalidate(reason:"generated data table, regenerated by tools/merge.py")',
        "rows = {",
    ]
    for path in sorted(rows):
        lufs, crest, peak, bv, mn, mx = rows[path]
        lines.append('    ["%s"] = { lufs = %s, crest = %s, peak = %s, bv = %s, mn = %s, mx = %s },' % (
            path, num(lufs, 1), num(crest, 1), num(peak, 1), num(bv, 3), num(mn, 1), num(mx, 1)))
    lines.append("}")
    with open(META_SCRIPT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def cmd_meta():
    """Emit aa_sound_metadata.script: each deployed sound's measured profile for the in-game readout.
    Reuses level_cache (LUFS/crest/peak) and the written blob (base_volume/min/max). Runs after level, so
    the blobs are final. The engine never reads it; the mod loads it once into xsound's meta registry."""
    cache = json.load(open(LEVEL_CACHE)) if os.path.exists(LEVEL_CACHE) else {}
    rows, measured = {}, 0
    for full, rel_lc in _iter_deployed():
        h = _hash_audio(full)
        m = cache.get(h)
        if m is None:
            m = list(_measure_audio(full))
            cache[h] = m
            measured += 1
        lufs, crest, peak = m
        with open(full, "rb") as fh:
            b = _read_blob(fh.read(16384))
        mn, mx, bv = b if b else (None, None, None)
        rows[rel_lc] = (lufs, crest, peak, bv, mn, mx)
    if measured:
        json.dump(cache, open(LEVEL_CACHE, "w"))
    _write_meta_script(rows)
    print(f"meta: {len(rows)} profiles -> aa_sound_metadata.script ({measured} newly measured)")


def cmd_all():
    for name, fn in (("materialize", cmd_materialize), ("fmt", cmd_fmt), ("fold", cmd_fold),
                     ("level", cmd_level), ("meta", cmd_meta), ("fingerprint", cmd_fingerprint), ("dead", cmd_dead),
                     ("verify", cmd_verify), ("audit", cmd_audit)):
        print(f"== {name} ==")
        fn()


if __name__ == "__main__":
    stage_arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    {"import": cmd_import, "materialize": cmd_materialize, "fmt": cmd_fmt, "fold": cmd_fold,
     "level": cmd_level, "meta": cmd_meta, "fingerprint": cmd_fingerprint, "dead": cmd_dead, "verify": cmd_verify,
     "audit": cmd_audit, "stage": cmd_stage, "unstage": cmd_unstage, "all": cmd_all}.get(stage_arg, cmd_all)()
