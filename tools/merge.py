"""AlifeAmbience bed union merge.

Stages (each reads the previous stage's committed artifact):
  plan    hash every source ambient ogg, dedup by waveform, resolve path conflicts   -> manifest.json
  deploy  copy the chosen files + the sound-routing config subset                     -> gamedata/
  config  fix the known stock defects in the deployed config                          -> gamedata/
  verify  six-invariant config-closure ledger                                         -> ledger.tsv
  prov    every shipped sound -> its origin pack + path                               -> provenance.tsv

Run: python merge.py <stage>   (or `all`). Hashes cache to tools/hashes.json (gitignored).

Design:
  - Ship the whole ambient union, deduped by whole-file md5, at ORIGINAL source paths so
    AlifeSpooks's path-based veto lines up.
  - Spine = Amplified: its sound-routing config is the base; its sound copy is the largest.
  - Path conflict (same relative path, different audio across packs): the AUDIBLE MASTER wins
    (RETUNE / myRETUNE) for background bed loops; otherwise the spine wins.
  - Never ship the bundled non-sound logic (surge/psi managers, weather graph, thunderbolts,
    unrelated system mods) - that fights GAMMA / Atmospherics. Keep only the ambient sound config.
"""
import os, sys, json, hashlib, shutil, re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
GD = os.path.join(REPO, "gamedata")
sys.path.insert(0, HERE)
import sources  # noqa

SPINE = "Amplified"
MASTERS = ("RETUNE457", "myRETUNE")  # audible background-bed masters win their paths
# registry entries kept for licence/provenance but NOT materialized:
#   vanilla       - GSC full unpack, non-ambient, huge; beds already come via Amplified/Soundscape
#   ShrikeInterior- proven 100% redundant (0 unique md5) by the dedup census
MATERIALIZE_SKIP = {"vanilla", "ShrikeInterior"}
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


# ---- graft: wire the union content into the config (research-derived placement) ----
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

# new channel: (name, [folders], params-from, [(terrain, [states])])  - placement per aa_placement.ltx:
#   frogs  = wetland at dusk/night           owls/dogs = outdoor night birds/beasts (aa_placement plays
#   aa_owls in escape/garbage night, aa_dogs day-night in field levels)   bats = forest/urban/lab night
GRAFT_NEW = [
    ("frogs", ["ambient/trx/nature/frog_a", "ambient/trx/nature/frog_b", "ambient/trx/nature/frog_c"],
     "bugs_swamp", [("swamp", ["evening", "night", "morning"])]),
    ("owls", ["ambient/trx/nature/owl"], "bugs_night",
     [("outdoor", ["evening", "night"])]),
    ("dogs_amb", ["ambient/trx/nature/dog"], "bugs_night",
     [("outdoor", ["day", "evening", "night", "morning"])]),
    ("bats_amb", ["ambient/trx/nature/bats"], "bugs_night",
     [("forest", ["night"]), ("urban", ["night"])]),
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


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "plan"
    {"plan": cmd_plan, "deploy": cmd_deploy, "config": cmd_config,
     "graft": cmd_graft, "prune": cmd_prune, "verify": cmd_verify}.get(stage, cmd_plan)()
