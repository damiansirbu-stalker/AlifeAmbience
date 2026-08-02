#!/usr/bin/env python3
"""Channel-driven merge for the Zone Soundscape override.

Uses each mod's own sound_channels.ltx as the curation signal: a sound "belongs"
in a channel because some mod put it there. For each channel (union of names), it
pools every sound any mod assigns to it, dedups identical sounds by fingerprint,
and keeps the best-quality copy. Channel settings (distance/period) come from the
highest-priority mod that defines the channel.

    plan   -> merged_channels.json + a report (no deploy)

Presets and the LTX/sound emit into GammaOverrides come in the next steps.
"""
import sys, json, re, collections, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import soundpool as sp

# Channels whose curated content does not resolve from any mod's config get filled
# deliberately from a content folder. out_mutants: the distant-growl recordings live
# under soundscape/mutants and no channel def points at them, so assign them here.
MANUAL_FILL = {
    "out_mutants": {
        "root": "C:/Users/damian/Downloads/extra_mods_analysys/Dark Signal Amplified Soundscape/gamedata/sounds/ambient/soundscape/mutants",
        "pattern": "distant", "mono": False, "limit": 100000,   # no cap: capture every distant-creature call
    },
}
LOWQ_BITRATE = 32000  # drop clearly junk-bitrate files when a channel has better

# Dark scope (I9): the ONLY channels AlifeAmbience keeps. Everything else in the
# packs (generic daytime life, neutral beds, plain wind) is left to the base
# ambience. Emission (blowout_*, emission_wind) is a separate system, never touched.
# Grouped by family - the same grouping seeds the runtime per-family policy later.
DARK_KEEP = {
    # dread cues
    "out_spooks", "out_day_spoops", "out_night_spoops", "northen_spoops", "urban_spoops_night",
    "out_screams", "out_mutants", "out_dark_amb", "out_night_amb", "dark_signal",
    "foliage_spook", "crows_spook", "inside_noise", "psi_sparks", "psistorm_background",
    "background_creepy_low_wind",
    "background_forest_whisper_day", "background_forest_whisper_evening",
    "background_forest_whisper_morning", "background_forest_whisper_night", "background_forest_whisper_tuman",
    # underground horror
    "ugrnd_ambient", "ugrnd_ambient_machine", "ugrnd_ambient_new", "ugrnd_banging", "ugrnd_bkg_1",
    "ugrnd_drip", "ugrnd_drone", "ugrnd_lab", "ugrnd_metal", "ugrnd_noise", "ugrnd_rats", "ugrnd_voices",
    "underground_background_1", "underground_background_2", "underground_background_3", "underground_background_4",
    "underground_background_5", "underground_background_6", "underground_background_7", "underground_background_8", "x18",
    # tension
    "out_gunfire", "out_drone", "drones", "day_drones", "urban_drones",
    "wind_creep", "wind_creep_alt", "wind_creep_urban", "branch", "branch_big", "branch_med",
    "vest_radio", "urban_debris",
    # eerie atmosphere (owls/dogs/crows/fog - confirmed in scope)
    "owls", "dogs", "crows", "crows_clear", "crows_forest", "crows_retune", "tree_sway_fog", "birds_night",
    "background_tuman_field_open", "background_tuman_field_openalt", "background_tuman_open",
    "background_tuman_open_alt", "background_tuman_open_alt2", "background_tuman_open_urban",
    # oppressive weather
    "storm", "storm_foliage", "storm_urban", "pre_storm", "background_storm_forest", "background_rain_forest",
    "background_wind_storm", "wind_dark", "wind_gale", "wind_heavy", "wind_strong", "chimes",
    "rain_gust", "rain_urban_gust",
}

# Folder-tree capture: the packs ship far more dark content than they wire into a
# channel's sounds= list (proven by the ledger: 1103 genuinely-new unused dark
# files). So we pull dark content from the FOLDER TREES directly, not just
# channel-referenced files. First matching substring (checked in order) maps the
# file to a channel; content-hash dedup collapses cross-tree copies. This is how
# ALL the horror (distant mutants, screams, spooks, underground) gets in.
DARK_FILL = [
    ("/screams", "out_screams"),
    ("/mutants/", "out_mutants"), ("spooks_above/mutants", "out_mutants"),
    ("amb_dark", "out_dark_amb"), ("amb_night", "out_night_amb"),
    ("spooks_below/metal", "ugrnd_metal"), ("spooks_below/banging", "ugrnd_banging"),
    ("spooks_below/rats", "ugrnd_rats"), ("spooks_below/noise", "ugrnd_noise"),
    ("spooks_below/lab", "ugrnd_lab"), ("water_drip", "ugrnd_drip"), ("/drip", "ugrnd_drip"),
    ("spooks_below/machine", "ugrnd_ambient_machine"), ("spooks_below/ambient", "ugrnd_ambient"),
    ("spooks_below/drone", "ugrnd_drone"), ("spooks_above/drone", "out_drone"),
    ("spooks_below/spooks", "out_spooks"), ("spooks_above/spooks", "out_spooks"), ("/spooks/", "out_spooks"),
    ("/thunder", "storm"), ("/rain", "rain_gust"),
    ("/shooting", "out_gunfire"), ("wind_dark", "wind_heavy"),
    ("spoops/urban_drones", "urban_drones"), ("spoops/drones", "out_drone"), ("/drones", "out_drone"),
    ("northern_spoops", "out_spooks"), ("storm_debris", "storm"), ("wind_tuman", "background_tuman_open"),
    ("spooks_above", "out_spooks"), ("spooks_below", "out_spooks"), ("/underground/", "ugrnd_ambient"),
    ("thunder", "storm"), ("pre_storm", "pre_storm"), ("storm_", "storm"), ("rain_storm", "storm"),
    ("tuman", "background_tuman_open"), ("underground_", "ugrnd_ambient"),
]

# priority order: settings for a shared channel come from the first that defines it
MODS = [
    ("DarkSigWeather", "D:/Games/GAMMA/GAMMA/mods/304- Dark Signal Weather and Ambiance Audio - Shrike/gamedata"),
    ("Soundscape",     "D:/Games/GAMMA/GAMMA/mods/3- Soundscape Overhaul - Solarint/gamedata"),
    ("RETUNE",         "D:/Games/GAMMA/GAMMA/mods/457- RETUNE Ambiant Sounds - Aphrodite_child/gamedata"),
    ("Amplified",      "C:/Users/damian/Downloads/extra_mods_analysys/Dark Signal Amplified Soundscape/gamedata"),
    ("vanilla",        "D:/Games/GAMMA/Anomaly/tools/_unpacked"),   # last: only for channels no pack defines (portability coverage)
]

HERE = Path(__file__).resolve().parent


def parse_channels(gamedata):
    """channel(lower) -> {settings:[raw non-sounds lines], stems:[sound stems]}.
    Reads sound_channels.ltx plus its ambient_channels includes."""
    env = Path(gamedata) / "configs/environment"
    files = [env / "sound_channels.ltx",
             env / "ambient_channels/blowout_channels.ltx",
             env / "ambient_channels/backgrounds.ltx"]
    ch, cur = {}, None
    for f in files:
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            raw = line
            code = line.split(";", 1)[0]
            m = re.match(r"\s*\[([^\]]+)\]", code)
            if m:
                cur = m.group(1).strip().lower()
                ch.setdefault(cur, {"settings": [], "stems": []})
                continue
            if cur is None:
                continue
            if "sounds" in code and "=" in code:
                for t in code.split("=", 1)[1].split(","):
                    t = t.strip().replace("\\", "/")
                    if t and "no_sound" not in t:
                        ch[cur]["stems"].append(t)
            elif code.strip():
                ch[cur]["settings"].append(raw.rstrip())
    return ch


def resolve(stem, sounds_root):
    p = Path(sounds_root) / (stem + ".ogg")
    return p if p.exists() else None


def file_hash(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def dedup_pick(files):
    """Dedup by EXACT file content, not acoustic similarity. Mods reship identical
    files; identical bytes collapse to one, distinct sounds never merge. Among an
    identical group keep the highest bitrate (they're the same anyway). Then drop
    junk-bitrate files if the channel still has content."""
    groups = {}
    for f in files:
        f["hash"] = file_hash(f["abs"])
        groups.setdefault(f["hash"], []).append(f)
    chosen = [max(g, key=lambda f: f["bitrate"]) for g in groups.values()]
    good = [c for c in chosen if c["bitrate"] >= LOWQ_BITRATE]
    return good if good else chosen


def cmd_plan(_):
    # 1. gather every channel's assigned sounds across mods
    per_mod = {name: parse_channels(gd) for name, gd in MODS}
    orig_def, pool = {}, collections.defaultdict(list)   # orig_def: settings + original stems from priority mod
    missing = collections.Counter()
    offrate = 0
    for name, gd in MODS:
        sounds_root = Path(gd) / "sounds"
        for chan, d in per_mod[name].items():
            if chan not in DARK_KEEP:            # dark scope only (I9); skip generic life/beds/emission
                continue
            if chan not in orig_def and (d["settings"] or d["stems"]):
                orig_def[chan] = {"mod": name, "settings": d["settings"], "stems": d["stems"]}
            for stem in d["stems"]:
                f = resolve(stem, sounds_root)
                if f is None:
                    missing[name] += 1
                    continue
                info = sp.probe(str(f)) or {}
                if info.get("sample_rate") != 44100:      # X-Ray fitness: 44100 only
                    offrate += 1
                    continue
                pool[chan].append({"abs": str(f), "stem": stem, "pool": name,
                                   "bitrate": info.get("bit_rate", 0),
                                   "channels": info.get("channels", 0)})
    # 1b. manual fill for channels whose curated content does not resolve
    for chan, rule in MANUAL_FILL.items():
        root = Path(rule["root"])
        rx = re.compile(rule["pattern"], re.I)
        cands = []
        for f in sorted(root.rglob("*.ogg")):
            if not rx.search(f.as_posix()):
                continue
            info = sp.probe(str(f)) or {}
            if info.get("sample_rate") != 44100:
                continue
            if rule.get("mono") and info.get("channels") != 1:
                continue
            cands.append({"abs": str(f), "stem": f.as_posix().split("/sounds/")[-1][:-4],
                          "pool": "ManualFill", "bitrate": info.get("bit_rate", 0),
                          "channels": info.get("channels", 0)})
        cands.sort(key=lambda c: -c["bitrate"])
        pool[chan].extend(cands[:rule.get("limit", 48)])

    # 1c. FOLDER-TREE capture: pull ALL dark content from the trees, not just files a
    #     channel wires. The packs ship far more than they reference (ledger proof).
    fill_added = collections.Counter()
    for name, gd in MODS:
        sroot = Path(gd) / "sounds"
        if not sroot.is_dir():
            continue
        for f in sroot.rglob("*.ogg"):
            rel = f.as_posix().lower()
            chan = next((c for sub, c in DARK_FILL if sub in rel), None)
            if not chan:
                continue
            info = sp.probe(str(f)) or {}
            if info.get("sample_rate") != 44100:
                offrate += 1
                continue
            pool[chan].append({"abs": str(f), "stem": f.as_posix().split("/sounds/")[-1][:-4],
                               "pool": name, "bitrate": info.get("bit_rate", 0),
                               "channels": info.get("channels", 0)})
            fill_added[chan] += 1
    print(f"folder-tree capture added (pre-dedup): {dict(fill_added)}")

    # 2. EVERY channel the base defines is emitted (missing section = engine CTD).
    #    Filled channels get our deduped content; unfilled ones (blowout/emission,
    #    packed-only) keep their original stems so they resolve from the base VFS.
    merged = {}
    tot_in = tot_kept = tot_dropped = inherited = 0
    for chan in sorted(set(orig_def) | set(pool)):
        files = pool.get(chan, [])
        tot_in += len(files)
        chosen = dedup_pick(files) if files else []
        tot_dropped += len(files) - len(chosen)
        tot_kept += len(chosen)
        od = orig_def.get(chan, {"mod": "?", "settings": [], "stems": []})
        if not chosen and od["stems"]:
            inherited += 1
        merged[chan] = {
            "settings_src": od["mod"], "settings": od["settings"],
            "orig_stems": od["stems"],
            "chosen": [{"abs": c["abs"], "stem": c["stem"], "pool": c["pool"],
                        "bitrate": c["bitrate"], "channels": c["channels"]} for c in chosen],
        }
    (HERE / "merged_channels.json").write_text(json.dumps(merged, indent=1), encoding="utf-8")

    # 3. report
    print(f"mods merged: {[m[0] for m in MODS]}")
    print(f"channels (union): {len(merged)}   filled: {sum(1 for v in merged.values() if v['chosen'])}   inherited (blowout/packed): {inherited}")
    print(f"sounds pooled: {tot_in}  ->  kept {tot_kept}  (dropped {tot_dropped}: exact dups + junk bitrate; {offrate} off-44100 skipped)")
    if missing:
        print(f"unresolved sound refs (packed/missing files): {dict(missing)}")


def parse_presets(gamedata):
    """{filename: {section: {base:[...], lines:[effect/period raw], dynamic:[layers]}}}"""
    d = Path(gamedata) / "configs/environment/ambients/presets"
    out = {}
    if not d.exists():
        return out
    for f in sorted(d.glob("*.ltx")):
        secs, cur = {}, None
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            code = line.split(";", 1)[0]
            m = re.match(r"\s*\[([^\]]+)\]", code)
            if m:
                cur = m.group(1).strip().lower()
                secs[cur] = {"base": [], "lines": [], "dynamic": []}
                continue
            if cur is None:
                continue
            if "sound_channels_dynamic" in code and "=" in code:
                secs[cur]["dynamic"] = [t.strip().lower() for t in code.split("=", 1)[1].split(",") if t.strip()]
            elif re.search(r"sound_channels\s*=", code):
                secs[cur]["base"] = [t.strip() for t in code.split("=", 1)[1].split(",") if t.strip()]
            elif code.strip() and "=" in code:
                secs[cur]["lines"].append(line.rstrip())
        out[f.name] = secs
    return out


MOD = HERE.parent                      # AlifeAmbience repo root
GDATA = MOD / "gamedata"
ENV = GDATA / "configs/environment"
SND = GDATA / "sounds/zs"              # zs\acc\<mood>\N.ogg and zs\tex\<bed>\N.ogg
HDR = "; GENERATED"


def _clean(d):
    if d.exists():
        import shutil as sh
        sh.rmtree(d)


# ----------------------------------------------------------------------------
# The shipped model: two layers over the untouched engine bed.
#   TEXTURE - looped continuous beds, 5 CONTEXTS, one at a time by aa_texture.script.
#   ACCENT  - dynamic one-shots, 5 MOODS, DLTX sound_channels_dynamic per preset.
# Role is MEASURED per file (classify); mood/context is the source channel name.
# ----------------------------------------------------------------------------

# Vocal source channels: a wail/scream/spook is an EVENT, never a bed. Forced
# accent regardless of measured duration.
VOCAL = {"out_screams", "out_spooks", "out_mutants", "out_day_spoops", "out_night_spoops",
         "urban_spoops_night", "northen_spoops", "foliage_spook", "crows_spook"}

# The five moods (accent) and five contexts (texture bed). Both are keyed off the
# source channel name (the pack author's taxonomy) - the second signal after the
# measured role. Kept as functions, not a dict, so a new source channel routes by
# substring without a table edit.
MOODS = ["dread", "underground", "weather", "human", "animal"]
# Texture pools = the looped beds the player hears one at a time. Underground is
# SPLIT by source-channel character into a LAB pool (machine/metal/voices/banging/
# lab hum - the X-Lab levels: X18, brain lab, war lab, X8) and a SEWER pool (drip/
# rats/noise/drone/ambient - tunnels, bunkers, agroprom underground), so a lab does
# not sound like a sewer. The material supports this split (the ugrnd_* channels are
# semantically distinct); it does NOT carry a per-level tag, so finer-than-class
# per-level underground pools would be invented, not traced - we do not do that.
BEDS = ["wind", "dread", "fog", "stormrain", "underground_lab", "underground_sewer"]
TEX_CAP = 40                          # loop variations per pool; draws the held surplus
UG_LAB_CH = {"ugrnd_lab", "ugrnd_ambient_machine", "ugrnd_metal", "ugrnd_voices",
             "ugrnd_banging", "x18"}


def mood_of(ch):
    c = ch.lower()
    if c.startswith("ugrnd_") or c == "x18" or "underground_background" in c:
        return "underground"
    if (c.startswith("crows") and "spook" not in c) or c == "owls" or c == "dogs" or c == "birds_night":
        return "animal"          # crows_spook is a scare, not wildlife -> falls through to dread
    if c in ("out_gunfire", "out_drone", "drones", "day_drones", "urban_drones", "urban_debris", "vest_radio"):
        return "human"
    if "storm" in c or "rain" in c or "wind" in c or c == "chimes" or "tuman" in c or c == "pre_storm":
        return "weather"
    return "dread"


def ctx_of(ch):
    c = ch.lower()
    if c.startswith("ugrnd_") or "underground_background" in c or c == "x18" or c == "inside_noise":
        return "underground"
    if "tuman" in c:
        return "fog"
    if "storm" in c or "rain" in c:
        return "stormrain"
    if "wind" in c:
        return "wind"
    return "dread"


def tex_pool(ch):
    """Texture pool for a source channel: the context bed, with underground split
    into lab vs sewer by channel character (UG_LAB_CH)."""
    c = ctx_of(ch)
    if c != "underground":
        return c
    return "underground_lab" if ch.lower() in UG_LAB_CH else "underground_sewer"


def _iter_chosen(mc):
    """Every chosen sound across all channels, in the canonical order
    (sorted channel name, then the channel's chosen order). This order defines
    classification.json and, downstream, the deployed N numbering."""
    for chan in sorted(mc):
        for c in mc[chan]["chosen"]:
            yield chan, c


# --- classify (measured role) ------------------------------------------------

def _classify_one(chan, c):
    abs_ = c["abs"]
    info = sp.probe(abs_) or {}
    dur = round(float(info.get("duration") or 0.0), 1)
    # one ffmpeg pass: spectral centroid + flatness (stdout via ametadata print),
    # crest factor (stderr astats summary).
    r = sp.run([sp.tool("ffmpeg"), "-v", "info", "-i", abs_, "-af",
                "aspectralstats=measure=centroid+flatness,ametadata=mode=print:file=-,"
                "astats=metadata=1:reset=0", "-f", "null", "-"])
    cens, flats = [], []
    for ln in r.stdout.splitlines():
        if "aspectralstats.1.centroid=" in ln:
            cens.append(float(ln.rsplit("=", 1)[1]))
        elif "aspectralstats.1.flatness=" in ln:
            flats.append(float(ln.rsplit("=", 1)[1]))
    crest = 0.0
    for ln in r.stderr.splitlines():
        if "Crest factor:" in ln:
            try:
                crest = float(ln.rsplit(":", 1)[1])
            except ValueError:
                pass
            break
    cen = int(round(sum(cens) / len(cens))) if cens else 0
    flat = round(sum(flats) / len(flats), 3) if flats else 0.0
    if chan in VOCAL:
        role = "accent"
    elif dur >= 30:
        role = "texture"
    elif dur < 4:
        role = "accent"
    else:
        role = "texture" if (crest < 12 and flat < 0.40) else "accent"
    bright = "dark" if cen < 2000 else ("mid" if cen < 4000 else "bright")
    tone = "tonal" if flat < 0.15 else ("mixed" if flat < 0.40 else "noisy")
    return {"ch": chan, "stem": c["stem"], "dur": dur, "cen": cen, "flat": flat,
            "crest": round(crest, 1), "role": role, "bright": bright, "tone": tone}


def cmd_classify(a):
    mc = json.loads((HERE / "merged_channels.json").read_text())
    items = list(_iter_chosen(mc))
    out = sp.pmap(lambda t: _classify_one(*t), items, sp.DEF_JOBS)
    dst = Path(a.out) if a.out else (HERE / "classification.json")
    dst.write_text(json.dumps(out, indent=1), encoding="utf-8")
    nt = sum(1 for r in out if r["role"] == "texture")
    print(f"classified {len(out)}: {nt} texture, {len(out) - nt} accent -> {dst.name}")


# --- loudness (per-group median leveling, outliers only) ---------------------

def _lufs_one(abs_):
    r = sp.run([sp.tool("ffmpeg"), "-i", abs_, "-af", "ebur128", "-f", "null", "-"])
    val = None
    for ln in r.stderr.splitlines():
        m = re.search(r"\bI:\s*(-?[0-9.]+)\s*LUFS", ln)
        if m:
            val = float(m.group(1))
    return val


def _median(xs):
    s = sorted(xs); n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def cmd_loudness(a):
    mc = json.loads((HERE / "merged_channels.json").read_text())
    items = list(_iter_chosen(mc))
    lufs = sp.pmap(lambda t: (t[0], t[1]["stem"], _lufs_one(t[1]["abs"])), items, sp.DEF_JOBS)
    by_ch = collections.defaultdict(list)
    for ch, stem, L in lufs:
        if L is not None:
            by_ch[ch].append((stem, L))
    outliers = []
    for ch, rows in by_ch.items():
        vals = sorted(L for _, L in rows)
        med = _median(vals)
        q1 = _median(vals[:len(vals) // 2])
        q3 = _median(vals[(len(vals) + 1) // 2:])
        band = max(6.0, 1.5 * (q3 - q1))
        for stem, L in rows:
            if abs(L - med) > band:
                outliers.append({"ch": ch, "stem": stem, "gain_db": round(med - L, 1)})
    dst = Path(a.out) if a.out else (HERE / "loudness_outliers.json")
    dst.write_text(json.dumps(outliers, indent=1), encoding="utf-8")
    print(f"loudness: {len(outliers)} outliers ({100*len(outliers)//max(1,len(lufs))}%) to gain -> {dst.name}")


# --- deploy (deterministic: reproduces the N numbering from the JSONs) --------

def _build_layers(mc, cls):
    """Group the classified sounds into the deployed structure, deterministically.
    accents[mood] = [entry,...] in canonical order; textures[bed] = top-TEX_CAP by
    duration. The source abs is resolved by (ch,stem) via a dict: on a duplicate
    (ch,stem) - same channel+stem captured from two pools - the last occurrence
    wins, matching the shipped bytes (proven: provenance self-verify = 0 mismatch)."""
    src = {(ch, c["stem"]): c for ch, c in _iter_chosen(mc)}
    accents = {m: [] for m in MOODS}
    tex_all = {b: [] for b in BEDS}
    for idx, r in enumerate(cls):
        c = src.get((r["ch"], r["stem"]))
        if not c:
            continue
        e = {"ch": r["ch"], "stem": r["stem"], "abs": c["abs"], "pool": c["pool"],
             "dur": r["dur"], "idx": idx}
        if r["role"] == "texture":
            tex_all[tex_pool(r["ch"])].append(e)
        else:
            accents[mood_of(r["ch"])].append(e)
    textures = {b: sorted(v, key=lambda e: (-e["dur"], e["idx"]))[:TEX_CAP] for b, v in tex_all.items()}
    return accents, textures


def _gain_map():
    return {(o["ch"], o["stem"]): o["gain_db"]
            for o in json.loads((HERE / "loudness_outliers.json").read_text())}


def _emit_audio(entry, dst, gain):
    dst.parent.mkdir(parents=True, exist_ok=True)
    g = gain.get((entry["ch"], entry["stem"]))
    if g is None:
        import shutil as sh
        sh.copy2(entry["abs"], dst)
    else:
        sp.run([sp.tool("ffmpeg"), "-y", "-i", entry["abs"], "-af", f"volume={g}dB",
                "-c:a", "libvorbis", "-ar", "44100", str(dst)])


ACC_SETTINGS = ["min_distance = 45", "max_distance = 100",
                "period0 = 20000", "period1 = 40000", "period2 = 30000", "period3 = 60000"]


def deploy_texture(root, textures, gain):
    """Emit the texture layer only (tex\\<pool>\\N.ogg + looped themes + bed list),
    leaving the accent tree untouched. Separated so the texture pools can be rebuilt
    without re-encoding the accents (an ffmpeg re-encode is not byte-deterministic)."""
    snd = root / "sounds/zs"
    _clean(snd / "tex")
    (root / "configs/scripts").mkdir(parents=True, exist_ok=True)
    (root / "configs/misc/sound").mkdir(parents=True, exist_ok=True)
    themes, beds_cfg = [HDR], [HDR, "[beds]"]
    beds_cfg += [b for b in BEDS if textures[b]]
    for bed in BEDS:
        entries = textures[bed]
        if not entries:
            continue
        for i, e in enumerate(entries, 1):
            _emit_audio(e, snd / "tex" / bed / f"{i}.ogg", gain)
        names = [f"aa_tex_{bed}_{i}" for i in range(1, len(entries) + 1)]
        for i, nm in enumerate(names, 1):
            themes += [f"[{nm}]", "type = looped", f"path = zs\\tex\\{bed}\\{i}", ""]
        beds_cfg += [f"\n[{bed}]", "themes = " + ", ".join(names)]
    (root / "configs/misc/sound/mod_script_sound_aa.ltx").write_text("\n".join(themes), encoding="utf-8")
    (root / "configs/scripts/aa_texture_beds.ltx").write_text("\n".join(beds_cfg) + "\n", encoding="utf-8")


def cmd_deploy(a):
    root = Path(a.root) if a.root else GDATA
    env = root / "configs/environment"
    snd = root / "sounds/zs"
    mc = json.loads((HERE / "merged_channels.json").read_text())
    cls = json.loads((HERE / "classification.json").read_text())
    gain = _gain_map()
    accents, textures = _build_layers(mc, cls)

    _clean(snd); _clean(env / "ambients")
    (root / "configs/scripts").mkdir(parents=True, exist_ok=True)
    (root / "configs/misc/sound").mkdir(parents=True, exist_ok=True)
    (env / "ambients/presets").mkdir(parents=True, exist_ok=True)

    # accents: acc\<mood>\N.ogg + @[aa_acc_<mood>]
    chan_lines = [HDR]
    for mood in MOODS:
        entries = accents[mood]
        for i, e in enumerate(entries, 1):
            _emit_audio(e, snd / "acc" / mood / f"{i}.ogg", gain)
        stems = ", ".join(f"zs\\acc\\{mood}\\{i}" for i in range(1, len(entries) + 1))
        chan_lines.append(f"@[aa_acc_{mood}]")
        chan_lines.extend(ACC_SETTINGS)
        chan_lines.append(f"sounds = {stems}\n")
    (env / "mod_sound_channels_alifeambience.ltx").write_text("\n".join(chan_lines), encoding="utf-8")

    deploy_texture(root, textures, gain)

    write_presets(env)
    print(f"deployed to {root}")
    print(f"  accents: " + ", ".join(f"{m} {len(accents[m])}" for m in MOODS))
    print(f"  textures: " + ", ".join(f"{b} {len(textures[b])}" for b in BEDS))


# --- distribution: which mood plays in which (level, time, weather) section ---
# n071. EVIDENCE-DRIVEN, not a hand table: a mood plays in (level, section) iff a
# source pack placed one of OUR channels of that mood in that exact level+section.
# The section name carries time (day/evening/morning/night) and weather (rain*/
# storm*/tuman*/pre_storm), so this inherits night-heavier-dread, animals-by-time,
# and weather-gating straight from how the pack authors placed the sounds. Two lore
# overrides where the generic packs were lazy: underground labs (structural - the
# source only wires them in indoor* sections) and the haunted whisper level.

# emission order: dread first (dominant), animal last (accent colour)
MOOD_ORDER = ["dread", "underground", "weather", "human", "animal"]
UNDERGROUND_LEVELS = {"environment_underground", "environment_underground_more",
                      "environment_underground_x18"}
WHISPER_LEVEL = "environment_whisper"


def _section_moods(fname, sec, per_pack, ourch):
    """The moods evidenced at (level fname, section sec) across all packs, our
    channels only, then lore-refined for the underground and whisper specials."""
    stem = fname[:-4]
    if stem in UNDERGROUND_LEVELS:                    # labs: underground only, indoor only
        return ["underground"] if sec.lower().startswith("indoor") else []
    chans = set()
    for pm in per_pack.values():
        chans |= set(pm.get(fname, {}).get(sec, {}).get("dynamic", []))
    moods = {mood_of(c) for c in chans if c in ourch}
    if stem == WHISPER_LEVEL:                         # haunted: dread + weather, no wildlife/people
        moods &= {"dread", "weather"}
    return [m for m in MOOD_ORDER if m in moods]


def write_presets(env):
    """Emit mod_<preset>_alifeambience.ltx: for each (level, section) append our
    evidence-placed mood channels via >sound_channels_dynamic. Sections the source
    left empty for that level (e.g. an underground level's surface hours) get no
    append, so nothing plays where nothing was meant to."""
    ourch = {r["ch"] for r in json.loads((HERE / "classification.json").read_text())}
    per_pack = {name: parse_presets(gd) for name, gd in MODS if name != "vanilla"}
    base = parse_presets("D:/Games/GAMMA/GAMMA/mods/304- Dark Signal Weather and Ambiance Audio - Shrike/gamedata")
    for fname, secs in base.items():
        lines = [HDR, ""]
        for sec in secs:
            moods = _section_moods(fname, sec, per_pack, ourch)
            if not moods:
                continue
            lines.append(f"![{sec}]")
            for m in moods:
                lines.append(f">sound_channels_dynamic = aa_acc_{m}")
            lines.append("")
        stem = fname[:-4]
        (env / "ambients/presets" / f"mod_{stem}_alifeambience.ltx").write_text("\n".join(lines), encoding="utf-8")


# --- ledger (the content-hash proof: UNUSED-DARK must be 0) -------------------

DARK_KW = ["spook", "spoop", "mutant", "scream", "distant", "amb_dark", "amb_night",
           "dark_amb", "ugrnd", "underground", "/metal", "banging", "rats", "drip",
           "/drone", "/noise", "whisper", "thunder", "storm", "shooting", "wind_dark",
           "tuman", "creep", "howl", "moan", "growl", "northern", "pre_storm"]
EMISSION_KW = ["blowout", "psi_storm", "emission"]
INCLUDE_ROOTS = ["ambient", "ambience_exp", "nature", "anomaly"]


def cmd_ledger(a):
    mc = json.loads((HERE / "merged_channels.json").read_text())
    cls = json.loads((HERE / "classification.json").read_text())
    role = {(r["ch"], r["stem"]): r["role"] for r in cls}
    chosen = {}                                        # source hash -> (ch, stem)
    for ch, c in _iter_chosen(mc):
        chosen[file_hash(c["abs"])] = (ch, c["stem"])
    deployed = set()                                   # hashes actually shipped
    zs = GDATA / "sounds/zs"
    for f in zs.rglob("*.ogg"):
        deployed.add(file_hash(f))
    rows, counts = [], collections.Counter()
    for name, gd in MODS:
        if name == "vanilla":
            continue
        sroot = Path(gd) / "sounds"
        if not sroot.is_dir():
            continue
        for f in sorted(sroot.rglob("*.ogg")):
            rel = f.as_posix().split("/sounds/")[-1]
            low = rel.lower()
            h = file_hash(f)
            dark = any(k in low for k in DARK_KW)
            emission = any(k in low for k in EMISSION_KW)
            under_root = low.split("/", 1)[0] in INCLUDE_ROOTS
            if h in deployed:
                st = "USED-shipped"
            elif h in chosen and role.get(chosen[h]) != "texture":
                st = "USED-gained"
            elif h in chosen:
                st = "HELD-texture-surplus"
            elif emission:
                st = "EMISSION-excluded"
            elif dark and under_root:
                info = sp.probe(str(f)) or {}
                st = "OFFSPEC-48k-excluded" if info.get("sample_rate") != 44100 else "UNUSED-DARK"
            elif under_root:
                st = "off-scope-or-dup"
            else:
                st = "SKIP-nonambient"
            rows.append(f"{name}\t{rel}\t{st}")
            counts[st] += 1
    (HERE / "ledger.tsv").write_text("pack\tfile\tstatus\n" + "\n".join(rows) + "\n", encoding="utf-8")
    for st, n in counts.most_common():
        print(f"{n:6d}  {st}")
    print(f"UNUSED-DARK = {counts['UNUSED-DARK']}   (MUST be 0)")


# --- provenance (n070: every shipped N.ogg -> what it is and where from) ------

def _parse_settings(lines):
    out = {}
    for ln in lines:
        m = re.match(r"\s*(min_distance|max_distance|period0|period1|period2|period3|height|indoor)\s*=\s*(\S+)", ln)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _channel_sections():
    """source channel -> sorted list of 'pack:presetfile:section' it played in."""
    out = collections.defaultdict(set)
    for name, gd in MODS:
        for fname, secs in parse_presets(gd).items():
            for sec, d in secs.items():
                for ch in d["dynamic"]:
                    out[ch].add(f"{name}:{fname[:-4]}:{sec}")
    return {k: sorted(v) for k, v in out.items()}


def cmd_provenance(a):
    mc = json.loads((HERE / "merged_channels.json").read_text())
    cls = json.loads((HERE / "classification.json").read_text())
    gain = _gain_map()
    accents, textures = _build_layers(mc, cls)
    settings = {ch: _parse_settings(mc[ch]["settings"]) for ch in mc}
    ch_sec = _channel_sections()
    zs = GDATA / "sounds/zs"

    cols = ["deployed", "layer", "group", "orig_mod", "orig_dir", "orig_file", "orig_channel",
            "min_distance", "max_distance", "period0", "period1", "period2", "period3",
            "indoor", "height", "gain_db", "orig_sections"]
    rows, verify_ok, verify_bad = [], 0, 0
    def add(entries, layer, group, subdir):
        nonlocal verify_ok, verify_bad
        for i, e in enumerate(entries, 1):
            dep = f"zs\\{subdir}\\{group}\\{i}"
            s = settings.get(e["ch"], {})
            g = gain.get((e["ch"], e["stem"]))
            stem = e["stem"]
            rows.append([dep, layer, group, e["pool"], str(Path(stem).parent).replace("\\", "/"),
                         Path(stem).name, e["ch"],
                         s.get("min_distance", ""), s.get("max_distance", ""),
                         s.get("period0", ""), s.get("period1", ""), s.get("period2", ""), s.get("period3", ""),
                         s.get("indoor", ""), s.get("height", ""),
                         "" if g is None else str(g), "; ".join(ch_sec.get(e["ch"], []))])
            # self-verify: a verbatim (ungained) shipped file must hash-equal its source
            if g is None:
                dfile = zs / subdir / group / f"{i}.ogg"
                if dfile.exists() and file_hash(dfile) == file_hash(e["abs"]):
                    verify_ok += 1
                else:
                    verify_bad += 1
    for mood in MOODS:
        add(accents[mood], "accent", mood, "acc")
    for bed in BEDS:
        add(textures[bed], "texture", bed, "tex")
    lines = ["\t".join(cols)] + ["\t".join(r) for r in rows]
    (HERE / "provenance.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"provenance: {len(rows)} shipped sounds -> provenance.tsv")
    print(f"verbatim hash self-verify vs deployed tree: {verify_ok} match, {verify_bad} MISMATCH")
    if verify_bad:
        print("  MISMATCH != 0 -> the deploy ordering does NOT reproduce the tree; provenance is NOT exact.")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan").set_defaults(func=cmd_plan)
    p = sub.add_parser("classify"); p.add_argument("--out"); p.set_defaults(func=cmd_classify)
    p = sub.add_parser("loudness"); p.add_argument("--out"); p.set_defaults(func=cmd_loudness)
    p = sub.add_parser("deploy"); p.add_argument("--root"); p.set_defaults(func=cmd_deploy)
    sub.add_parser("ledger").set_defaults(func=cmd_ledger)
    sub.add_parser("provenance").set_defaults(func=cmd_provenance)
    a = ap.parse_args(); a.func(a)
