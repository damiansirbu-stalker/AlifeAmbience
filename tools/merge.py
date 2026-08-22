"""AlifeAmbience: build the ambient soundscape from a best-of-breed pack roster, made audible by ear.

Two orchestrator commands (shape shared with AlifeSpooks):
  rebuild   full, destructive: wipe the deployed audio, regenerate the whole corpus from source.
  add       incremental: run the pipeline WITHOUT wiping (deploy skips existing, fold/level hash-cached).
            NOTE: graft APPENDS, so `add` is not idempotent - prefer `rebuild` after any config/roster change.
Run: python merge.py <command|stage>   (bare = add).

Stages, in order (each reads the previous stage's output on disk):
  plan         hash the roster packs' oggs, dedup by PATH (byte hash)                  -> manifest.json
  deploy       copy the chosen files + the Amplified config subset (the spine)         -> gamedata/
  config       fix stock defects, strip dead refs, cap spawn distance per category     -> gamedata/ cfg
  graft        wire best-of-breed folders into channels + presets, add frogs/heli      -> gamedata/ cfg
  fingerprint  acoustic dedup (Chromaprint): collapse same-recording aliases           -> gamedata/ cfg, sounds
  prune        delete every file no channel references                                 -> gamedata/sounds
  fold         stereo -> mono (re-encode) + resample off-rate to 44100                 -> sounds, fold_blobs
  master       RETIRED no-op (its min floor moved into level, crest-inverted)          -> -
  level        the two blob floors + the loudness ceiling, from one crest+LUFS pass    -> sounds, level_cache
  cull         delete silent/dead files, strip their refs (never emptying a channel)   -> gamedata/sounds
  verify       six-invariant config-closure ledger                                     -> ledger.tsv
  audit        wired min/felt-far ratio + crushed share (acceptance gate)              -> stdout

Design:
  - ROSTER, not a union: best-of-breed per category (Soundscape environment, Audio Expansion insects/
    frogs, Immersive wind/helicopter) on the Amplified config spine. RETUNE/Antares dropped.
  - Amplified is the config spine (the only pack with a complete level/weather config). The roster packs
    SHARE deploy paths, so best-of-breed emerges from fingerprint (drop acoustic aliases), level (lift the
    salvageable) and cull (drop the dead), not from folder selection.
  - Never include the bundled non-sound logic (surge/psi managers, weather graph, thunderbolts) - it fights
    the weather mods. Keep only the ambient sound config.
  - Audibility is an ENGINE problem, not loudness: stereo plays 2D, min 1-2 is crushed by OpenAL, quiet
    content stays quiet. Fixed by lossless blob edits keyed to an ear calibration: fold stereo->mono; a
    crest-inverted min-distance floor (fixes the OpenAL rolloff); and a base_volume loudness BAND (floor
    lifts quiet content, ceiling lowers hot content) to the ear-anchored -30/-36 floors and -24/-28
    ceilings (continuous / one-shot). See doc/library/anomaly/internals/sound-source-and-emitter.md.
"""
import os, sys, json, hashlib, shutil, re, struct, subprocess, math, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
GD = os.path.join(REPO, "gamedata")
sys.path.insert(0, HERE)
import sources  # noqa

SPINE = "Amplified"                              # config spine: the only pack with a complete level/weather config
MASTERS = ("Soundscape", "ImmersiveAmbience")    # roster environment winners override the spine at background beds
# The ROSTER (2026-08-22, measured + ear-anchored): best-of-breed per category, not a union.
#   Amplified  - config spine + birds; its wind/foliage culled (muffled/stereo, 21%/0% dead but quiet)
#   Soundscape - environment core: wind, weather, birds, foliage (mono, present, low content-limited)
#   Immersive  - wind reinforcement + helicopter (loud, mono)
#   AudioExp   - insects + frogs (loud, mono, distinct)
# registry entries kept for licence/provenance but NOT materialized:
#   vanilla       - GSC full unpack, non-ambient, huge
#   ShrikeInterior- proven 100% redundant (0 unique md5) by the dedup census
#   RETUNE457 / myRETUNE - the RETUNE/Antares family; dropped (RETUNE + loudness, 48% stereo, no unique craft)
MATERIALIZE_SKIP = {"vanilla", "ShrikeInterior", "RETUNE457", "myRETUNE"}
# only these sound roots are the ambient bed; excludes weapons/voice/etc. under a full unpack
AMBIENT_MARKERS = ("/sounds/ambient/", "/sounds/ambience_exp/")

# the sound-routing config subset we keep from the spine (relative to gamedata/)
KEEP_CONFIG_DIRS = [
    "configs/environment/ambients",             # ambients.ltx lives one level up; dir = level files + presets
    "configs/environment/ambient_channels",     # backgrounds.ltx + blowout_channels.ltx
]
KEEP_CONFIG_FILES = [
    "configs/environment/ambients.ltx",
    "configs/environment/sound_channels.ltx",
]
# non-sound logic bundled in the packs that we NEVER ship (fights GAMMA/Atmospherics)
DROP_CONFIG_RE = re.compile(
    r"(dynamic_weather_graphs|thunderbolt|weather_effects|surge_manager|psi_storm_manager"
    r"|mod_system_|mod_animations_settings)", re.I)

# the four stock dangling-ref defects found by the baseline audit (invariant 3)
DEFECT_FIXES = {
    "wind_trong": "wind_strong",   # typo
    # branch_spook / bugs / drones_day: no valid target - drop the ref (handled in config stage)
}
DEFECT_DROP = {"branch_spook", "bugs", "drones_day"}


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


def cmd_plan():
    sources.check_licences(public=False)
    cache = _load_hashes()
    order = [name for name, _ in sources.mods()]
    # gather: per source, list of (rel, fullpath, md5)
    per_source = {}
    for name, gd in sources.mods():
        if name in MATERIALIZE_SKIP:
            continue
        rows = []
        for full, rel in _iter_oggs(gd):
            md5 = cache.get(full)
            if md5 is None:
                md5 = _hash(full)
                cache[full] = md5
            # rel_lc = case-insensitive dedup/conflict key; rel = original-case deploy path
            rows.append((rel.lower(), rel, full, md5))
        per_source[name] = rows
        print(f"  hashed {name}: {len(rows)} oggs")
    _save_hashes(cache)

    # dedup by PATH (the config-referenceable location), not by waveform: the config points at exact
    # paths, and the same audio at two different paths is two distinct locations both channels may use,
    # so each must ship. For each unique path, pick one source's file.
    # priority: spine first (owns its paths), then masters (override spine at background beds), then rest.
    prio = [SPINE] + [m for m in MASTERS if m != SPINE] + [n for n in order if n not in (SPINE,) + MASTERS]
    path_choice = {}     # rel_lc -> (source, rel_orig, full, md5)
    overrides = 0
    for name in prio:
        for rel_lc, rel, full, md5 in per_source.get(name, []):
            if rel_lc not in path_choice:
                path_choice[rel_lc] = (name, rel, full, md5)
                continue
            owner_name = path_choice[rel_lc][0]
            # an audible master overrides the spine's (dead) copy at a background bed path
            if name in MASTERS and owner_name == SPINE and "background" in rel_lc:
                path_choice[rel_lc] = (name, rel, full, md5)
                overrides += 1
            # else keep the existing owner (earlier-in-priority wins)

    shipped = {rel: {"source": name, "md5": md5, "full": full}
               for (name, rel, full, md5) in path_choice.values()}
    waveforms = len(set(md5 for (_, _, _, md5) in path_choice.values()))

    manifest = {
        "sources": [n for n in order if n not in MATERIALIZE_SKIP],
        "spine": SPINE,
        "masters": list(MASTERS),
        "total_source_oggs": sum(len(v) for v in per_source.values()),
        "unique_paths": len(path_choice),
        "unique_waveforms": waveforms,
        "master_overrides": overrides,
        "shipped_paths": len(shipped),
        "shipped": shipped,
    }
    json.dump(manifest, open(os.path.join(HERE, "manifest.json"), "w"), indent=1)
    print(f"  total source oggs : {manifest['total_source_oggs']}")
    print(f"  unique waveforms  : {manifest['unique_waveforms']}")
    print(f"  shipped paths     : {manifest['shipped_paths']}")


def cmd_deploy():
    manifest = json.load(open(os.path.join(HERE, "manifest.json")))
    # 1. audio
    copied = skipped = 0
    for rel, info in manifest["shipped"].items():
        dst = os.path.join(GD, "sounds", rel.replace("/", os.sep))
        if os.path.exists(dst):
            skipped += 1
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(info["full"], dst)
        copied += 1
    print(f"  audio: copied {copied}, skipped(existing) {skipped}")
    # 2. config subset from the spine (dropping the non-sound logic)
    spine_gd = dict(sources.mods())[SPINE]
    n = 0
    for base in KEEP_CONFIG_DIRS:
        src = os.path.join(spine_gd.replace("/", os.sep), base.replace("/", os.sep))
        for dp, _, fns in os.walk(src):
            for fn in fns:
                if not fn.lower().endswith(".ltx"):
                    continue
                if DROP_CONFIG_RE.search(fn):
                    continue
                s = os.path.join(dp, fn)
                rel = os.path.relpath(s, spine_gd.replace("/", os.sep))
                d = os.path.join(GD, rel)
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
                n += 1
    for f in KEEP_CONFIG_FILES:
        s = os.path.join(spine_gd.replace("/", os.sep), f.replace("/", os.sep))
        if os.path.exists(s):
            d = os.path.join(GD, f.replace("/", os.sep))
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
            n += 1
    print(f"  config: copied {n} sound-routing ltx (dropped non-sound logic)")


# ---- config wiring ----

ENV = os.path.join(GD, "configs", "environment")
PRESETS = os.path.join(ENV, "ambients", "presets")
LEVELS = os.path.join(ENV, "ambients")
CHANNEL_FILES = [os.path.join(ENV, "ambient_channels", "backgrounds.ltx"),
                 os.path.join(ENV, "ambient_channels", "blowout_channels.ltx"),
                 os.path.join(ENV, "sound_channels.ltx")]
# Atmospherics ambient-state vocabulary (the weather matrix columns)
WEATHER_STATES = ["day", "morning", "evening", "night", "rain", "rain_day", "rain_night",
                  "storm_day", "storm_night", "tuman", "tuman_night", "indoor_underground"]
UNDERGROUND_STATE = "indoor_underground"


def _read(p):
    return open(p, encoding="utf-8", errors="replace").read()


# Gentle per-category spawn-distance cap: a category's channels should not spawn TOO far (System B felt ~
# max_distance/2). Channel-name keyed, lower-only, guarded so max stays > min (engine assert). Applied by the
# pipeline, not by hand. Values are ear-tune starting points, like the loudness floors.
SPAWN_CAP = {"wind": 130.0}   # wind 200 -> 130 (felt ~100 -> ~65): nudge the far ones without collapsing them


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


def cmd_config():
    """Fix the four stock dangling-ref defects (invariant 3) in the deployed presets."""
    fixed = {"rename": 0, "drop": 0}
    for fn in os.listdir(PRESETS):
        p = os.path.join(PRESETS, fn)
        txt = _read(p)
        orig = txt
        # rename wind_trong -> wind_strong (whole-word)
        txt2 = re.sub(r"\bwind_trong\b", "wind_strong", txt)
        if txt2 != txt:
            fixed["rename"] += txt.count("wind_trong")
        txt = txt2
        # drop the three undefined channels from any sound_channels/_dynamic list
        for bad in DEFECT_DROP:
            def _strip(m):
                items = [c.strip() for c in re.split(r"[,;]", m.group(2)) if c.strip()]
                items = [c for c in items if c.lower() != bad]
                fixed["drop"] += 1
                return m.group(1) + ", ".join(items)
            txt = re.sub(r"(sound_channels(?:_dynamic)?\s*=\s*)([^\n]*\b" + re.escape(bad) + r"\b[^\n]*)",
                         _strip, txt, flags=re.I)
        if txt != orig:
            open(p, "w", encoding="utf-8").write(txt)
    # 5th stock defect: `aambient\...\drone32` double-a typo in sound_channels.ltx (unreachable path)
    typo = 0
    for f in CHANNEL_FILES:
        if os.path.exists(f):
            t = _read(f)
            t2 = t.replace("aambient\\", "ambient\\").replace("aambient/", "ambient/")
            if t2 != t:
                typo += t.count("aambient")
                open(f, "w", encoding="utf-8").write(t2)
    # strip genuinely-dead channel refs: a `sounds=` entry whose file (or folder, for a random-pick
    # ref) is absent on disk. Keeps folder refs and no_sound; guards against emptying a channel.
    sroot = os.path.join(GD, "sounds")
    disk = set()
    for dp, _, fns in os.walk(sroot):
        for fn in fns:
            if fn.lower().endswith(".ogg"):
                disk.add(os.path.relpath(os.path.join(dp, fn), sroot).replace("\\", "/").lower())
    disk_dirs = {os.path.dirname(d) for d in disk}
    dead = 0
    for f in CHANNEL_FILES:
        if not os.path.exists(f):
            continue
        out = []
        for ln in _read(f).split("\n"):
            m = re.match(r"(\s*sounds\d*\s*=\s*)(\S.*)$", ln, re.I)
            if m:
                keep = []
                for one in re.split(r"[,;]", m.group(2)):
                    e = one.strip()
                    t = e.replace("\\", "/").lower()
                    if not t:
                        continue
                    if t == "ambient/no_sound" or (t + ".ogg") in disk or t in disk_dirs:
                        keep.append(e)
                    else:
                        dead += 1
                if not keep:
                    keep = ["ambient\\no_sound"]
                ln = m.group(1) + ", ".join(keep)
            out.append(ln)
        open(f, "w", encoding="utf-8").write("\n".join(out))
    print(f"  defect fix: wind_trong x{fixed['rename']}, bad-ref lists x{fixed['drop']}, "
          f"aambient x{typo}, dead channel refs stripped x{dead}")
    _cap_spawn_distances()


# ---- graft: wire best-of-breed folders into the config (research-derived placement) ----
# Placement is DERIVED, not chosen: the folder name states zone+time, the preset pattern states which
# channel plays where, and most species already have a channel (enrich it). Evidence: environment_swamp
# schedules bugs_swamp/birds_night by time; Audio Expansion ships insect_swamp_night, insect_morning,
# frog_a; the channel list already defines insects/birds_night/crows/wind_*.

# folder under sounds/ -> existing channel to enrich (append its files to that channel's `sounds=`)
GRAFT_ENRICH = {
    "ambient/trx/nature/insect": "insects",
    "ambient/trx/nature/insect_day_long": "insects",
    "ambient/trx/nature/insect_morning": "insects",
    "ambient/trx/nature/flie": "insects",
    "ambient/trx/nature/insect_night": "Insects_night",
    "ambient/trx/nature/cricket": "bugs_night",
    "ambient/trx/nature/insect_swamp_night": "bugs_night",
    "ambient/trx/nature/insect_evening_long": "bugs_swamp",
    "ambient/trx/nature/insect_swamp_day": "bugs_swamp",
    "ambient/trx/nature/birds": "birds",
    "ambient/trx/nature/birds_night": "birds_night",
    "ambient/trx/nature/gull": "birds_swamp",
    "ambient/trx/nature/crow": "crows",
    "ambient/trx/nature/rustle": "foliage",
    "ambient/trx/nature/whispers": "foliage_spook",
    "ambient/trx/nature/storm": "storm",
    "ambient/trx/nature/wind_normal": "wind_normal",
    "ambient/trx/nature/wind_forest": "wind_forest",
    "ambient/trx/nature/wind_gust": "wind_gust",
    "ambient/trx/nature/wind_heavy": "wind_heavy",
    "ambient/trx/nature/wind_tuman": "wind_normal",
    "ambient/trx/nature/wind_dark": "wind_normal",
    "ambient/soundscape/nature/wind_normal": "wind_normal",
    "ambient/soundscape/nature/wind_forest": "wind_forest",
    "ambient/soundscape/nature/wind_gust": "wind_gust",
    "ambient/soundscape/nature/wind_heavy": "wind_heavy",
    "ambient/soundscape/nature/wind_tuman": "wind_normal",
    "ambient/soundscape/nature/wind_dark": "wind_normal",
    "ambient/soundscape/insects/stereo": "insects",
    "ambience_exp/wind_random": "wind_normal",
    "ambience_exp/wind_random/mono": "wind_normal",
    "ambience_exp/wind_random/stereo": "wind_normal",
    "ambience_exp/wind_interior": "wind_urban",
    "ambience_exp/wind_interior/stereo": "wind_urban",
    "ambience_exp/wind_strong": "wind_strong",
    "ambience_exp/rain": "rain_gust",
    "ambience_exp/rain_footstep": "rain_gust",
    "ambient/outdoors": "wind_normal",
    "ambient/rnd_outdoor": "wind_normal",
    "ambient/soundscape/nature": "wind_normal",
    "ambient/soundscape/forest_night": "wind_forest",
}
# TERRAIN -> presets, DERIVED by joining AlifeSpooks/as_static_map.ltx (level terrain) with each
# deployed ambients/<level>.ltx #include. The preset NAMES are misleading (environment_forest is used
# by a FIELD level, environment_darkscape by red_forest) so terrain must come from the join, not names.
# Confirmed vs STALKER canon: Zaton/Yantar/Marsh = wetland, Red Forest/Military = forest.
TERRAIN_PRESETS = {
    "swamp":  ["environment_swamp", "environment_yantar", "environment_zaton"],
    "forest": ["environment_darkscape", "environment_field_army"],
    "field":  ["environment_cemetary", "environment_darkvalley", "environment_field",
               "environment_field_northalt", "environment_forest", "environment_garbage",
               "environment_generators", "environment_jupiter"],
    "urban":  ["environment_hospital", "environment_npp", "environment_pripyat",
               "environment_pripyat_outskirts", "environment_rostok", "environment_rostok_wild"],
}
TERRAIN_PRESETS["outdoor"] = (TERRAIN_PRESETS["swamp"] + TERRAIN_PRESETS["forest"]
                              + TERRAIN_PRESETS["field"])

# new channel: (name, [folders], params-from-template, [(terrain, [states])]). The roster's two genuinely-new
# categories - frogs (wetland at dusk/night, near placement) and the helicopter (a rare distant outdoor event).
# Night-birds and time-insects are NOT here: the spine already has birds_night / Insects_night channels, so
# those are enrichment (GRAFT_ENRICH), not new channels. Placement (spawn distance) comes from the template.
GRAFT_NEW = [
    ("frogs", ["ambient/trx/nature/frog_a", "ambient/trx/nature/frog_b", "ambient/trx/nature/frog_c"],
     "bugs_swamp", [("swamp", ["evening", "night", "morning"])]),
    ("helicopter", ["ambience_exp/helicopter"], "storm",
     [("outdoor", ["day", "evening", "night", "morning"])]),
]
SC = os.path.join(ENV, "sound_channels.ltx")


def _folder_files(folder):
    """deployed sound paths (backslash, no ext) under a folder, for a `sounds=` list."""
    d = os.path.join(GD, "sounds", folder.replace("/", os.sep))
    out = []
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith(".ogg"):
                out.append((folder + "/" + fn[:-4]).replace("/", "\\"))
    return out


def cmd_graft():
    txt = _read(SC)
    enriched = created = wired = 0
    # 1. enrich existing channels: append folder files to the channel's sounds= list
    for folder, chan in GRAFT_ENRICH.items():
        files = _folder_files(folder)
        if not files:
            continue
        # find [chan] ... sounds = <val>  (case-insensitive channel, first sounds= in the block)
        pat = re.compile(r"(\[" + re.escape(chan) + r"\][^\[]*?\n\s*sounds\d*\s*=\s*)([^\n]*)", re.I)
        m = pat.search(txt)
        if not m:
            continue
        txt = txt[:m.end(2)] + ", " + ", ".join(files) + txt[m.end(2):]
        enriched += 1
    # 2. new channels: append a block cloned from a template channel's params
    for name, folders, tmpl, _presets in GRAFT_NEW:
        files = []
        for f in folders:
            files += _folder_files(f)
        if not files:
            continue
        tm = re.search(r"\[" + re.escape(tmpl) + r"\]([^\[]*?)\n\s*sounds\d*\s*=", txt, re.I)
        params = tm.group(1).rstrip() if tm else "\n        max_distance = 75\n        min_distance = 15\n        period0 = 10000\n        period1 = 30000\n        period2 = 10000\n        period3 = 30000"
        block = f"\n[{name}]\t;grafted{params}\n        sounds                           = " + ", ".join(files) + "\n"
        txt += block
        created += 1
    open(SC, "w", encoding="utf-8").write(txt)
    # 3. wire new channels into every preset of the matching TERRAIN, for the given states
    for name, _f, _t, terr_specs in GRAFT_NEW:
        for terrain, states in terr_specs:
            for preset in TERRAIN_PRESETS[terrain]:
                pp = os.path.join(PRESETS, preset + ".ltx")
                if not os.path.exists(pp):
                    continue
                pt = _read(pp)
                for st in states:
                    sec = re.compile(r"(\[" + st + r"\][^\[]*?sound_channels_dynamic\s*=\s*)([^\n]*)", re.I)
                    mm = sec.search(pt)
                    if mm and name.lower() not in mm.group(2).lower():
                        pt = pt[:mm.end(2)] + f", {name}" + pt[mm.end(2):]
                        wired += 1
                open(pp, "w", encoding="utf-8").write(pt)
    print(f"  graft: enriched {enriched} channels, created {created} new channels, wired {wired} preset slots")
    _split_sound_lines()


# the engine reads each `sounds =` value into a fixed ~4096 buffer (SoundRender_Core.cpp:249,
# r_stringZ; FS.cpp:467 asserts sz < tgt_sz). Stock Amplified's longest line was 4091 -- right under
# it. A line over the buffer is a hard CTD on config load. So SPLIT an over-long channel into
# sub-channels (<name>__2, __3, ...), each under the cap, and reference all of them in every preset
# that referenced the original -- NO sound is dropped, the engine just picks across the sub-channels.
LINE_CAP = 3900


def _split_sound_lines():
    split_map = {}   # original channel (lower) -> [sub-channel names]
    for f in CHANNEL_FILES:
        if not os.path.exists(f):
            continue
        txt = _read(f)
        parts = re.split(r"(?m)^(?=\[[A-Za-z0-9_]+\])", txt)
        preamble = parts[0] if parts and not parts[0].lstrip().startswith("[") else ""
        blocks = parts[1:] if preamble else parts
        out = []
        for blk in blocks:
            hm = re.match(r"\[([A-Za-z0-9_]+)\]", blk)
            sm = re.search(r"(?im)^(\s*sounds\d*\s*=\s*)(.+)$", blk)
            if not hm or not sm or len((sm.group(1) + sm.group(2)).rstrip()) <= LINE_CAP:
                out.append(blk)
                continue
            name, head = hm.group(1), sm.group(1)
            items = [it.strip() for it in re.split(r"[,;]", sm.group(2)) if it.strip()]
            chunks, cur = [], []
            for it in items:
                if cur and len(head + ", ".join(cur + [it])) > LINE_CAP:
                    chunks.append(cur)
                    cur = []
                cur.append(it)
            if cur:
                chunks.append(cur)
            pre, post = blk[:sm.start()], blk[sm.end():]   # params before / after the sounds line
            out.append(pre + head + ", ".join(chunks[0]) + post)
            subs = []
            for i, ch in enumerate(chunks[1:], start=2):
                sub = f"{name}__{i}"
                subs.append(sub)
                nb = re.sub(r"^\[" + re.escape(name) + r"\]", f"[{sub}]", pre, count=1)
                out.append(nb + head + ", ".join(ch) + (post if post.strip() else "\n"))
            split_map[name.lower()] = subs
        open(f, "w", encoding="utf-8").write((preamble or "") + "".join(out))
    # reference the sub-channels in every preset that referenced the original
    if split_map:
        def _add_subs(m):
            key, val = m.group(1), m.group(2)
            refs = [r.strip() for r in re.split(r"[,;]", val) if r.strip()]
            have = {r.lower() for r in refs}
            add = [s for r in refs for s in split_map.get(r.lower(), []) if s.lower() not in have]
            return key + val.rstrip() + (", " + ", ".join(add) if add else "")
        for fn in os.listdir(PRESETS):
            pp = os.path.join(PRESETS, fn)
            pt = re.sub(r"(?im)^(\s*sound_channels(?:_dynamic)?\s*=\s*)(.+)$", _add_subs, _read(pp))
            open(pp, "w", encoding="utf-8").write(pt)
    total = sum(len(v) for v in split_map.values())
    print(f"  split: {len(split_map)} over-long channels -> +{total} sub-channels (every sound kept)")
    _normalize_dynamic()


def _normalize_dynamic():
    """Preset sound_channels / _dynamic lines: some source lines end in a `;` (an ltx comment
    terminator). Appending grafts/sub-channels AFTER the `;` buries them in a comment (ignored) and
    the malformed `;,` can break the line. Normalize: treat every `,`/`;`-separated token as a
    channel, dedupe, drop the `;`, rejoin -- so all channels (original + grafted) are live."""
    fixed = 0
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
                if tok and tok.lower() not in seen:
                    seen.add(tok.lower())
                    chans.append(tok)
            new = m.group(1) + ", ".join(chans)
            if new != ln:
                fixed += 1
            out.append(new)
        open(pp, "w", encoding="utf-8").write("\n".join(out))
    print(f"  normalize: fixed {fixed} preset channel lines (stripped ';' comment traps)")


# ---- verify: six-invariant config-closure ledger ----

def _defined_channels():
    ch = set()
    for f in CHANNEL_FILES:
        if os.path.exists(f):
            ch |= {m.lower() for m in re.findall(r"^\s*\[([A-Za-z0-9_]+)\]", _read(f), re.M)}
    return ch


def _tok_ok(t):
    t = t.strip().replace("\\", "/").lower()
    # a real sound path: has a folder separator, no key/space garbage, not the silent placeholder
    if not t or t == "ambient/no_sound" or "=" in t or " " in t or "\t" in t or "/" not in t:
        return None
    return t


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


def cmd_verify():
    defined = _defined_channels()
    referenced = _preset_refs()
    chan_paths = _channel_paths()
    # disk sound set (lowercased rel under sounds/)
    disk = set()
    sroot = os.path.join(GD, "sounds")
    for dp, _, fns in os.walk(sroot):
        for fn in fns:
            if fn.lower().endswith(".ogg"):
                rel = os.path.relpath(os.path.join(dp, fn), sroot).replace("\\", "/").lower()
                disk.add(rel)
    disk_dirs = {os.path.dirname(d) for d in disk}

    # inv1 orphan files: on disk, no channel path points at the file or its folder
    def covered(rel):
        if rel in chan_paths:
            return True
        return os.path.dirname(rel) in {os.path.dirname(p) for p in chan_paths}
    orphan_files = sum(1 for d in disk if not covered(d))
    # inv2 orphan channels: defined, never referenced
    orphan_channels = sorted(defined - referenced)
    # inv3 dangling refs: referenced, not defined
    dangling = sorted(referenced - defined)
    # inv4 missing paths: channel path with no file on disk (file OR folder)
    def path_on_disk(p):
        return (p + ".ogg") in disk or p in disk_dirs or any(d.startswith(p + "/") for d in disk_dirs)
    missing_paths = sorted(p for p in chan_paths if not path_on_disk(p))
    # inv5 level routing
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
    # inv6 weather matrix: each preset covers its states (outdoor -> 11, underground -> indoor_underground)
    matrix_gaps = []
    for fn in os.listdir(PRESETS):
        secs = {s.lower() for s in re.findall(r"^\s*\[([A-Za-z0-9_]+)\]", _read(os.path.join(PRESETS, fn)), re.M)}
        is_ug = "underground" in fn.lower()
        need = [UNDERGROUND_STATE] if is_ug else [s for s in WEATHER_STATES if s != UNDERGROUND_STATE]
        miss = [s for s in need if s not in secs]
        if miss:
            matrix_gaps.append((fn, miss))

    # (name, count, severity) - orphan channels are INFO: an unused channel definition is harmless
    rows = [
        ("1 orphan files (on disk, unwired)", orphan_files, "FAIL"),
        ("2 orphan channels (defined, unreferenced)", len(orphan_channels), "INFO"),
        ("3 dangling refs (referenced, undefined)", len(dangling), "FAIL"),
        ("4 missing paths (channel -> no file)", len(missing_paths), "FAIL"),
        ("5 level-routing errors", len(level_bad), "FAIL"),
        ("6 weather-matrix gaps", len(matrix_gaps), "FAIL"),
    ]
    with open(os.path.join(HERE, "ledger.tsv"), "w") as fh:
        fh.write("invariant\tcount\tseverity\n")
        for k, v, sev in rows:
            fh.write(f"{k}\t{v}\t{sev}\n")
    print("  CONFIG-CLOSURE LEDGER")
    for k, v, sev in rows:
        status = "INFO" if sev == "INFO" else ("PASS" if v == 0 else "FAIL")
        print(f"    {status}  {k}: {v}")
    if dangling:
        print("    dangling:", dangling[:12])
    if level_bad:
        print("    level-bad:", level_bad[:6])
    if matrix_gaps:
        print("    matrix-gaps:", matrix_gaps[:6])
    # detail for the orphan graft work
    json.dump({"orphan_channels": orphan_channels, "dangling": dangling,
               "missing_paths": missing_paths, "level_bad": level_bad,
               "matrix_gaps": matrix_gaps},
              open(os.path.join(HERE, "ledger_detail.json"), "w"), indent=1)


def cmd_prune():
    """Delete only files that NO channel references. Keep EVERY channel definition. A channel can be
    referenced from ambients.ltx, a per-level file, or the engine's base fallbacks (default_ambient_*)
    that are not visible in the shipped config -- dropping one is a 'can't open section' CTD, while an
    unused channel def is harmless. So the safe rule: a file survives iff some channel's `sounds=`
    points at it (or its folder); channels are never dropped."""
    keep = set()
    for f in CHANNEL_FILES:
        if not os.path.exists(f):
            continue
        for m in re.findall(r"(?im)^\s*sounds\d*\s*=\s*(.+)$", _read(f)):
            for one in re.split(r"[,;]", m):
                t = _tok_ok(one)
                if t:
                    keep.add(t)
    keep_dirs = {os.path.dirname(p) for p in keep}
    sroot = os.path.join(GD, "sounds")
    removed = 0
    for dp, _, fns in os.walk(sroot):
        for fn in fns:
            if not fn.lower().endswith(".ogg"):
                continue
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, sroot).replace("\\", "/").lower()
            if rel not in keep and os.path.dirname(rel) not in keep_dirs:
                os.remove(full)
                removed += 1
    for dp, _, _ in os.walk(sroot, topdown=False):
        try:
            if not os.listdir(dp):
                os.rmdir(dp)
        except OSError:
            pass
    print(f"  prune: removed {removed} files no channel references (all channels kept)")


# ---- audibility: the engine facts behind the fold + the blob floors (fold stage, then floors in level) ----
# Two engine facts (doc/library/anomaly/internals/sound-source-and-emitter.md) make most of a merged
# ambient corpus INAUDIBLE at range even when the files sound fine at-ear:
#   1. A STEREO ogg force-plays 2D at-ear at full volume, escaping both distance rolloffs (":258-268").
#      Only MONO spatialises. So every stereo bed/one-shot plays in-head, ignoring placement.
#   2. Every 3D voice is attenuated TWICE - X-Ray's linear fade AND OpenAL's inverse model keyed on the
#      ogg blob's min_distance (":132-181"). min 1-2 (the unset ffmpeg-era default, ~84% of this corpus)
#      costs -26..-31 dB at a 25-50 m placement BEFORE the linear fade. base_volume can't rescue it.
# The fix is two stages, in order: fold every stereo file to mono (re-encode, lossy - the one place
# byte-for-byte is impossible since the engine only positions mono), then floor each file's blob
# min_distance to a crest-inverted ratio of its channel felt-far placement (the crest-min floor, applied in
# level). base_volume and max_distance stay the author's. Off-rate files (!=44100) are resampled in the fold.

FLOOR_MAX_FRAC = 0.8     # cap the min floor below blob max so a real fade band always survives.
DEFAULT_MAX    = 100.0   # blob max for a blob-less file (corpus median from the survey).
ENCODE_Q       = 6       # libvorbis -q for the mono re-encode (high quality, deterministic).
ANTIPHASE_DB   = 3.0     # side RMS this many dB above mid -> anti-phase pair, summing cancels -> drop R.
FOLD_BLOBS     = os.path.join(HERE, "fold_blobs.json")   # author blobs captured before the fold strips them
SROOT          = os.path.join(GD, "sounds")

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
DEAD_LUFS        = -60.0   # content LUFS at/below = silent/dead (ebur128 floors true silence at ~-70) -> cull
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


def _iter_deployed():
    for dp, _, fns in os.walk(SROOT):
        for fn in fns:
            if fn.lower().endswith(".ogg"):
                full = os.path.join(dp, fn)
                rel = os.path.relpath(full, SROOT).replace("\\", "/")
                yield full, rel[:-4].lower()


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
    file's author blob to fold_blobs.json BEFORE the re-encode strips it, so master can restore its
    min/max/base_volume. Re-encode is libvorbis -q6; the audio is no longer byte-identical (unavoidable:
    the engine only spatialises mono). Idempotent-ish: a file already mono+44100 is skipped."""
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


def cmd_master():
    """Retired: the min_distance floor moved into cmd_level, where it is crest-inverted and applied from the
    same crest+LUFS measurement as the loudness floor (consolidated, matching AlifeSpooks build.py
    _normalize_blobs). Kept as a no-op for pipeline-stage compatibility."""
    print("  master: (retired - min floor now applied in level, crest-inverted)")


def cmd_audit():
    """Acceptance gate: over the WIRED files, report min/felt-far (the audibility ratio) and the crushed
    share (<0.15 = whisper). Target = the crest-inverted min floor's ratio band (0.40-0.60), so the median
    should sit ~0.4-0.5 with few crushed. Blob reads only, no ffmpeg."""
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
# Both applied together from one crest+LUFS measurement (see the ported-floor block: _crest_ratio /
# _loud_floor_for / _loudness_floor). The min floor fixes the OpenAL rolloff (crest-inverted: a sustained
# tone carries, a transient stays near-field); the loudness floor lifts quiet CONTENT the min floor cannot,
# to the ear-anchored delivered level (-30 eff beds / -36 one-shots, 2026-08-22 calibration), partial +
# capped, never lowered. Idempotent + add-ready: floors are absolute (not a corpus median), lift-only, and
# the measure is cached by AUDIO-page hash (stable across blob rewrites) so a rerun re-measures only new audio.
LEVEL_CACHE    = os.path.join(HERE, "level_cache.json")   # audio-hash -> [lufs, crest, peak]


def _hash_audio(path):
    """md5 of the audio pages only (after ID + comment/setup), so a comment-blob rewrite (master/level)
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
    """Apply both lossless blob floors to each wired file, from one crest+LUFS measurement (the min floor
    moved here from master so it can be crest-inverted, matching AlifeSpooks build.py _normalize_blobs):
      1. min_distance -> max(author, crest-inverted ratio x felt-far), capped 0.8*max  (fixes OpenAL rolloff)
      2. base_volume -> lifted so delivered loudness at felt-far reaches the ear floor (-30 eff beds /
         -36 one-shots), partial + capped, never lowered  (fixes quiet content the min floor cannot)
    Skips emission (blowout/anomaly) and unwired files. Measure cached by audio hash; lossless rewrite."""
    cache = json.load(open(LEVEL_CACHE)) if os.path.exists(LEVEL_CACHE) else {}
    fold_blobs = json.load(open(FOLD_BLOBS)) if os.path.exists(FOLD_BLOBS) else {}
    ff = _file_felt_far(_channel_bands())
    total = wrote = floored = lifted = lowered = e_skip = u_skip = no_meas = measured = 0
    gains = []
    for full, rel_lc in _iter_deployed():
        total += 1
        if rel_lc.startswith("ambient/blowout") or rel_lc.startswith("ambient/anomaly"):
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
        if _write_blob(full, mn, mx, bv):
            wrote += 1
    json.dump(cache, open(LEVEL_CACHE, "w"))
    gm = statistics.median(gains) if gains else 0.0
    gx = max(gains) if gains else 0.0
    print(f"  level: {total} files | min-floored {floored} (crest-inverted), loudness-lifted {lifted}, "
          f"lowered {lowered} (over ceiling) (median {gm:+.1f} dB, up to {gx:+.1f} dB)")
    print(f"         wrote {wrote} blobs | skipped {e_skip} emission, {u_skip} unwired, "
          f"{no_meas} unmeasurable | measured {measured} new, {len(cache) - measured} cached")


# Two orchestrator commands, two guarantees (shape shared with AlifeSpooks's rebuild/add):
#   rebuild - full, destructive, reproducible, RARE: wipes the deployed audio and regenerates the whole
#             corpus from source (re-folds every stereo file). The clean-slate reset.
#   add     - incremental, curation-safe, the EVERYDAY path: never wipes. deploy skips existing, and
#             fold/master/level are hash-cached, so only NET-NEW audio is processed. Registering a new
#             source pack in sources.py then running `add` grows the corpus without touching the rest.
# --- acoustic dedup (Chromaprint) ------------------------------------------------------------------
# `plan` dedups by BYTE hash (md5), so it keeps two files that are the SAME recording re-encoded or
# renamed (different bytes, same sound) - measured ~1.4% of the corpus. This stage dedups by ACOUSTIC
# identity: fpcalc fingerprints each file, each fingerprint group collapses to one canonical, config refs
# to the aliases repoint to it, and the alias files drop (prune then tidies up). Runs on ORIGINAL audio,
# before `fold` re-encodes it. Un-fingerprintable clips (very short) fall back to the byte dedup. Never
# empties a channel or a referenced folder. Cached by audio-page hash, stable across the later blob rewrites.
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
    """Dedup by acoustic identity (Chromaprint), catching same-recording aliases the byte hash misses.
    Keep one canonical per fingerprint group, repoint config refs to it, drop the aliases. Runs before fold
    (original audio); un-fingerprintable short clips fall back to byte dedup; never empties a channel/folder."""
    cache = json.load(open(FP_CACHE)) if os.path.exists(FP_CACHE) else {}
    by_fp = {}                                    # fingerprint -> [rel_lc, ...]
    n = measured = 0
    for full, rel_lc in _iter_deployed():
        n += 1
        h = _hash_audio(full)
        fp = cache.get(h)
        if fp is None:
            fp = _fingerprint(full)
            cache[h] = fp
            measured += 1
        if fp:                                    # un-fingerprintable clips skipped (byte dedup handled them)
            by_fp.setdefault(fp, []).append(rel_lc)
    json.dump(cache, open(FP_CACHE, "w"))
    alias = {}                                    # alias rel_lc -> canonical rel_lc
    groups = 0
    for rels in by_fp.values():
        u = sorted(set(rels))
        if len(u) < 2:
            continue
        groups += 1
        for r in u[1:]:
            alias[r] = u[0]
    if not alias:
        print(f"  fingerprint: {n} files ({measured} measured) | no acoustic aliases beyond byte dedup")
        return
    repointed = 0                                 # repoint individual file refs alias -> canonical, dedup, keep >=1
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
                    key = e.replace("\\", "/").lower()
                    if key in alias:
                        key = alias[key]
                        e = key.replace("/", "\\")
                        repointed += 1
                    if key not in keys:
                        keys.add(key)
                        seen.append(e)
                if not seen:
                    seen = ["ambient\\no_sound"]
                ln = mm.group(1) + ", ".join(seen)
            out.append(ln)
        open(f, "w", encoding="utf-8").write("\n".join(out))
    sroot = os.path.join(GD, "sounds")            # drop alias files, but never the last ogg in a folder
    folder_n = {}
    for _, rel_lc in _iter_deployed():
        d = os.path.dirname(rel_lc)
        folder_n[d] = folder_n.get(d, 0) + 1
    deleted = kept = 0
    for a in sorted(alias):
        d = os.path.dirname(a)
        if folder_n.get(d, 0) <= 1:               # last file in a folder-referenced dir -> leave it
            kept += 1
            continue
        p = os.path.join(sroot, a.replace("/", os.sep) + ".ogg")
        if os.path.exists(p):
            os.remove(p)
            folder_n[d] -= 1
            deleted += 1
    print(f"  fingerprint: {n} files ({measured} measured) | {groups} acoustic-dup groups | "
          f"repointed {repointed} refs, dropped {deleted} aliases (kept {kept} last-in-folder)")


def cmd_cull():
    """Delete DEAD deployed files (silent - the level measure found no LUFS) after the fold + floors, then
    strip their now-absent channel refs, keeping >=1 sound per channel (never empties a bed -> would CTD).
    Reuses the level cache, no extra ffmpeg. A quiet-but-real sound is KEPT (the loudness floor lifts it as
    far as it can); only true silence is removed - so best-of-breed emerges by itself: dead culled, faint lifted."""
    cache = json.load(open(LEVEL_CACHE)) if os.path.exists(LEVEL_CACHE) else {}
    removed = 0
    for full, rel_lc in _iter_deployed():
        m = cache.get(_hash_audio(full))
        if m is not None and (m[0] is None or m[0] <= DEAD_LUFS):   # silent/dead (ebur128 floors silence ~-70)
            os.remove(full)
            removed += 1
    sroot = os.path.join(GD, "sounds")                          # strip refs to now-absent files, keep >=1 per channel
    disk = set()
    for dp, _, fns in os.walk(sroot):
        for fn in fns:
            if fn.lower().endswith(".ogg"):
                disk.add(os.path.relpath(os.path.join(dp, fn), sroot).replace("\\", "/").lower())
    disk_dirs = {os.path.dirname(d) for d in disk}
    stripped = 0
    for f in CHANNEL_FILES:
        if not os.path.exists(f):
            continue
        out = []
        for ln in _read(f).split("\n"):
            mm = re.match(r"(\s*sounds\d*\s*=\s*)(\S.*)$", ln, re.I)
            if mm:
                keep = []
                for one in re.split(r"[,;]", mm.group(2)):
                    e = one.strip()
                    t = e.replace("\\", "/").lower()
                    if not t:
                        continue
                    if t == "ambient/no_sound" or (t + ".ogg") in disk or t in disk_dirs:
                        keep.append(e)
                    else:
                        stripped += 1
                if not keep:
                    keep = ["ambient\\no_sound"]
                ln = mm.group(1) + ", ".join(keep)
            out.append(ln)
        open(f, "w", encoding="utf-8").write("\n".join(out))
    print(f"  cull: removed {removed} dead files (silent); stripped {stripped} dead channel refs (channels kept non-empty)")


# Both run the same stage sequence; only the wipe differs.
def _run_pipeline():
    for name, fn in (("plan", cmd_plan), ("deploy", cmd_deploy), ("config", cmd_config),
                     ("graft", cmd_graft), ("fingerprint", cmd_fingerprint), ("prune", cmd_prune),
                     ("fold", cmd_fold), ("master", cmd_master), ("level", cmd_level), ("cull", cmd_cull),
                     ("prune", cmd_prune), ("verify", cmd_verify), ("audit", cmd_audit)):
        print(f"== {name} ==")
        fn()


def cmd_rebuild():
    """Full destructive rebuild: wipe the deployed audio, regenerate everything from source. Rare."""
    if os.path.isdir(SROOT):
        shutil.rmtree(SROOT)
        print(f"== wipe == removed {SROOT} (full rebuild)")
    _run_pipeline()


def cmd_add():
    """Incremental grow-and-resync: run the whole pipeline WITHOUT wiping. deploy skips existing,
    fold/master/level are cached, so only net-new source content is processed. The everyday path."""
    _run_pipeline()


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "plan"
    {"plan": cmd_plan, "deploy": cmd_deploy, "config": cmd_config,
     "graft": cmd_graft, "fingerprint": cmd_fingerprint, "prune": cmd_prune, "verify": cmd_verify,
     "fold": cmd_fold, "master": cmd_master, "level": cmd_level, "cull": cmd_cull, "audit": cmd_audit,
     "rebuild": cmd_rebuild, "add": cmd_add, "all": cmd_add}.get(stage, cmd_add)()
