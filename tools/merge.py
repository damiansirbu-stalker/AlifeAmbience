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

# The 8 channels we actually ship, on a role x mood grid. Role = how it composes
# in the mix (texture = intermittent fill; accent = rare foreground one-shot).
# Mood = what it is (drives sound selection + the MCM knob). Every dark channel
# folds into one cell; the pack's source-name taxonomy is discarded.
GRID_GROUPS = {
    "aa_dread_texture": [
        "out_dark_amb", "out_night_amb", "dark_signal", "inside_noise", "background_creepy_low_wind",
        "background_forest_whisper_day", "background_forest_whisper_evening",
        "background_forest_whisper_morning", "background_forest_whisper_night", "background_forest_whisper_tuman"],
    "aa_dread_accent": [
        "out_spooks", "out_day_spoops", "out_night_spoops", "northen_spoops", "urban_spoops_night",
        "out_screams", "out_mutants", "foliage_spook", "crows_spook", "psi_sparks", "psistorm_background"],
    "aa_ug_texture": [
        "ugrnd_ambient", "ugrnd_ambient_machine", "ugrnd_ambient_new", "ugrnd_bkg_1", "ugrnd_noise",
        "ugrnd_drip", "ugrnd_drone", "ugrnd_lab",
        "underground_background_1", "underground_background_2", "underground_background_3", "underground_background_4",
        "underground_background_5", "underground_background_6", "underground_background_7", "underground_background_8"],
    "aa_ug_accent": ["ugrnd_banging", "ugrnd_metal", "ugrnd_rats", "ugrnd_voices", "x18"],
    "aa_human_accent": ["out_gunfire", "out_drone", "drones", "day_drones", "urban_drones", "vest_radio", "urban_debris"],
    "aa_weather_texture": [
        "wind_creep", "wind_creep_alt", "wind_creep_urban", "branch", "branch_big", "branch_med",
        "wind_dark", "wind_gale", "wind_heavy", "wind_strong", "chimes", "rain_gust", "rain_urban_gust",
        "background_rain_forest", "tree_sway_fog",
        "background_tuman_field_open", "background_tuman_field_openalt", "background_tuman_open",
        "background_tuman_open_alt", "background_tuman_open_alt2", "background_tuman_open_urban"],
    "aa_weather_accent": [
        "storm", "storm_foliage", "storm_urban", "pre_storm", "background_storm_forest", "background_wind_storm"],
    "aa_animal_accent": ["owls", "dogs", "crows", "crows_clear", "crows_forest", "crows_retune", "birds_night"],
}
GRID = {member: grid for grid, members in GRID_GROUPS.items() for member in members}

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
]

# priority order: settings for a shared channel come from the first that defines it
MODS = [
    ("DarkSigWeather", "D:/Games/GAMMA/GAMMA/mods/304- Dark Signal Weather and Ambiance Audio - Shrike/gamedata"),
    ("Soundscape",     "D:/Games/GAMMA/GAMMA/mods/3- Soundscape Overhaul - Solarint/gamedata"),
    ("RETUNE",         "D:/Games/GAMMA/GAMMA/mods/457- RETUNE Ambiant Sounds - Aphrodite_child/gamedata"),
    ("Amplified",      "C:/Users/damian/Downloads/extra_mods_analysys/Dark Signal Amplified Soundscape/gamedata"),
    ("vanilla",        "D:/Games/GAMMA/Anomaly/tools/_unpacked"),   # last: only for channels no pack defines (portability coverage)
]

# Middle-ground tuning applied to channel settings at deploy. The Dark Signal packs
# fire 2-5x more often and carry farther than vanilla; these pull toward the middle.
# Tunable: raise PERIOD_MULT for rarer, lower MAX_DIST_CAP for shorter carry.
PERIOD_MULT = 2.0
MAX_DIST_CAP = 150.0
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


def cmd_presets(_):
    merged_ch = set(json.loads((HERE / "merged_channels.json").read_text()))  # lowercase names
    per_mod = {name: parse_presets(gd) for name, gd in MODS}
    order = [name for name, _ in MODS]
    gamma = per_mod["DarkSigWeather"]

    all_files = set().union(*[set(pm) for pm in per_mod.values()])
    merged, added_total, dropped_refs = {}, 0, set()
    for fname in sorted(all_files):
        secs = set().union(*[set(per_mod[n].get(fname, {})) for n in order])
        merged[fname] = {}
        for sec in secs:
            dyn = set()
            for n in order:
                dyn |= set(per_mod[n].get(fname, {}).get(sec, {}).get("dynamic", []))
            keep = {l for l in dyn if l in merged_ch}
            dropped_refs |= (dyn - keep)
            # base bed + effect/period lines: prefer GAMMA, else first mod that has this section
            src = None
            for n in order:
                s = per_mod[n].get(fname, {}).get(sec)
                if s:
                    src = s; break
            gset = set(gamma.get(fname, {}).get(sec, {}).get("dynamic", []))
            added_total += len(keep - gset)
            merged[fname][sec] = {"base": src["base"] if src else [],
                                  "lines": src["lines"] if src else [],
                                  "dynamic": sorted(keep)}
    # inject horror layers that no source preset switches on. out_screams is
    # defined everywhere but invoked nowhere; out_mutants fires in few places.
    # Add them wherever the outdoor dread layer (out_spooks) already plays.
    INJECT = {"out_spooks": ["out_mutants", "out_screams"]}
    injected = 0
    for secs in merged.values():
        for d in secs.values():
            dyn = set(d["dynamic"])
            for trig, adds in INJECT.items():
                if trig in dyn:
                    for a in adds:
                        if a in merged_ch and a not in dyn:
                            d["dynamic"].append(a); dyn.add(a); injected += 1

    (HERE / "merged_presets.json").write_text(json.dumps(merged, indent=1), encoding="utf-8")
    print(f"horror layers injected where out_spooks plays: {injected}")

    nsec = sum(len(v) for v in merged.values())
    print(f"preset files (union): {len(merged)}   places (file+time sections): {nsec}")
    print(f"layer-slots added over GAMMA: {added_total}")
    if dropped_refs:
        print(f"layers referenced by a preset but NOT in our merged channels (skipped): {len(dropped_refs)}")
        print("  " + ", ".join(sorted(dropped_refs)))
    print("\nsample places (GAMMA layers -> merged layers):")
    shown = 0
    for fname in sorted(merged):
        for sec in sorted(merged[fname]):
            g = len(gamma.get(fname, {}).get(sec, {}).get("dynamic", []))
            mm = len(merged[fname][sec]["dynamic"])
            if mm > g and shown < 10:
                print(f"  {fname} [{sec}]: {g} -> {mm}")
                shown += 1


MOD = HERE.parent                      # GammaExternal/Zone Soundscape
GDATA = MOD / "gamedata"
ENV = GDATA / "configs/environment"
SND = GDATA / "sounds/zs"              # per-channel folders under here
HDR = ("; Zone Soundscape - GENERATED by tools/merge.py; do not hand-edit, regenerate.\n"
       "; Per-channel sound provenance: tools/merged_channels.json. Method + credits: doc/.\n")


def _clean(d):
    if d.exists():
        import shutil as sh
        sh.rmtree(d)


def tune_settings(lines):
    """Middle-ground tuning: stretch periods (rarer) and cap max_distance (shorter
    carry). Leaves other setting lines untouched."""
    out = []
    for ln in lines:
        m = re.match(r'(\s*period[0-3]\s*=\s*)([0-9.]+)', ln)
        if m:
            out.append(f"{m.group(1)}{int(float(m.group(2)) * PERIOD_MULT)}")
            continue
        m = re.match(r'(\s*max_distance\s*=\s*)([0-9.]+)', ln)
        if m:
            out.append(f"{m.group(1)}{min(float(m.group(2)), MAX_DIST_CAP):.1f}")
            continue
        out.append(ln)
    return out


def cmd_deploy(_):
    import shutil as sh
    mc = json.loads((HERE / "merged_channels.json").read_text())
    mp = json.loads((HERE / "merged_presets.json").read_text())

    _clean(GDATA / "sounds"); _clean(ENV)   # wipe any prior generated output
    SND.mkdir(parents=True, exist_ok=True)
    (ENV / "ambients/presets").mkdir(parents=True, exist_ok=True)

    # 1. copy sounds into per-channel folders; build channel -> [deploy stems]
    stems, copied, inherited = {}, 0, 0
    for chan in sorted(mc):
        chosen = mc[chan]["chosen"]
        if chosen:
            cdir = SND / chan
            cdir.mkdir(parents=True, exist_ok=True)
            stems[chan] = []
            for i, c in enumerate(chosen, 1):
                sh.copy2(c["abs"], cdir / f"{i}.ogg")
                copied += 1
                stems[chan].append(f"zs\\{chan}\\{i}")
        elif mc[chan].get("orig_stems"):
            # unfilled (blowout/emission, packed-only): keep original refs, resolve from base VFS
            stems[chan] = [s.replace("/", "\\") for s in mc[chan]["orig_stems"]]
            inherited += 1
        else:
            stems[chan] = []

    # 2. write sound_channels.ltx (all channels inline, no includes = self-contained)
    out = [HDR]
    for chan in sorted(mc):
        out.append(f"[{chan}]")
        out.extend(tune_settings(mc[chan]["settings"]))
        s = stems.get(chan) or []
        out.append("\tsounds\t= " + (", ".join(s) if s else "ambient\\no_sound"))
        out.append("")
    # required no-sound sentinel channels the engine/presets reference
    SENTINELS = {
        "default": ["\tmax_distance = 600.0", "\tmin_distance = 300.0",
                    "\tperiod0 = 5000", "\tperiod1 = 10000", "\tperiod2 = 5000", "\tperiod3 = 10000"],
        "default_ambient_night": ["\tmax_distance = 2.0", "\tmin_distance = 1.0",
                    "\tperiod0 = 0", "\tperiod1 = 0", "\tperiod2 = 0", "\tperiod3 = 0"],
        "silent": ["\tmax_distance = 2.0", "\tmin_distance = 1.0",
                   "\tperiod0 = 0", "\tperiod1 = 0", "\tperiod2 = 0", "\tperiod3 = 0"],
    }
    for name, settings in SENTINELS.items():
        if name not in mc:
            out.append(f"[{name}]")
            out.extend(settings)
            out.append("\tsounds\t= ambient\\no_sound")
            out.append("")
    (ENV / "sound_channels.ltx").write_text("\n".join(out), encoding="utf-8")

    # 3. write preset files (base bed + effect lines kept, dynamic = merged layers)
    for fname, secs in mp.items():
        lines = [HDR]
        for sec, d in secs.items():
            lines.append(f"[{sec}]")
            lines.extend(d["lines"])
            if d["base"]:
                lines.append("\tsound_channels\t= " + ", ".join(d["base"]))
            if d["dynamic"]:
                lines.append("\tsound_channels_dynamic\t= " + ", ".join(d["dynamic"]))
            lines.append("")
        (ENV / "ambients/presets" / fname).write_text("\n".join(lines), encoding="utf-8")

    print(f"deployed to {MOD}")
    print(f"  sound_channels.ltx: {len(mc)} channels ({inherited} inherit original refs, e.g. blowout/emission)")
    print(f"  presets: {len(mp)} files")
    print(f"  sounds copied into per-channel folders: {copied}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan").set_defaults(func=cmd_plan)
    sub.add_parser("presets").set_defaults(func=cmd_presets)
    sub.add_parser("deploy").set_defaults(func=cmd_deploy)
    a = ap.parse_args(); a.func(a)
