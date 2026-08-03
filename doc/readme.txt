AlifeAmbience: dark horror ambience and in-world audio control for STALKER Anomaly / GAMMA, by Damian
Version: next (xlibs optional; no modded exes required)
GitHub: https://github.com/damiansirbu-stalker/AlifeAmbience
Changelog: https://github.com/damiansirbu-stalker/AlifeAmbience/blob/main/doc/changelog
Architecture: https://github.com/damiansirbu-stalker/AlifeAmbience/blob/main/doc/architecture.md
Russian / Na russkom: https://github.com/damiansirbu-stalker/AlifeAmbience/blob/main/doc/readme_ru.txt
Bugs, suggestions: https://github.com/damiansirbu-stalker/AlifeAmbience/issues

! Reset MCM settings to defaults after updating !

The Zone used to be frightening. Modern soundscape mods sharpened its realism and, in
the trade, stripped the horror. AlifeAmbience puts it back, and hands you a mixer for the
in-world sound the Zone already plays.

Why it is different:
- Old-school horror, restored. The dread the realism packs removed: a scream past the
  treeline, a groan under the ground, wind that carries something wrong.
- Measured, not dumped. Every sound is analysed by tools for spectral shape, loudness,
  and length, then deduplicated and loudness-leveled. No junk, no duplicates, no guesswork.
- Composes, never overrides. Most packs carry thousands of files that all rewrite the same
  base channels, so half never fire and the rest collide. This one appends with DLTX and
  places every sound on purpose, over GAMMA, vanilla, or any soundscape.
- Provable. An in-game trace logs every sound as it plays. Every file traces back to its
  origin mod, folder, filename, channel, and exact settings.
- Configurable. MCM control of the atmosphere per mood and of the in-world radios,
  megaphones, and instruments.
- Growing. Original sounds recorded for this mod, and a scripted system that triggers
  dread inside buildings and lairs, are in progress.

Two systems, two MCM tabs.

Atmosphere:
  A dark ambient layer over your untouched engine bed, in two parts.
  Texture is one continuous low bed matched to where you stand: machine and metal in the
  X-Labs, dripping stone in the sewers, storm and rain in bad weather, fog on foggy days,
  a dark drone after dusk, a lighter wind by day.
  Accent is rare one-shot scares placed around you: distant growls and screams, metal
  groans and drips underground, far gunfire and drones in the ruins, owls and dogs and
  crows in the wild, storm and wind.
  Placement is traced from where the source packs used each sound, per level, per hour,
  per weather, then corrected against S.T.A.L.K.E.R. canon: underground labs get only
  tunnel dread, the whisper level is haunted dread and wind, city ruins lean human,
  swamps lean wildlife and fog.
  Fear comes from distance, rarity, and surprise, not volume.

Diegetic:
  Volume, enable, and frequency control for the in-world sound the characters hear: base
  and campfire radios, megaphone announcers, campfire guitar and harmonica. At default it
  changes nothing. Turn a base radio down without touching the rest, or silence the
  megaphones and keep the guitar. The instruments need a campfire-instrument mod present.

How it is built:
  A tool measures every sound and proves the result. Whether a sound becomes a looped bed
  or a one-shot scare is decided from its measured length and steadiness, not its filename.
  Identical files across packs collapse to one by content hash. Loudness is leveled per
  group, outliers only, so a whisper and a scream keep their difference. A content-hash
  ledger proves no dark sound in a source pack is missed, and a provenance record maps
  every included sound back to its origin. The whole overlay rebuilds from the packs in
  one run.

Installation:
  A DLTX overlay plus a few scripts. Loads at any position, changes nothing in the engine
  bed. Requires 44.1 kHz OGG playback, the Anomaly standard. The MCM and the in-game trace
  need xlibs. Without xlibs the mod still runs, content only.

Credits:
  The Diegetic tab plays the game's own in-world sound and adds no audio. The Atmosphere
  content is drawn from these community packs, with thanks to their authors:
    Dark Signal Weather and Ambiance   - Shrike
    Dark Signal Amplified Soundscape   - Shrike
    Soundscape Overhaul                - Solarint
    RETUNE Ambient Sounds              - Aphrodite_child
  Used under the terms on each source page. Only the selected audio is redistributed, with
  attribution. If an author requests removal, their pack is dropped from the build.
