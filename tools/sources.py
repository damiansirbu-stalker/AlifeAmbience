"""Source registry for the AlifeAmbience bed merge.

One declarative entry per pack. `MODS` derives from `SOURCES` preserving order (dedup is
order-sensitive). Sources are ALWAYS pulled locally by hand; the pipeline never downloads, so `url`
and `licence` are credit/provenance record only (doc/licensing.md holds the basis per source).

Licence values mirror doc/licensing.md:
  game       - GSC original-game audio, community-tolerated (vanilla, standalone builds)
  pd         - Public Domain, credit only
  cc         - Creative Commons, credit only
  permission - the author granted it for my S.T.A.L.K.E.R. mods (doc/licensing.md records each grant)
  pending    - not located / unconfirmed; do not ship until resolved
"""

SOURCES = [
    # ROSTER (2026-08-22, best-of-breed per category, not a union). `role` = what each pack contributes.
    # config spine + birds (its wind/foliage are muffled/stereo and get culled)
    {"name": "Amplified", "licence": "permission", "role": "config spine + birds",
     "url": "https://www.moddb.com/mods/stalker-anomaly/addons/dark-signal-amplified-soundscape",
     "path": "C:/Users/damian/Downloads/stalker_anomaly_mods/audio/Dark Signal Amplified Soundscape/gamedata"},

    # RETUNE/Antares family - BENCH (doc/architecture.md content model): a family enters only by
    # beating the current holder of its slot, by measurement and by ear.
    {"name": "RETUNE457", "licence": "permission", "role": "bench (RETUNE/Antares family)",
     "url": "https://www.moddb.com/mods/stalker-anomaly/addons/retune-ambience-sounds",
     "path": "D:/Games/GAMMA/GAMMA/mods/457- RETUNE Ambiant Sounds - Aphrodite_child/gamedata"},
    {"name": "myRETUNE", "licence": "pending", "role": "bench (RETUNE/Antares variant)",
     "url": None,  # AntaresWolverine 2.1; no moddb page found, confirm author before shipping
     "path": "C:/Users/damian/Downloads/stalker_anomaly_mods/audio/myRETUNE_AntaresWolverine_2.1/myRETUNE ambience sounds ver2.1/gamedata"},

    # insects + frogs (distinct, loud, mono) - ships no config, grafted into the spine's channels
    {"name": "AudioExpansion", "licence": "permission", "role": "insects + frogs",
     "url": "https://www.moddb.com/mods/stalker-anomaly/addons/audio-expansion",
     "path": "C:/Users/damian/Downloads/stalker_anomaly_mods/audio/Audio Expansion/gamedata"},

    # wind reinforcement + the helicopter (loud, mono) - ships no config, grafted
    {"name": "ImmersiveAmbience", "licence": "cc", "role": "wind + helicopter",
     "url": "https://www.moddb.com/mods/stalker-anomaly/addons/immersive-ambience-expansion",
     "path": "C:/Users/damian/Downloads/stalker_anomaly_mods/audio/Immersive Ambience Expansion/gamedata"},

    # interior bed (slam, interior winds) - Shrike's unreleased material; NOT materialized (0 unique md5)
    {"name": "ShrikeInterior", "licence": "permission", "role": "interior bed (skipped, redundant)",
     "url": None,  # unreleased, granted directly by Shrike
     "path": "C:/Users/damian/Downloads/stalker_anomaly_mods/audio/Dark Signal Unused Interior - Shrike/gamedata"},

    # environment CORE: wind, weather, birds, foliage (best-authored - mono, present, low content-limited)
    {"name": "Soundscape", "licence": "pd", "role": "environment core (wind/weather/birds/foliage)",
     "url": "https://www.moddb.com/mods/stalker-anomaly/addons/soundscape-overhaul-2",
     "path": "D:/Games/GAMMA/GAMMA/mods/3- Soundscape Overhaul - Solarint/gamedata"},

    # GSC base beds
    {"name": "vanilla", "licence": "game", "role": "GSC base",
     "url": None,
     "path": "D:/Games/GAMMA/Anomaly/tools/_unpacked"},
]

# ---- curation registers (doc/architecture.md: retention, gate 7) ----------------------------------
# DEPLOY_EXTRA: curated deploys OUTSIDE the ambient channel config. The engine thunderbolt system
# plays strike sounds from the paths vanilla thunderbolts.ltx names (`sound = nature\...`;
# thunderbolt.cpp:235 plays them positioned, speed-of-sound delayed, with a per-strike range).
# Deploying Amplified's strike recordings AT those vanilla paths upgrades the strikes with zero
# config - no collection or timing key is touched, so the weather mod's tuning stays intact. Only
# the 18 Amplified files whose names match a vanilla-referenced path deploy; the rest of nature/
# has no reachable section (see DISPOSITIONS). Rows: (source, rel under sounds/, deploy rel, reason).
_STRIKE = "strike upgrade at a vanilla thunderbolts.ltx sound path"
DEPLOY_EXTRA = [("Amplified", "nature/" + n + ".ogg", "nature/" + n + ".ogg", _STRIKE) for n in (
    "new_thunder1_hec", "new_thunder2_hec", "new_thunder3_hec", "new_thunder4_hec",
    "storm_2", "storm_3", "storm_4", "storm_5",
    "thunder-0", "thunder-0-hec", "thunder-1", "thunder-2", "thunder-3", "thunder-3-hec",
    "thundernew1", "thundernew2", "thundernew3", "thundernew5",
)]

# The vanilla surge bed pools (blowout_channels.ltx: blowout_impacts/rumble/ambient/flare).
# Amplified never shipped these recordings and vanilla sits in RESOLVE_SKIP, so the four channels
# were muted for lack of a source (found 2026-09-03). Explicit rows restore them without opening
# the vanilla tree to full path resolution or retention.
_SURGE = "vanilla surge bed pool (blowout_channels.ltx)"
DEPLOY_EXTRA += [("vanilla", "ambient/trx/blowout/" + n + ".ogg", "ambient/trx/blowout/" + n + ".ogg", _SURGE) for n in (
    "blowout_boom_01", "blowout_boom_02", "blowout_boom_03", "blowout_boom_04", "blowout_boom_05",
    "blowout_ambient_rumble_01", "blowout_ambient_rumble_02", "blowout_ambient_rumble_03", "blowout_ambient_rumble_04",
    "blowout_amb_01", "blowout_amb_02", "blowout_amb_03", "blowout_amb_04", "blowout_amb_05",
    "blowout_amb_06", "blowout_amb_07", "blowout_amb_08", "blowout_amb_09",
    "blowout_flare_01", "blowout_flare_02", "blowout_flare_03",
)]

# The vanilla ambient EFFECT sounds (effects.ltx effect_0..9 -> trx wind_gust wind_gust_01..06 +
# rnd_wind_1..3). Same case as the surge beds: their only source is vanilla, which sits in
# RESOLVE_SKIP, and the effect override (mod_effects_alifeambience.ltx) is read by no channel, so
# nothing pulled them. The override pointed sound= at the vanilla names while nothing deployed them,
# so the restored effect layer played silent (found 2026-09-07). Explicit rows carry the 9 files.
_EFFECT = "vanilla ambient effect sound (effects.ltx effect_0..9, mod_effects_alifeambience.ltx)"
DEPLOY_EXTRA += [("vanilla", "ambient/trx/nature/wind_gust/" + n + ".ogg", "ambient/trx/nature/wind_gust/" + n + ".ogg", _EFFECT) for n in (
    "wind_gust_01", "wind_gust_02", "wind_gust_03", "wind_gust_04", "wind_gust_05", "wind_gust_06",
    "rnd_wind_1", "rnd_wind_2", "rnd_wind_3",
)]

# DISPOSITIONS: every ambience-scope source file NOT referenced by the config / DEPLOY_EXTRA must be
# covered by a row here, else verify gate 7 FAILs the build. Verdicts: excluded (a decided no, with
# the reason), deferred (a signed decision to decide in a named later pass). Referenced files never
# need a row. Rows: (source, rel prefix under sounds/, verdict, reason).
DISPOSITIONS = [
    # Amplified thunder corpus (the clear-weather-thunder defect's home; architecture.md: Thunder)
    ("Amplified", "ambient/soundscape/nature/storm_", "deferred",
     "storm-bed candidates for the storm-role ear pass"),
    ("Amplified", "ambient/soundscape/nature/pre_storm_", "deferred",
     "pre-storm bed candidates for the storm-role ear pass"),
    ("Amplified", "ambient/soundscape/nature/", "excluded",
     "strike claps duplicating the sounds/nature strike set (the engine thunderbolt system plays "
     "those); the rumbles are picked into thunder_far"),
    ("Amplified", "nature/", "excluded",
     "strike files with no vanilla thunderbolts.ltx section; reachable only by shipping thunderbolt "
     "configs, which fights the weather mod (DEPLOY_EXTRA carries the 18 vanilla-matched ones)"),
    ("Amplified", "ambience_exp/wind_random/", "excluded",
     "wind_random cap overflow: 40 best distinct recordings picked (native-mono first, then loudness)"),
    ("ImmersiveAmbience", "ambience_exp/wind_random/", "excluded",
     "wind_random cap overflow (see the Amplified row)"),
    ("Amplified", "ambient/soundscape/underground/under_", "excluded",
     "ugrnd_ambient_new cap overflow: 40 loudest of the under_ family picked (line was over the ini "
     "buffer guard); stray cross-folder refs dropped per the single-source pool rule"),
    # spine remainder: curated category by category (architecture.md, order of work)
    ("Amplified", "ambient/", "deferred", "spine curation passes pending"),
    ("Amplified", "ambience_exp/", "deferred", "spine curation passes pending"),
    # gap-channel packs: referenced content is in; the rest awaits its curation pass
    ("AudioExpansion", "ambient/", "deferred", "insects/frogs referenced; remainder awaits curation"),
    ("AudioExpansion", "nature/", "deferred", "unreviewed candidates"),
    ("ImmersiveAmbience", "ambience_exp/", "deferred", "wind/helicopter referenced; remainder awaits curation"),
    ("Soundscape", "ambient/", "deferred", "wind-family A/B and thunder-rumble candidates for the ear pass"),
    # bench packs
    ("RETUNE457", "ambient/", "deferred", "bench: enters only by beating a slot holder"),
    ("RETUNE457", "ambience_exp/", "deferred", "bench"),
    ("myRETUNE", "ambient/", "deferred", "bench: enters only by beating a slot holder"),
    ("myRETUNE", "ambience_exp/", "deferred", "bench"),
]


def mods():
    """(name, path) pairs in registry order - the shape the pipeline expects."""
    return [(s["name"], s["path"]) for s in SOURCES]
