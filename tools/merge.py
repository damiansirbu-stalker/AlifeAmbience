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
    # net-new distant-creature calls (99 files, 0 content-hash overlap with Amplified's
    # mutant pool). No sound_channels.ltx of its own - captured via DARK_FILL /mutants/.
    ("RealDistantMutants", "C:/Users/damian/Downloads/anomaly_audio_mods/Real Distant Mutants Sounds/gamedata"),
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


# --- base-dedup: never ship a sound the install already PLAYS ----------------
# The install plays a fixed set, winner-resolved: vanilla's own ambient channels
# (unpacked sounds_ambient.db0) + the GAMMA winner (DSW) active channels. Our content
# must exclude those by md5 AND by acoustic fingerprint - the packs re-encode the same
# sound to new bytes, so md5 alone misses the re-encoded copies (measured: ~250 of the
# "net-new" set were acoustic duplicates of a base-played sound). fpcalc + fp_similarity
# is the same same-sound test soundpool uses; BASE_SIM matches its dup_similarity_threshold.
VAN_CFG = "D:/Games/GAMMA/Anomaly/tools/_unpacked"
VAN_SND = Path("D:/Games/GAMMA/Anomaly/tmp_van_ambient/sounds")     # unpacked sounds_ambient.db0
CONVERTER = "D:/Games/GAMMA/Anomaly/tools/converter.exe"
VAN_DB = "D:/Games/GAMMA/Anomaly/db/sounds/sounds_ambient.db0"
GAMMA_WINNER = "D:/Games/GAMMA/GAMMA/mods/304- Dark Signal Weather and Ambiance Audio - Shrike/gamedata"
GAMMA_DEFINERS = [GAMMA_WINNER,
    "D:/Games/GAMMA/GAMMA/mods/3- Soundscape Overhaul - Solarint/gamedata",
    "D:/Games/GAMMA/GAMMA/mods/457- RETUNE Ambiant Sounds - Aphrodite_child/gamedata"]
FP_LEN = 30
BASE_SIM = 0.88     # soundpool dup_similarity_threshold; >= this to a base sound = drop


def _active_channels(gd):
    """channels PLAYED in a preset (static sound_channels + dynamic) on this install."""
    a = set()
    for _f, secs in parse_presets(gd).items():
        for _s, d in secs.items():
            a |= {c.lower() for c in d.get("base", [])} | {c.lower() for c in d.get("dynamic", [])}
    return a


def _base_played_files():
    """{md5: path} for every sound the install PLAYS. GAMMA winner = DSW's active
    channels (so its stripped channels are NOT counted - those are ours to restore);
    vanilla = its active channels resolved from the unpacked ambient tree."""
    files = {}
    dsw_act = _active_channels(GAMMA_WINNER)
    for gd in GAMMA_DEFINERS:
        root = Path(gd) / "sounds"
        for ch, d in parse_channels(gd).items():
            if ch.lower() in dsw_act:
                for st in d["stems"]:
                    f = resolve(st, root)
                    if f:
                        files.setdefault(file_hash(f), f)
    van_act = _active_channels(VAN_CFG)
    for ch, d in parse_channels(VAN_CFG).items():
        if ch.lower() in van_act:
            for st in d["stems"]:
                f = resolve(st, VAN_SND)
                if f:
                    files.setdefault(file_hash(f), f)
    return files


def _ensure_vanilla_unpacked():
    if VAN_SND.is_dir() and next(VAN_SND.rglob("*.ogg"), None):
        return
    import subprocess
    VAN_SND.parent.mkdir(parents=True, exist_ok=True)
    print(f"unpacking vanilla ambient sounds -> {VAN_SND.parent}")
    subprocess.run([CONVERTER, "-unpack", "-xdb", "-dir", str(VAN_SND.parent), VAN_DB], check=True)


def cmd_basedex(_a):
    """Build the base-played index (md5 + fingerprint + duration) -> base_index.json.
    Run once; plan reads it to drop duplicates. Rebuild when the install's ambient
    mods change (winner, DSW/Soundscape/RETUNE, or the vanilla pack)."""
    _ensure_vanilla_unpacked()
    files = _base_played_files()

    def one(hp):
        h, f = hp
        info = sp.probe(str(f)) or {}
        return {"md5": h, "fp": sp.fingerprint(str(f), FP_LEN),
                "dur": round(float(info.get("duration") or 0))}
    rows = sp.pmap(one, list(files.items()), sp.DEF_JOBS)
    (HERE / "base_index.json").write_text(json.dumps(rows), encoding="utf-8")
    print(f"base index: {len(rows)} played sounds (vanilla + GAMMA winner) -> base_index.json")


def _load_base_index():
    p = HERE / "base_index.json"
    if not p.exists():
        cmd_basedex(None)
    rows = json.loads(p.read_text())
    md5 = {r["md5"] for r in rows}
    by_dur = collections.defaultdict(list)
    for r in rows:
        if r["fp"]:
            by_dur[r["dur"]].append(r["fp"])
    return md5, by_dur


def _base_dedup(merged):
    """Drop every chosen sound the install already plays: md5 hit, or acoustic
    fingerprint >= BASE_SIM to a base sound of the same duration (a re-encode)."""
    md5set, by_dur = _load_base_index()
    uniq = {c["abs"]: None for chan in merged for c in merged[chan]["chosen"]}
    for a in uniq:
        uniq[a] = file_hash(a)
    need = [a for a, h in uniq.items() if h not in md5set]
    fpres = dict(zip(need, sp.pmap(
        lambda a: (sp.fingerprint(a, FP_LEN), round(float((sp.probe(a) or {}).get("duration") or 0))),
        need, sp.DEF_JOBS)))

    def base_hit(a):
        if uniq[a] in md5set:
            return "md5"
        fp, dur = fpres.get(a, (None, 0))
        if not fp:
            return None
        for d in (dur - 1, dur, dur + 1):
            for bfp in by_dur.get(d, ()):
                if sp.fp_similarity(fp, bfp) >= BASE_SIM:
                    return "fp"
        return None
    hit = {a: base_hit(a) for a in uniq}
    n_md5 = sum(1 for v in hit.values() if v == "md5")
    n_fp = sum(1 for v in hit.values() if v == "fp")
    for chan in merged:
        merged[chan]["chosen"] = [c for c in merged[chan]["chosen"] if hit[c["abs"]] is None]
    print(f"base-dedup: dropped {n_md5} md5 + {n_fp} acoustic re-encodes the install already plays "
          f"(of {len(uniq)} chosen)")


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
    # base-dedup: never ship a sound vanilla or the GAMMA winner already plays (md5 +
    # acoustic). Runs on the chosen set before it is frozen into merged_channels.json.
    _base_dedup(merged)
    (HERE / "merged_channels.json").write_text(json.dumps(merged, indent=1), encoding="utf-8")

    # 3. report
    print(f"mods merged: {[m[0] for m in MODS]}")
    net_new = sum(len(v["chosen"]) for v in merged.values())
    print(f"channels (union): {len(merged)}   filled: {sum(1 for v in merged.values() if v['chosen'])}   inherited (blowout/packed): {inherited}")
    print(f"sounds pooled: {tot_in}  ->  deduped {tot_kept}  ->  net-new after base-dedup: {net_new}  (dropped {tot_dropped}: exact dups + junk bitrate; {offrate} off-44100 skipped)")
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
#   TEXTURE - looped continuous beds, one at a time by context (aa_texture.script).
#   ACCENT  - dynamic one-shots on the engine's own channels, enrich/restore/define
#             (see _channel_routing); grouped into 11 LAYERS for volume + density.
# Role is MEASURED per file (classify); the layer comes from layer_of.
# ----------------------------------------------------------------------------

# Vocal source channels: a wail/scream/spook is an EVENT, never a bed. Forced
# accent regardless of measured duration.
VOCAL = {"out_screams", "out_spooks", "out_mutants", "out_day_spoops", "out_night_spoops",
         "urban_spoops_night", "northen_spoops", "foliage_spook", "crows_spook"}

# The texture contexts (bed pool per source channel), separate from the accent layers.
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

def _build_layers(mc, cls, ch_to_group, group_key):
    """Group the classified sounds into the deployed structure, deterministically.
    accents[group] = [entry,...] in canonical order (group = <mood>_<n>, one per exact
    settings-tuple); textures[bed] = top-TEX_CAP by duration. The source abs is resolved
    by (ch,stem) via a dict: on a duplicate (ch,stem) - same channel+stem captured from
    two pools - the last occurrence wins, matching the shipped bytes."""
    src = {(ch, c["stem"]): c for ch, c in _iter_chosen(mc)}
    accents = {g: [] for g in group_key}
    tex_all = {b: [] for b in BEDS}
    for idx, r in enumerate(cls):
        c = src.get((r["ch"], r["stem"]))
        if not c:
            continue
        e = {"ch": r["ch"], "stem": r["stem"], "abs": c["abs"], "pool": c["pool"],
             "dur": r["dur"], "idx": idx}
        if r["role"] == "texture":
            tex_all[tex_pool(r["ch"])].append(e)
        elif r["ch"] in ch_to_group:          # skip accent sounds of bed channels (not routed)
            accents[ch_to_group[r["ch"]]].append(e)
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


# Each accent channel keeps its VERBATIM source settings - no median. Channels are grouped
# by (mood, exact-settings-tuple): one deployed channel aa_acc_<mood>_<n> per distinct tuple,
# so a source channel's period/distance/indoor/height survive exactly (provenance-faithful).
# The mood is only a tag for the MCM knobs; aa_sound reads it off the <mood> in the name.
def _chan_settings(lines):
    d = {}
    for ln in lines or []:
        m = re.match(r"\s*(\w+)\s*=\s*([\d.]+|true|false)", ln)
        if m:
            d[m.group(1)] = m.group(2)

    def num(x, dflt):
        try:
            return int(float(x))
        except (TypeError, ValueError):
            return dflt
    return {"min": num(d.get("min_distance"), 45), "max": num(d.get("max_distance"), 80),
            "p": tuple(num(d.get(f"period{i}"), 0) for i in range(4)),
            "indoor": d.get("indoor") == "true", "height": num(d.get("height"), 0)}


_SETTINGS_CACHE = None


def _settings_key(ch):
    """The exact (min, max, periods, indoor, height) tuple for a source channel."""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is None:
        mc = json.loads((HERE / "merged_channels.json").read_text())
        _SETTINGS_CACHE = {c: _chan_settings(mc[c].get("settings")) for c in mc}
    s = _SETTINGS_CACHE.get(ch) or _chan_settings(None)
    return (s["min"], s["max"], s["p"], s["indoor"], s["height"])


# --- layers + channel routing (the shipped model) ---------------------------
# A LAYER is a pure-purpose group of channels. Each deployed channel belongs to
# exactly one; the layer drives its MCM volume slider and the per-section density
# budget. Named for what the sound IS. layer_of is the single source of truth; the
# deploy materialises it to aa_channel_layers.ltx so aa_sound reads it, never a name.
LAYERS = ["spooks", "screams", "mutants", "ambience", "machines", "forest",
          "storm", "wind", "rain", "wildlife", "underground"]
# emission priority when a section is over the density budget: dread-core first,
# wildlife/rain last (accent colour). Layers not listed rank after these.
LAYER_ORDER = ["spooks", "screams", "mutants", "ambience", "underground", "forest",
               "storm", "wind", "machines", "rain", "wildlife"]


def layer_of(ch):
    c = ch.lower()
    if c.startswith("aa_"):        # deployed define channels are aa_<source>; layer by the source
        c = c[3:]
    if c.startswith("ugrnd_") or c == "x18" or c == "inside_noise" or "underground_background" in c:
        return "underground"
    if "rain" in c:
        return "rain"
    if "storm" in c or c == "pre_storm" or c == "chimes":
        return "storm"
    if "wind" in c:
        return "wind"
    if c in ("branch", "branch_med", "branch_big", "foliage_spook", "tree_sway_fog", "crows_spook"):
        return "forest"
    if c == "out_screams":
        return "screams"
    if c == "out_mutants":
        return "mutants"
    if c in ("out_dark_amb", "out_night_amb", "psi_sparks", "psistorm_background", "dark_signal"):
        return "ambience"
    if c in ("out_gunfire", "out_drone", "drones", "day_drones", "urban_drones", "vest_radio", "urban_debris"):
        return "machines"
    if c in ("crows", "crows_clear", "crows_forest", "crows_retune", "owls", "dogs", "birds_night"):
        return "wildlife"
    return "spooks"   # out_spooks, *_spoops: dark presence (default)


# strip-4: channels vanilla plays but the GAMMA winner (DSW) strips. We restore them
# on both installs (define fully + re-add to presets), filled with our net-new content.
STRIP4 = {"out_screams", "out_mutants", "out_gunfire", "wind_dark"}


def _channel_routing(mc, cls):
    """source channel -> (deployed, mode, layer) for every channel with ACCENT content.
      enrich  - a channel BOTH installs play: append our net-new sounds to it (deployed =
                the base name), NO preset change (it already plays where the base plays it).
      restore - a strip-4 channel: define fully + re-add to presets (deployed = base name).
      define  - a purpose no live base channel provides: our own aa_<ch> (deployed = aa_ch).
    Beds (texture role) are not routed here - the deploy sends them to the bed pools."""
    have_accent = {r["ch"] for r in cls if r["role"] != "texture"}
    both = _active_channels(VAN_CFG) & _active_channels(GAMMA_WINNER)
    gam_defined = set(parse_channels(GAMMA_WINNER).keys())   # channels DSW defines (played or not)
    routing = {}
    for ch in sorted(mc):
        if ch not in have_accent or not mc[ch]["chosen"]:
            continue
        if all(v == 0 for v in _chan_settings(mc[ch].get("settings"))["p"]):
            continue    # a bed (all periods 0) is a continuous loop -> the texture layer, never an accent
        lay = layer_of(ch)
        if ch in STRIP4 and ch in gam_defined:
            # stripped from the winner's presets but still DEFINED -> re-activate + enrich it
            routing[ch] = (ch, "restore", lay)
        elif ch in both:
            # a channel both installs actively play -> append our net-new sounds in place
            routing[ch] = (ch, "enrich", lay)
        else:
            # no channel both installs run (wind_dark absent on GAMMA, or a pack refinement
            # like out_day_spoops) -> our own self-contained channel, defined + placed
            routing[ch] = (f"aa_{ch}", "define", lay)
    return routing


def accent_group_map(cls):
    """(ch -> deployed channel, deployed channel -> settings key), derived from the
    routing. Deployed name = the base channel (enrich/restore) or aa_<ch> (define).
    Kept as the shared entry point for _build_layers, deploy and provenance."""
    mc = json.loads((HERE / "merged_channels.json").read_text())
    routing = _channel_routing(mc, cls)
    ch_to_group, group_key = {}, {}
    for ch, (dep, _mode, _lay) in routing.items():
        ch_to_group[ch] = dep
        group_key[dep] = _settings_key(ch)
    return ch_to_group, group_key


ACC_PERIOD_FLOOR = 20000   # a period of 0 makes a one-shot fire every tick (spam); floor it.
                           # The source's 0 is recorded verbatim in provenance; only the deploy floors it.


def _acc_settings(key):
    mn, mx, p, indoor, height = key
    lines = [f"min_distance = {mn}", f"max_distance = {mx}"]
    for i, pv in enumerate(p):
        lines.append(f"period{i} = {pv if pv > 0 else ACC_PERIOD_FLOOR}")
    lines.append(f"height = {height}")
    if indoor:
        lines.append("indoor = true")
    return lines


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
    routing = _channel_routing(mc, cls)
    ch_to_group = {ch: dep for ch, (dep, _m, _l) in routing.items()}
    group_key = {dep: _settings_key(ch) for ch, (dep, _m, _l) in routing.items()}
    dep_mode = {dep: mode for _ch, (dep, mode, _l) in routing.items()}
    dep_layer = {dep: lay for _ch, (dep, _m, lay) in routing.items()}
    accents, textures = _build_layers(mc, cls, ch_to_group, group_key)

    _clean(snd); _clean(env / "ambients")
    (root / "configs/scripts").mkdir(parents=True, exist_ok=True)
    (root / "configs/misc/sound").mkdir(parents=True, exist_ok=True)
    (env / "ambients/presets").mkdir(parents=True, exist_ok=True)

    # Deployed accent channels. @[C] is the DLTX safe create-or-override: it MERGES our
    # sounds into an existing channel (enrich/restore) or CREATES it (define). Sounds are
    # always appended with >sounds so a base channel's own sounds are never replaced; a
    # define channel additionally carries its settings and a seeding `sounds =` line.
    # ONE sound per line - a single long `sounds = a,b,c,...` overflows the engine's fixed
    # LTX read buffer (IReader::r_string, FS.cpp) and CTDs at load.
    chan_lines, layer_lines = [HDR], [HDR, "[aa_channel_layers]"]
    for dep in sorted(accents):
        entries = accents[dep]
        if not entries:
            continue
        for i, e in enumerate(entries, 1):
            _emit_audio(e, snd / dep / f"{i}.ogg", gain)
        chan_lines.append(f"@[{dep}]")
        if dep_mode[dep] == "define":
            chan_lines.extend(_acc_settings(group_key[dep]))
            chan_lines.append(f"sounds = zs\\{dep}\\1")
            start = 2
        else:                       # enrich / restore: append only, inherit the base settings
            start = 1
        for i in range(start, len(entries) + 1):
            chan_lines.append(f">sounds = zs\\{dep}\\{i}")
        chan_lines.append("")
        layer_lines.append(f"{dep} = {dep_layer[dep]}")
    # Also map the base's OWN dark channels (the install plays them, we ship no content for
    # them), so the per-layer volume governs the WHOLE dark soundscape, not just our additions.
    # aa_sound applies the layer to every dynamic channel it plays, ours or the base's; a base
    # channel absent from the map would only obey the global knob. Beds are skipped (never a
    # dynamic accent). Non-accent nature stays out (DARK_KEEP is dark-scoped).
    mapped = {ln.split(" = ", 1)[0] for ln in layer_lines[2:]}
    base_active = (_active_channels(VAN_CFG) | _active_channels(GAMMA_WINNER)) & DARK_KEEP
    for ch in sorted(base_active):
        if ch in mapped or "background" in ch or ch.endswith("_bkg_1"):
            continue
        layer_lines.append(f"{ch} = {layer_of(ch)}")
    (env / "mod_sound_channels_alifeambience.ltx").write_text("\n".join(chan_lines), encoding="utf-8")
    (env / "aa_channel_layers.ltx").write_text("\n".join(layer_lines) + "\n", encoding="utf-8")

    deploy_texture(root, textures, gain)
    write_presets(env, routing)
    counts = collections.Counter(dep_mode[d] for d in accents if accents[d])
    print(f"deployed to {root}")
    print(f"  accent channels: enrich {counts['enrich']}, restore {counts['restore']}, "
          f"define {counts['define']}; {sum(len(v) for v in accents.values())} sounds")
    print(f"  textures: " + ", ".join(f"{b} {len(textures[b])}" for b in BEDS))


# --- distribution: which channel plays in which (level, time, weather) section -----
# EVIDENCE + LORE + BUDGET. A restore/define channel plays where a source pack placed
# its source channel (the section name carries time + weather, so night-heavier dread,
# animals-by-time and weather-gating fall out of the placement), refined by two lore
# rules (underground labs, the haunted whisper level), then capped so base + our added
# channels never exceed vanilla's per-section maximum. ENRICH channels are NOT placed
# here - they already play wherever the base plays them; we only added sounds to them.
SECTION_MAX = 13    # vanilla's observed per-section channel ceiling; keep total <= this
UNDERGROUND_LEVELS = {"environment_underground", "environment_underground_more",
                      "environment_underground_x18"}
WHISPER_LEVEL = "environment_whisper"


def _place_map(routing):
    """source channel -> deployed name, for the channels we PLACE (restore + define).
    Enrich channels are excluded: they already play wherever the base plays them."""
    return {ch: dep for ch, (dep, mode, _l) in routing.items() if mode in ("restore", "define")}


def _section_channels(fname, sec, place, routing):
    """Deployed restore/define channels to place at (level fname, section sec):
    evidenced (a source pack placed the source channel there), lore-refined for the
    underground labs and the haunted whisper level. Returns deployed channel names."""
    stem = fname[:-4]
    lay = {dep: layer_of(dep) for dep in place.values()}
    if stem in UNDERGROUND_LEVELS:                    # labs: underground channels, indoor only
        if not sec.lower().startswith("indoor"):
            return []
        return sorted({dep for dep in place.values() if lay[dep] == "underground"})
    srcs = set()
    for pm in _PER_PACK.values():
        srcs |= set(pm.get(fname, {}).get(sec, {}).get("dynamic", []))
    deps = {place[c] for c in srcs if c in place}
    if stem == WHISPER_LEVEL:                         # haunted: no wildlife, no people
        deps = {d for d in deps if lay[d] not in ("wildlife", "machines")}
    return sorted(deps)


# Vanilla presets no pack rebinds away. Portability: on bare vanilla (no soundscape
# packs), darkscape/red-forest use environment_forest_more and the coast uses
# environment_swamp_coast; alias them to the nearest generated distribution so every
# vanilla preset is overlaid too. On GAMMA these are moot (the packs rebind to the 21).
PRESET_ALIASES = {"environment_forest_more": "environment_forest",
                  "environment_swamp_coast": "environment_swamp"}
_PER_PACK = {}


def write_presets(env, routing):
    """Emit mod_<preset>_alifeambience.ltx. Per (level, section), place our restore/define
    channels via >sound_channels_dynamic (evidence + lore), then cap so the winner's base
    channel count + our additions stays <= SECTION_MAX (vanilla's ceiling); over budget,
    drop by LAYER_ORDER (dread-core kept, wildlife/rain first out). Enrich channels are not
    placed - they already play wherever the base plays them."""
    global _PER_PACK
    _PER_PACK = {name: parse_presets(gd) for name, gd in MODS if name != "vanilla"}
    base = parse_presets(GAMMA_WINNER)
    place = _place_map(routing)
    lay = {dep: layer_of(dep) for dep in place.values()}

    def budget_cap(deps, base_count):
        room = SECTION_MAX - base_count
        if room <= 0:
            return []
        if len(deps) <= room:
            return deps

        def rank(d):
            l = lay.get(d, "spooks")
            return (LAYER_ORDER.index(l) if l in LAYER_ORDER else len(LAYER_ORDER), d)
        return sorted(sorted(deps, key=rank)[:room])

    def emit(out_stem, src_fname, secs):
        lines = [HDR, ""]
        for sec in secs:
            deps = budget_cap(_section_channels(src_fname, sec, place, routing),
                              len(secs[sec].get("dynamic", [])))
            if not deps:
                continue
            lines.append(f"![{sec}]")
            for d in deps:
                lines.append(f">sound_channels_dynamic = {d}")
            lines.append("")
        (env / "ambients/presets" / f"mod_{out_stem}_alifeambience.ltx").write_text("\n".join(lines), encoding="utf-8")

    for fname, secs in base.items():
        emit(fname[:-4], fname, secs)
    for alias_stem, src_stem in PRESET_ALIASES.items():   # vanilla-only presets
        src_fname = src_stem + ".ltx"
        if src_fname in base:
            emit(alias_stem, src_fname, base[src_fname])


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
    base_md5, base_by_dur = _load_base_index()         # sounds the install already PLAYS
    rows, counts, pending = [], collections.Counter(), []
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
            elif h in base_md5:                         # the install plays it (exact) -> not ours
                st = "BASE-DUP-excluded"
            elif dark and under_root:
                info = sp.probe(str(f)) or {}
                if info.get("sample_rate") != 44100:
                    st = "OFFSPEC-48k-excluded"
                else:
                    pending.append((name, rel, f))      # decide UNUSED-DARK vs BASE-DUP acoustically
                    continue
            elif under_root:
                st = "off-scope-or-dup"
            else:
                st = "SKIP-nonambient"
            rows.append(f"{name}\t{rel}\t{st}")
            counts[st] += 1
    # a dark file the install doesn't byte-match may still be a re-encoded copy it plays;
    # fingerprint the residue against the base index so UNUSED-DARK is only true misses.
    def _fp(t):
        _n, _r, f = t
        return (sp.fingerprint(str(f), FP_LEN), round(float((sp.probe(str(f)) or {}).get("duration") or 0)))
    for (name, rel, _f), (fp, dur) in zip(pending, sp.pmap(_fp, pending, sp.DEF_JOBS)):
        st = "UNUSED-DARK"
        if fp:
            for d in (dur - 1, dur, dur + 1):
                if any(sp.fp_similarity(fp, b) >= BASE_SIM for b in base_by_dur.get(d, ())):
                    st = "BASE-DUP-excluded"
                    break
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
    ch_to_group, group_key = accent_group_map(cls)
    accents, textures = _build_layers(mc, cls, ch_to_group, group_key)
    settings = {ch: _parse_settings(mc[ch]["settings"]) for ch in mc}
    ch_sec = _channel_sections()
    zs = GDATA / "sounds/zs"

    cols = ["deployed", "layer", "group", "orig_mod", "orig_dir", "orig_file", "orig_channel",
            "min_distance", "max_distance", "period0", "period1", "period2", "period3",
            "indoor", "height", "gain_db", "orig_sections"]
    rows, verify_ok, verify_bad = [], 0, 0
    def add(entries, layer, group, reldir):
        nonlocal verify_ok, verify_bad
        for i, e in enumerate(entries, 1):
            dep = f"zs\\{reldir}\\{i}"
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
                dfile = zs / Path(reldir.replace("\\", "/")) / f"{i}.ogg"
                if dfile.exists() and file_hash(dfile) == file_hash(e["abs"]):
                    verify_ok += 1
                else:
                    verify_bad += 1
    for g in sorted(group_key):                       # accents deploy to zs\<channel>\N
        add(accents[g], layer_of(g), g, g)
    for bed in BEDS:                                  # texture beds to zs\tex\<bed>\N
        add(textures[bed], "texture", bed, f"tex\\{bed}")
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
    sub.add_parser("basedex").set_defaults(func=cmd_basedex)
    p = sub.add_parser("classify"); p.add_argument("--out"); p.set_defaults(func=cmd_classify)
    p = sub.add_parser("loudness"); p.add_argument("--out"); p.set_defaults(func=cmd_loudness)
    p = sub.add_parser("deploy"); p.add_argument("--root"); p.set_defaults(func=cmd_deploy)
    sub.add_parser("ledger").set_defaults(func=cmd_ledger)
    sub.add_parser("provenance").set_defaults(func=cmd_provenance)
    a = ap.parse_args(); a.func(a)
