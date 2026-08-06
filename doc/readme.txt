AlifeSpooks: dark horror ambience and in-world audio control for STALKER Anomaly / GAMMA, by Damian
Version: next (xlibs optional; no modded exes required)
GitHub: https://github.com/damiansirbu-stalker/AlifeSpooks
Changelog: https://github.com/damiansirbu-stalker/AlifeSpooks/blob/main/doc/changelog
Architecture: https://github.com/damiansirbu-stalker/AlifeSpooks/blob/main/doc/architecture.md
Russian / Na russkom: https://github.com/damiansirbu-stalker/AlifeSpooks/blob/main/doc/readme_ru.txt
Bugs, suggestions: https://github.com/damiansirbu-stalker/AlifeSpooks/issues

Alife Collection:
AlifeBalance: https://www.moddb.com/mods/stalker-anomaly/addons/alifebalance
AlifeDiegetic: https://www.moddb.com/mods/stalker-anomaly/addons/diegetic-audio-control-100
AlifeGuard: https://www.moddb.com/mods/stalker-anomaly/addons/alifeguard-1001
AlifePlus: https://www.moddb.com/mods/stalker-anomaly/addons/alifeplus-v1-0-01
AlifeSpooks: https://github.com/damiansirbu-stalker/AlifeSpooks
AlifeTactics: https://www.moddb.com/mods/stalker-anomaly/addons/alifetactics

! Reset MCM settings to defaults after updating !

The Zone used to be frightening. Modern soundscape mods sharpened its realism and, in
the trade, stripped the horror. AlifeSpooks puts it back, and hands you a mixer for the
in-world sound the Zone already plays.

Why it is different:
- Old-school horror, restored. The dread the realism packs removed: a scream past the
  treeline, a groan under the ground, wind that carries something wrong.
- Measured, not dumped. Every sound goes through signal analysis for spectral shape,
  loudness, and length, then a three-stage dedup - exact hash, acoustic fingerprint, and a
  waveform cross-correlation that tells a re-encoded copy from a genuinely different sound -
  and per-group loudness leveling. No junk, no duplicates, no lost variety.
- Never repetitive. Play rates are tuned so a long storm never overlaps into a wall and a
  channel with few sounds is not spammed, and a runtime no-repeat memory means you never
  hear the same call twice - the whole library is heard, not the same 10% on a loop.
- Composes, never duplicates. It adds its sounds INTO the game's own channels with DLTX,
  and never adds a sound your install already plays - matched by hash, by acoustic
  fingerprint, and confirmed by waveform, so even a re-encoded copy of a base sound is
  caught. No collisions, no doubling, no extra density, over GAMMA, vanilla, or any soundscape.
- Provable. An in-game trace logs every sound as it plays, so an Anomaly run and a GAMMA
  run diff cleanly. Every file traces back to its origin mod, folder, filename, channel,
  and exact settings.
- Configurable. MCM volume control of the atmosphere per layer - spooks, screams, mutants,
  storm, wind, rain, underground, and more.
- Growing. Original sounds recorded for this mod, and a scripted system that triggers
  dread inside buildings and lairs, are in progress.

One system in two MCM tabs - Atmosphere, and a Development tab that holds the trace controls
and a reset-to-defaults button.

Atmosphere:
  A dark ambient layer over your untouched engine bed, in two parts.
  Loop is one continuous low bed matched to where you stand: machine and metal in the
  X-Labs, dripping stone in the sewers, storm and rain in bad weather, fog on foggy days,
  a dark drone after dusk, a lighter wind by day.
  Effect is rare one-shot scares placed around you: distant growls and screams, metal
  groans and drips underground, far gunfire and drones in the ruins, owls and dogs and
  crows in the wild, storm and wind.
  Placement is traced from where the source packs used each sound, per level, per hour,
  per weather, then corrected against S.T.A.L.K.E.R. canon: underground labs get only
  tunnel dread, the whisper level is haunted dread and wind, city ruins lean human,
  swamps lean wildlife and fog.
  Fear comes from distance, rarity, and surprise, not volume.

How it is built:
  Every sound is put through signal analysis before it goes in, and the result is proven.
  Whether it becomes a looped bed or a one-shot scare is decided from measured length,
  steadiness (crest factor), and loudness (EBU R128), not from its filename.
  Duplicates collapse to one by a three-stage test: exact hash, then acoustic fingerprint to
  propose re-encoded copies, then a waveform cross-correlation to confirm two files really are
  the same recording before merging - so genuinely different sounds are never merged away.
  Anything your install already plays is excluded the same way, and each loop bed is
  deduped across the channels that feed it, so a continuous bed never loops the same recording.
  Loudness is leveled per group, outliers only, so a whisper and a scream keep their
  difference. A ledger proves no net-new dark sound is missed, and a provenance record maps
  every included sound back to its origin. The whole overlay rebuilds from the packs in one run.
  The pipeline, one command end to end:
    index what your install plays  ->  pool the packs' dark sounds  ->  dedup each channel to
    one copy per recording (hash, fingerprint, waveform)  ->  measure and classify each  ->
    level loudness  ->  compose the overlay (channels + placement)  ->  prove coverage and origin.
  On the current build that meant 5487 candidate sounds pulled and reduced to 1487 genuinely
  new dark sounds: the waveform test caught 177 re-encoded copies plain hashing kept, every
  sound the game already plays was excluded, and every included sound traces to its origin.

Installation:
  A DLTX overlay plus a few scripts. Loads at any position, changes nothing in the engine
  bed. Requires 44.1 kHz OGG playback, the Anomaly standard. The MCM and the in-game trace
  need xlibs. Without xlibs the mod still runs, content only.

Credits:
  The content is drawn from these community packs, with thanks to their authors:
    Dark Signal Weather and Ambiance   - Shrike
    Dark Signal Amplified Soundscape   - Shrike
    Soundscape Overhaul                - Solarint
    RETUNE Ambient Sounds              - Aphrodite_child
    Real Distant Mutants Sounds        - moddb (distant creature calls)
  Used under the terms on each source page. Only the selected audio is redistributed, with
  attribution. If an author requests removal, their pack is dropped from the build.
