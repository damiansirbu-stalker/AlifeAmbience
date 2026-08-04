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
- Measured, not dumped. Every sound goes through signal analysis for spectral shape,
  loudness, and length, then content-hash dedup and per-group loudness leveling. No junk,
  no duplicates, no guesswork.
- Never repetitive. Play rates are tuned so a long storm never overlaps into a wall and a
  channel with few sounds is not spammed, and a runtime no-repeat memory means you never
  hear the same call twice - the whole library is heard, not the same 10% on a loop.
- Composes, never duplicates. It adds its sounds INTO the game's own channels with DLTX,
  and never ships a sound your install already plays - filtered by content hash AND by
  acoustic fingerprint, so even a re-encoded copy of a base sound is caught. No collisions,
  no doubling, no extra density, over GAMMA, vanilla, or any soundscape.
- Provable. An in-game trace logs every sound as it plays, so an Anomaly run and a GAMMA
  run diff cleanly. Every file traces back to its origin mod, folder, filename, channel,
  and exact settings.
- Configurable. MCM volume control of the atmosphere per layer - spooks, screams, mutants,
  storm, wind, rain, underground, and more - and of the in-world radios, megaphones, and
  instruments.
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
  Every sound is put through signal analysis before it goes in, and the result is proven.
  Whether it becomes a looped bed or a one-shot scare is decided from measured length,
  steadiness (crest factor), and loudness (EBU R128), not from its filename.
  Identical files across packs collapse to one by content hash, and anything your install
  already plays is dropped - by hash and by acoustic fingerprint, so re-encoded copies are
  caught too. Loudness is leveled per group, outliers only, so a whisper and a scream keep
  their difference. A ledger proves no net-new dark sound is missed, and a provenance record
  maps every included sound back to its origin. The whole overlay rebuilds from the packs in
  one run.
  The pipeline, one command end to end:
    index what your install plays  ->  pool the packs' dark sounds  ->  drop every
    duplicate (hash AND acoustic fingerprint)  ->  measure and classify each  ->  level
    loudness  ->  compose the DLTX overlay  ->  prove coverage and origin.
  On the current build that meant 2695 candidate sounds pulled, 970 dropped because the
  game already plays them - including 350 re-encoded copies plain hashing would have
  missed - and 1593 genuinely new dark sounds shipped: zero duplicates, every one traced.

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
    Real Distant Mutants Sounds        - moddb (distant creature calls)
  Used under the terms on each source page. Only the selected audio is redistributed, with
  attribution. If an author requests removal, their pack is dropped from the build.
