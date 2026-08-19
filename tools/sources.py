"""Source registry for the AlifeAmbience bed merge.

One declarative entry per pack. `MODS` derives from `SOURCES` preserving order (dedup is
order-sensitive). Sources are ALWAYS pulled locally by hand; the pipeline never downloads, so `url` is a
credit/provenance reference only. A licence gate (`check_licences`) stops the build on any source not
cleared for AlifeAmbience.

Licence values mirror doc/licensing.md:
  game       - GSC original-game audio, community-tolerated (vanilla, standalone builds)
  pd         - Public Domain, credit only
  cc         - Creative Commons, credit only
  permission - author granted for AlifeSpooks; must be EXTENDED to AlifeAmbience before public release
  pending    - not located / unconfirmed; do not ship until resolved
"""

SOURCES = [
    # content + config spine
    {"name": "Amplified", "licence": "permission", "role": "spine (content + config)",
     "url": "https://www.moddb.com/mods/stalker-anomaly/addons/dark-signal-amplified-soundscape",
     "path": "C:/Users/damian/Downloads/anomaly_audio_mods/Dark Signal Amplified Soundscape/gamedata"},

    # audible background bed masters
    {"name": "RETUNE457", "licence": "permission", "role": "audible bed masters",
     "url": "https://www.moddb.com/mods/stalker-anomaly/addons/retune-ambience-sounds",
     "path": "D:/Games/GAMMA/GAMMA/mods/457- RETUNE Ambiant Sounds - Aphrodite_child/gamedata"},
    {"name": "myRETUNE", "licence": "pending", "role": "audible bed masters (variant)",
     "url": None,  # AntaresWolverine 2.1; no moddb page found, confirm author before shipping
     "path": "C:/Users/damian/Downloads/anomaly_audio_mods/myRETUNE_AntaresWolverine_2.1/myRETUNE ambience sounds ver2.1/gamedata"},

    # species content (frogs, night birds, time-of-day insects, bats) - ships no config, grafted
    {"name": "AudioExpansion", "licence": "permission", "role": "species content",
     "url": "https://www.moddb.com/mods/stalker-anomaly/addons/audio-expansion",
     "path": "C:/Users/damian/Downloads/anomaly_audio_mods/Audio Expansion/gamedata"},

    # weather-event layer (rain, wind by intensity)
    {"name": "ImmersiveAmbience", "licence": "cc", "role": "weather events",
     "url": "https://www.moddb.com/mods/stalker-anomaly/addons/immersive-ambience-expansion",
     "path": "C:/Users/damian/Downloads/anomaly_audio_mods/Immersive Ambience Expansion/gamedata"},

    # interior bed (slam, interior winds) - Shrike's unreleased material
    {"name": "ShrikeInterior", "licence": "permission", "role": "interior bed",
     "url": None,  # unreleased, granted directly by Shrike
     "path": "C:/Users/damian/Downloads/anomaly_audio_mods/Dark Signal Unused Interior - Shrike/gamedata"},

    # public-domain fill, credit only
    {"name": "Soundscape", "licence": "pd", "role": "fill (public domain)",
     "url": "https://www.moddb.com/mods/stalker-anomaly/addons/soundscape-overhaul-2",
     "path": "D:/Games/GAMMA/GAMMA/mods/3- Soundscape Overhaul - Solarint/gamedata"},

    # GSC base beds
    {"name": "vanilla", "licence": "game", "role": "GSC base",
     "url": None,
     "path": "D:/Games/GAMMA/Anomaly/tools/_unpacked"},
]

# licences cleared to build/ship.
#   PRIVATE build: personal use of legitimately-downloaded packs is unrestricted, so everything we
#     hold locally is allowed - including `pending` (terms unknown but private use needs no grant).
#   PUBLIC release: only free licences; `permission` grants were scoped to AlifeSpooks and must be
#     extended to AlifeAmbience first, and `pending` must be resolved. (see doc/licensing.md)
CLEARED_PRIVATE = {"game", "pd", "cc", "permission", "pending"}
CLEARED_PUBLIC = {"game", "pd", "cc"}


def mods():
    """(name, path) pairs in registry order - the shape the pipeline expects."""
    return [(s["name"], s["path"]) for s in SOURCES]


def check_licences(public=False):
    """Stop the build on any source not cleared. `public=True` requires permission grants to be
    extended to AlifeAmbience (drops the provisional `permission` clearance)."""
    cleared = CLEARED_PUBLIC if public else CLEARED_PRIVATE
    blocked = [s["name"] for s in SOURCES if s["licence"] not in cleared]
    if blocked:
        scope = "public release" if public else "build"
        raise SystemExit(
            f"licence gate ({scope}): uncleared sources: {', '.join(blocked)} "
            f"(see doc/licensing.md)")
